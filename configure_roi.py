"""Interactively select two rectangles without publishing local camera settings."""
import argparse
import json
from pathlib import Path


def select(video, destination):
    import cv2
    cap = cv2.VideoCapture(str(Path(video).resolve()))
    try:
        ok, image = cap.read()
        if not ok:
            raise ValueError('無法讀取影片第一幀。')
    finally:
        cap.release()
    height, width = image.shape[:2]
    try:
        main = tuple(map(int, cv2.selectROI('Main ROI - Enter to confirm, Esc to cancel', image, False)))
        if not main[2] or not main[3]:
            print('已取消，設定未變更。')
            return
        preview = image.copy()
        x, y, w, h = main
        cv2.rectangle(preview, (x, y), (x+w, y+h), (255, 255, 0), 2)
        zone = tuple(map(int, cv2.selectROI('Person Zone - select inside Main ROI', preview, False)))
        if not zone[2] or not zone[3]:
            print('已取消，設定未變更。')
            return
        a, b, c, d = zone
        if not (x <= a and y <= b and a+c <= x+w and b+d <= y+h):
            raise ValueError('Person Zone 必須在 Main ROI 內，原設定未變更。')
        keys = ('x', 'y', 'width', 'height')
        config = dict(video_width=width, video_height=height,
                      main_roi=dict(zip(keys, main)), person_zone=dict(zip(keys, zone)))
        Path(destination).write_text(json.dumps(config, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        print(f'已儲存：{destination}')
    finally:
        cv2.destroyAllWindows()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='設定主要分析區域與人物區域')
    parser.add_argument('video')
    parser.add_argument('--output', default=str(Path(__file__).with_name('zone_config.json')))
    args = parser.parse_args()
    select(args.video, args.output)
