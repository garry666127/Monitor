import json
from pathlib import Path
import tempfile
import unittest

from detect_person_yolo import Intervals, in_zone, read_config


class PresenceTests(unittest.TestCase):
    box = (10, 10, 40, 90)

    def test_one_false_positive_does_not_create_interval(self):
        state = Intervals()
        state.update(0, .1, [self.box])
        state.update(.6, .7, [])
        state.close()
        self.assertEqual(state.intervals, [])

    def test_brief_miss_is_bridged_but_end_is_last_positive_frame(self):
        state = Intervals()
        for t, boxes in [(0, [self.box]), (.1, [self.box]), (.5, []), (.8, [self.box]), (1.9, [])]:
            state.update(t, t+.1, boxes)
        self.assertEqual(state.intervals, [(0, .9)])

    def test_distant_false_detections_do_not_confirm_each_other(self):
        state = Intervals()
        state.update(0, .1, [self.box])
        state.update(.1, .2, [(100, 100, 140, 190)])
        state.close()
        self.assertEqual(state.intervals, [])

    def test_end_of_video_uses_same_endpoint_as_normal_close(self):
        state = Intervals()
        state.update(1, 1.1, [self.box])
        state.update(1.1, 1.2, [self.box])
        state.close()
        self.assertEqual(state.intervals, [(1, 1.2)])

    def test_long_gap_splits_events(self):
        state = Intervals()
        for t in [0, .1, 2, 2.1]:
            state.update(t, t+.1, [self.box])
        state.close()
        self.assertEqual(len(state.intervals), 2)

    def test_zone_uses_full_box_center(self):
        zone = dict(x=20, y=20, width=30, height=40)
        self.assertTrue(in_zone(self.box, zone))
        self.assertFalse(in_zone((0, 0, 10, 10), zone))

    def test_wrong_resolution_rejected(self):
        with self.assertRaisesRegex(ValueError, '解析度'):
            read_config(Path(__file__).with_name('zone_config.example.json'), 1920, 1080)

    def test_empty_roi_rejected(self):
        cfg = dict(video_width=100, video_height=100,
                   main_roi=dict(x=0, y=0, width=0, height=100))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'config.json'
            path.write_text(json.dumps(cfg))
            with self.assertRaisesRegex(ValueError, '無效'):
                read_config(path, 100, 100)


if __name__ == '__main__':
    unittest.main()
