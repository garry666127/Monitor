"""Detect person intervals inside a configured zone; preserve source timestamps."""
import argparse
from collections import deque
import csv
from datetime import datetime
import json
import math
from pathlib import Path
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE


def timestamp(seconds):
    ms = max(0, round(seconds * 1000))
    hours, ms = divmod(ms, 3600000)
    minutes, ms = divmod(ms, 60000)
    seconds, ms = divmod(ms, 1000)
    return f'{hours:02}:{minutes:02}:{seconds:02}.{ms:03}'


def read_config(path, width, height):
    cfg = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    if (cfg.get('video_width'), cfg.get('video_height')) != (width, height):
        raise ValueError(f'區域設定解析度與影片 {width}x{height} 不同，請重新設定 ROI。')
    for key in ('main_roi', 'person_zone'):
        rect = cfg[key]
        values = [rect[k] for k in ('x', 'y', 'width', 'height')]
        if any(type(v) is not int for v in values):
            raise ValueError(f'{key} 座標必須為整數。')
        x, y, w, h = values
        if x < 0 or y < 0 or w <= 0 or h <= 0 or x+w > width or y+h > height:
            raise ValueError(f'{key} 超出畫面或大小無效。')
    main, zone = cfg['main_roi'], cfg['person_zone']
    if not (main['x'] <= zone['x'] and main['y'] <= zone['y']
            and zone['x']+zone['width'] <= main['x']+main['width']
            and zone['y']+zone['height'] <= main['y']+main['height']):
        raise ValueError('Person Zone 必須位於 Main ROI 內。')
    return main, zone


def in_zone(box, zone):
    x1, y1, x2, y2 = box
    return (zone['x'] <= (x1+x2)/2 < zone['x']+zone['width']
            and zone['y'] <= (y1+y2)/2 < zone['y']+zone['height'])


def near(a, b):
    """Require successive evidence to refer to nearby, overlapping boxes."""
    return min(a[2], b[2]) > max(a[0], b[0]) and min(a[3], b[3]) > max(a[1], b[1])


class Intervals:
    def __init__(self, confirm_window=0.5, gap=1.0):
        self.window, self.gap = confirm_window, gap
        self.pending = deque()
        self.start = self.last_seen = self.last_end = None
        self.intervals = []

    def close(self):
        if self.start is not None:
            self.intervals.append((self.start, self.last_end))
        self.start = self.last_seen = self.last_end = None
        self.pending.clear()

    def update(self, t, frame_end, boxes):
        if self.start is not None and t-self.last_seen > self.gap:
            self.close()
        while self.pending and t-self.pending[0][0] > self.window:
            self.pending.popleft()
        if not boxes:
            return
        if self.start is None:
            matches = [old_t for old_t, old_boxes in self.pending
                       if t > old_t and any(near(a, b) for a in old_boxes for b in boxes)]
            if matches:
                self.start = min(matches)
            self.pending.append((t, boxes))
        if self.start is not None:
            self.last_seen, self.last_end = t, frame_end


