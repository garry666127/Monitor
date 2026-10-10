"""Local model loading; all paths are relative to the cloned project."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / '.yolo'
CONFIG.mkdir(exist_ok=True)
os.environ['YOLO_CONFIG_DIR'] = str(CONFIG)
os.environ.setdefault('YOLO_OFFLINE', 'true')


def load_model(size, backend, model_name='yolo11s'):
    import torch
    from ultralytics import YOLO, settings
    settings.update({'sync': False})
    if size not in (640, 960) or backend not in ('openvino', 'pytorch'):
        raise ValueError('不支援的辨識尺寸或引擎。')
    if model_name != 'yolo11s':
        raise ValueError('本工具使用 YOLO11s。')
    torch.set_num_threads(min(4, os.cpu_count() or 4))
    path = ROOT/'models'/(f'{model_name}_{size}_openvino_model' if backend == 'openvino' else f'{model_name}.pt')
    if not path.exists():
        raise ValueError('找不到本機模型。請先執行 setup.ps1。')
    return YOLO(str(path), task='detect')
