"""Convert the explicitly downloaded trusted model for local CPU inference."""
import shutil
from runtime import ROOT, load_model


def main():
    for size in (640, 960):
        target = ROOT/'models'/f'yolo11s_{size}_openvino_model'
        if (target/'metadata.yaml').exists() and list(target.glob('*.bin')) and list(target.glob('*.xml')):
            print(f'Already prepared: {target}', flush=True)
            continue
        if target.exists():
            raise RuntimeError(f'Incomplete model directory: {target}. Rename it and retry.')
        model = load_model(size, 'pytorch')
        exported = model.export(format='openvino', imgsz=size, dynamic=False, device='cpu')
        shutil.move(str(exported), str(target))
        print(f'Prepared: {target}', flush=True)


if __name__ == '__main__':
    main()
