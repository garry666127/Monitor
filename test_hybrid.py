import unittest

from hybrid import Frame, HybridScanner, MotionDetector
from detect_person_yolo import Intervals

BOX = ((10, 10, 40, 100), .8, True)


class HybridTests(unittest.TestCase):
    def scanner(self, positives=(), **kwargs):
        self.calls, self.output = [], []
        def predict(t):
            self.calls.append(t)
            return [BOX] if t in positives else []
        return HybridScanner(predict, self.output.append, **kwargs)

    def feed(self, scanner, times, motions=()):
        for t in times:
            scanner.push(Frame(t, t+.25, t), t in motions)

    def test_idle_skips_frames_and_still_checks_periodically(self):
        s = self.scanner()
        self.feed(s, [i/4 for i in range(81)])
        s.finish()
        self.assertLess(len(self.calls), 20)
        self.assertGreaterEqual(s.periodic, 3)
        self.assertEqual(len(self.output), 81)
        self.assertTrue(any(f.detections is None for f in self.output))

    def test_motion_replays_without_duplicate_inference_or_output(self):
        s = self.scanner()
        self.feed(s, [i/4 for i in range(33)], [5])
        s.finish()
        for t in [3, 3.25, 4, 4.75, 5]:
            self.assertIn(t, self.calls)
        self.assertEqual(len(self.calls), len(set(self.calls)))
        self.assertEqual([f.time for f in self.output], [i/4 for i in range(33)])

    def test_periodic_hit_replays_then_confirms_in_source_order(self):
        # Last warmup check is 1.75; periodic check is 6.75.
        s = self.scanner(positives=[6.5, 6.75, 7, 7.25])
        self.feed(s, [i/4 for i in range(41)])
        s.finish()
        state = Intervals()
        for f in self.output:
            if f.detections is not None:
                state.update(f.time, f.end, [box for box, _, inside in f.detections if inside])
        state.close()
        self.assertEqual(state.intervals, [(6.5, 7.5)])
        self.assertIn(6.5, self.calls)

    def test_stationary_person_keeps_dense_checks_without_motion(self):
        positives = [i/4 for i in range(60)]
        s = self.scanner(positives=positives)
        self.feed(s, positives)
        s.finish()
        self.assertEqual(len(self.calls), 60)

    def test_single_candidate_gets_followup_before_confirmation_expires(self):
        s = self.scanner(positives=[6.75])
        self.feed(s, [i/4 for i in range(33)])
        s.finish()
        self.assertIn(7, self.calls)
        self.assertIn(7.25, self.calls)

    def test_tail_hit_replays_pending_frames(self):
        s = self.scanner(positives=[4.5, 4.75])
        self.feed(s, [i/4 for i in range(20)])
        s.finish()
        self.assertIn(4.5, self.calls)
        self.assertEqual(self.output[-1].reason, 'FINAL')

    def test_buffer_is_bounded_at_high_fps(self):
        s = self.scanner(max_frames=10)
        for i in range(400):
            s.push(Frame(i/100, (i+1)/100, i/100), False)
            self.assertLessEqual(len(s.pending), 11)
        s.finish()
        self.assertGreater(s.evicted, 0)
        self.assertEqual(len(self.output), 400)

    def test_thorough_checks_every_frame_once(self):
        s = self.scanner(thorough=True)
        self.feed(s, [i/4 for i in range(60)])
        s.finish()
        self.assertEqual(len(self.calls), 60)

    def test_mog2_detects_new_foreground_after_background_training(self):
        import numpy as np
        motion = MotionDetector()
        image = np.zeros((392, 352, 3), dtype=np.uint8)
        for _ in range(100):
            motion.observe(image)
        self.assertFalse(motion.observe(image))
        image[100:300, 150:210] = 255
        self.assertTrue(motion.observe(image))


if __name__ == '__main__':
    unittest.main()
