# Security and private data

- Do not commit camera footage, debug videos, screenshots, local ROI configuration, outputs, credentials, or model files. Keep them outside Git or in the ignored directories.
- Existing tracked files are not protected by .gitignore. Check `git ls-files` before publishing changes.
- Model files are trusted executable inputs. Setup downloads YOLO11s from the upstream GitHub assets release; vendor signatures or a trusted SHA-256 manifest are not currently verified. Do not substitute unknown checkpoints.
- `requirements-lock.txt` pins the tested environment, but does not contain package hashes and is not a vulnerability audit. Run dependency scanning and review updates before production use.
- Runtime defaults YOLO_OFFLINE=true and sets Ultralytics sync=false. This reduces optional Ultralytics network activity; it is not a firewall or proof of zero outbound traffic. Installation requires network access; OpenVINO conversion dependencies may have separate telemetry settings.
- Run without administrator privileges. Apply operating-system access controls and storage encryption to input and output directories. The application does not encrypt its own results or enforce retention.
- Only accept trusted camera exports. Video decoders process complex untrusted formats; isolate processing if accepting uploads from other people.
- Long videos or continuous motion can consume CPU, memory and disk. There is no per-job time or storage quota. Check free disk space before exporting debug video.
- Keep original footage for human review. A negative detection result is not evidence that nobody entered. This is not an access-control, identity-recognition or intrusion-proof system.
- Do not post credentials or private footage in security reports. Report privately to the repository owner.
