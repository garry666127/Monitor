"""Motion schedules YOLO; only YOLO results count as person evidence."""
from collections import deque
from dataclasses import dataclass


@dataclass
class Frame:
    time: float
    end: float
    image: object
    detections: object = None
    reason: str = 'SKIPPED'


class MotionDetector:
    def __init__(self):
        import cv2
        self.cv = cv2
        self.background = cv2.createBackgroundSubtractorMOG2(
            history=300, varThreshold=25, detectShadows=False)
        self.kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))

    def observe(self, roi):
        cv = self.cv
        width = min(176, roi.shape[1])
        small = cv.resize(roi, (width, max(1, round(roi.shape[0]*width/roi.shape[1]))))
        gray = cv.GaussianBlur(cv.cvtColor(small, cv.COLOR_BGR2GRAY), (5, 5), 0)
        mask = self.background.apply(gray, learningRate=.01)
        mask = cv.morphologyEx(mask, cv.MORPH_OPEN, self.kernel)
        count, _, stats, _ = cv.connectedComponentsWithStats(mask)
        return any(stats[i, cv.CC_STAT_AREA] >= 40 for i in range(1, count))


class HybridScanner:
    """Delay output so replay can fill old frames without reversing state time.

    predict(image) returns [(full_image_box, score, inside_zone), ...].
    emit(frame) is called once per input frame, in source order.
    """
    def __init__(self, predict, emit, interval=5.0, pre_roll=2.0,
                 hold=1.0, max_frames=120, thorough=False):
        self.predict, self.emit = predict, emit
        self.interval, self.pre_roll, self.hold = interval, pre_roll, hold
        self.max_frames, self.thorough = max_frames, thorough
        self.pending = deque()
        self.dense_until = self.last_check = float('-inf')
        self.first_time = None
        self.inferred = self.replayed = self.periodic = self.evicted = 0

    def infer(self, frame, reason):
        if frame.detections is not None:
            return
        frame.detections = self.predict(frame.image)
        frame.reason = reason
        self.inferred += 1
        self.replayed += reason == 'REPLAY'
        self.periodic += reason == 'PERIODIC'
        self.last_check = max(self.last_check, frame.time)
        if any(inside for _, _, inside in frame.detections):
            self.dense_until = max(self.dense_until, frame.end+self.hold)

    def push(self, frame, motion):
        if self.first_time is None:
            self.first_time = frame.time
        # Retain a bounded pre-roll. No old frame is emitted twice.
        while self.pending and (frame.time-self.pending[0].time > self.pre_roll
                                or len(self.pending) >= self.max_frames):
            self.evicted += len(self.pending) >= self.max_frames
            self.emit(self.pending.popleft())
        if motion:
            self.dense_until = max(self.dense_until, frame.time+self.hold)
        warmup = frame.time-self.first_time < 2.0
        dense = self.thorough or warmup or frame.time <= self.dense_until
        due = frame.time-self.last_check >= self.interval
        if dense:
            for old in self.pending:
                self.infer(old, 'REPLAY')
            self.infer(frame, 'YOLO' if self.thorough else 'WARMUP' if warmup else 'DENSE')
        elif due:
            # Probe current first, but only emit in chronological order.
            self.infer(frame, 'PERIODIC')
            if any(inside for _, _, inside in frame.detections):
                for old in self.pending:
                    self.infer(old, 'REPLAY')
        self.pending.append(frame)

    def finish(self):
        # Always probe the final frame; a hit also replays the retained tail.
        if self.pending and self.pending[-1].detections is None:
            self.infer(self.pending[-1], 'FINAL')
            if any(inside for _, _, inside in self.pending[-1].detections):
                for old in self.pending:
                    self.infer(old, 'REPLAY')
        self.flush()

    def flush(self):
        while self.pending:
            self.emit(self.pending.popleft())