def save(output, intervals, metadata):
    with (output/'person_intervals.csv').open('w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(['編號', '開始時間', '結束時間', '開始秒數', '結束秒數', '持續時間'])
        for i, (start, end) in enumerate(intervals, 1):
            writer.writerow([i, timestamp(start), timestamp(end), round(start, 3),
                             round(end, 3), round(end-start, 3)])
    lines = [f"影片：{metadata['video']}", f"狀態：{metadata['status']}",
             '時間為原始影片時間；片段試跑只涵蓋指定範圍。',
             '區間涵蓋最後命中的影格，不額外加上結束等待時間。']
    lines += [f'{i}. {timestamp(a)} ~ {timestamp(b)}' for i, (a, b) in enumerate(intervals, 1)]
    if not intervals:
        lines.append('本次分析範圍內沒有通過連續確認的人物區間。')
    (output/'person_intervals.txt').write_text('\n'.join(lines), encoding='utf-8')
    (output/'run.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')


def analyze(args):
    import av
    import cv2
    sys.path.insert(0, str(ROOT))
    from runtime import load_model
    cv2.setNumThreads(1)
    video = Path(args.video).resolve()
    if not video.is_file():
        raise ValueError('找不到影片。')
    for key in ('confidence', 'gap', 'start', 'seconds', 'check_interval', 'pre_roll'):
        value = getattr(args, key)
        if not math.isfinite(value) or value < 0:
            raise ValueError(f'{key} 必須是有限的非負數。')
    if not 0 < args.confidence <= 1 or args.gap <= 0:
        raise ValueError('confidence 必須介於 0 與 1，gap 必須大於 0。')
    if args.check_interval <= 0 or args.pre_roll <= 0:
        raise ValueError('定期檢查及回查秒數必須大於 0。')
    started = time.perf_counter()
    print(f'模式：{args.mode}；模型：YOLO11s；載入模型中...', flush=True)
    model = load_model(args.size, args.backend, 'yolo11s')
    output = HERE/'results'/(video.stem+'_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    output.mkdir(parents=True)
    state = Intervals(gap=args.gap)
    writer = None
    frames, hits = 0, 0
    scanner = None
    frame_log = None
    metadata = dict(video=str(video), status='分析中', settings=vars(args),
                    interval_rule='two overlapping detections within 0.5s; end at last detected frame end')
    print(f'結果資料夾：{output}', flush=True)
    try:
        with av.open(str(video)) as container, (output/'detections.csv').open('w', newline='', encoding='utf-8-sig') as log:
            stream = container.streams.video[0]
            rate = stream.average_rate
            if rate is None or float(rate) <= 0:
                raise ValueError('無法取得影片 FPS。')
            fps = float(rate)
            main, zone = read_config(args.config, stream.width, stream.height)
            metadata['config'] = {'main_roi': main, 'person_zone': zone}
            origin = float((stream.start_time or 0)*stream.time_base)
            if args.start:
                container.seek(int((args.start+origin)/stream.time_base), stream=stream, backward=True)
            if args.debug:
                writer = cv2.VideoWriter(str(output/'debug.mp4'), cv2.VideoWriter_fourcc(*'mp4v'),
                                         fps, (stream.width, stream.height))
                if not writer.isOpened():
                    raise RuntimeError('無法建立除錯影片。')
            rows = csv.writer(log)
            rows.writerow(['seconds', 'time', 'confidence', 'x1', 'y1', 'x2', 'y2', 'in_zone'])
            rx, ry, rw, rh = [main[k] for k in ('x', 'y', 'width', 'height')]
            from hybrid import Frame, HybridScanner, MotionDetector
            motion_detector = MotionDetector() if args.mode == 'hybrid' else None
            frame_log = (output/'frames.csv').open('w', newline='', encoding='utf-8-sig')
            frame_rows = csv.writer(frame_log)
            frame_rows.writerow(['seconds', 'time', 'check', 'person_boxes', 'confirmed_present'])

            def predict(image):
                roi = image[ry:ry+rh, rx:rx+rw]
                result = model.predict(roi, classes=[0], conf=args.confidence, imgsz=args.size,
                                       device='intel:cpu' if args.backend == 'openvino' else 'cpu', verbose=False)[0]
                found = []
                for x1, y1, x2, y2, score, _ in result.boxes.data.cpu().tolist():
                    box = (x1+rx, y1+ry, x2+rx, y2+ry)
                    found.append((box, score, in_zone(box, zone)))
                return found

            def emit(record):
                nonlocal hits
                t, image = record.time, record.image
                candidates = []
                for box, score, inside in record.detections or []:
                    rows.writerow([round(t, 6), timestamp(t), round(score, 4),
                                   *[round(v, 1) for v in box], inside])
                    if inside:
                        candidates.append(box)
                    if writer is not None:
                        a, b, c, d = map(round, box)
                        color = (0, 255, 0) if inside else (0, 165, 255)
                        cv2.rectangle(image, (a, b), (c, d), color, 2)
                        cv2.putText(image, f'person {score:.2f}', (a, max(15, b-5)),
                                    cv2.FONT_HERSHEY_SIMPLEX, .5, color, 1)
                # An unchecked frame must not become negative evidence.
                if record.detections is not None:
                    state.update(t, record.end, candidates)
                hits += bool(candidates)
                frame_rows.writerow([round(t, 6), timestamp(t), record.reason,
                                     len(candidates) if record.detections is not None else '',
                                     state.start is not None])
                if writer is not None:
                    for rect in (main, zone):
                        x, y, w, h = [rect[k] for k in ('x', 'y', 'width', 'height')]
                        cv2.rectangle(image, (x, y), (x+w, y+h), (255, 255, 0), 1)
                    label = ('NOT CHECKED' if record.detections is None else
                             'PRESENT' if state.start is not None else
                             'CANDIDATE' if candidates else 'NO DETECTION')
                    cv2.putText(image, f'{timestamp(t)} {label}', (12, 25),
                                cv2.FONT_HERSHEY_SIMPLEX, .6, (255, 255, 255), 2)
                    cv2.putText(image, record.reason, (12, 48),
                                cv2.FONT_HERSHEY_SIMPLEX, .5, (255, 255, 255), 1)
                    writer.write(image)
                if 'first_frame_seconds' not in metadata:
                    metadata['first_frame_seconds'] = t
                    cv2.imencode('.jpg', image)[1].tofile(str(output/'first_frame.jpg'))
                metadata['last_frame_end_seconds'] = record.end

            scanner = HybridScanner(predict, emit, interval=args.check_interval,
                                    pre_roll=args.pre_roll, hold=max(1.0, args.gap+.5),
                                    thorough=args.mode == 'thorough')
            total_end = (float(stream.duration*stream.time_base) if stream.duration is not None
                         else float(container.duration/av.time_base) if container.duration else None)
            if args.seconds:
                total_end = min(total_end, args.start+args.seconds) if total_end else args.start+args.seconds
            last_progress = -1
            last_t = None
            for decoded in container.decode(stream):
                if decoded.pts is None:
                    raise RuntimeError('影格缺少時間戳，無法可靠記錄區間。')
                t = float(decoded.pts*decoded.time_base)-origin
                if t < args.start:
                    continue
                if args.seconds and t >= args.start+args.seconds:
                    break
                if last_t is not None and t <= last_t:
                    raise RuntimeError('影片時間戳未遞增，分析已停止。')
                last_t = t
                frame_end = t+(float(decoded.duration*decoded.time_base) if decoded.duration else 1/fps)
                if args.seconds:
                    frame_end = min(frame_end, args.start+args.seconds)
                image = decoded.to_ndarray(format='bgr24')
                motion = motion_detector.observe(image[ry:ry+rh, rx:rx+rw]) if motion_detector else False
                frames += 1
                scanner.push(Frame(t, frame_end, image), motion)
                progress = int(time.perf_counter()-started)//10
                if progress != last_progress:
                    elapsed = time.perf_counter()-started
                    completed = max(0.001, frame_end-args.start)
                    eta = max(0, total_end-frame_end)*elapsed/completed if total_end else None
                    estimate = (f' | 預估剩餘 {eta/60:.1f} 分鐘'
                                if eta is not None and frames >= 30 else ' | 耗時估算中')
                    print(f'{timestamp(t)} | {frames} 幀 | YOLO {scanner.inferred} 幀'
                          f' | {frames/max(.01,elapsed):.1f} 幀/秒{estimate}', flush=True)
                    last_progress = progress
            if not frames:
                raise ValueError('指定範圍沒有可分析的影格。')
            scanner.finish()
        metadata['status'] = '片段分析完成' if args.start or args.seconds else '分析完成'
    except BaseException as exc:
        metadata['status'] = '中止或失敗（結果不完整）'
        metadata['error'] = str(exc)
        raise
    finally:
        if writer is not None:
            writer.release()
        if frame_log is not None:
            frame_log.close()
        if scanner is not None:
            metadata.update(inferred_frames=scanner.inferred, replayed_frames=scanner.replayed,
                            periodic_checks=scanner.periodic, buffer_evictions=scanner.evicted,
                            skipped_frames=frames-scanner.inferred)
        state.close()
        metadata.update(frames=frames, hit_frames=hits, elapsed_seconds=time.perf_counter()-started)
        save(output, state.intervals, metadata)
    print(f'完成：{len(state.intervals)} 段；{output}', flush=True)
    print(f'共 {frames} 幀，YOLO 檢查 {scanner.inferred} 幀，'
          f'略過 {(frames-scanner.inferred)/frames:.1%}；'
          f'耗時 {metadata["elapsed_seconds"]/60:.1f} 分鐘。', flush=True)
    return output


def main():
    parser = argparse.ArgumentParser(description='人物區間偵測（MOG2 + YOLO11s + ROI）')
    parser.add_argument('video')
    parser.add_argument('--config', default=str(HERE/'zone_config.json'))
    parser.add_argument('--confidence', type=float, default=.25)
    parser.add_argument('--gap', type=float, default=1.0)
    parser.add_argument('--size', type=int, choices=(640, 960), default=640)
    parser.add_argument('--backend', choices=('openvino', 'pytorch'), default='openvino')
    parser.add_argument('--mode', choices=('hybrid', 'thorough'), default='hybrid')
    parser.add_argument('--check-interval', type=float, default=5.0, help='無動作時定期補查秒數')
    parser.add_argument('--pre-roll', type=float, default=2.0, help='觸發前回查秒數，最多保留 120 幀')
    parser.add_argument('--debug', action='store_true')
    parser.add_argument('--start', type=float, default=0, help='原片開始秒數')
    parser.add_argument('--seconds', type=float, default=0, help='分析長度，0 表示至片尾')
    args = parser.parse_args()
    try:
        analyze(args)
    except (Exception, KeyboardInterrupt) as exc:
        print(f'分析未完成：{exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
