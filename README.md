# Monitor

本機監視器人物區間分析工具。使用 **MOG2 背景差分篩選 + YOLO11s 人物確認**，保留原片時間，輸出人物出現區間與標示影片。以 Windows、Python 3.12、CPU OpenVINO 為目前測試環境。

## 安裝

1. 從這個儲存庫 Clone 或下載 ZIP 並解壓縮。
2. 安裝 [uv](https://docs.astral.sh/uv/getting-started/installation/)。
3. 在專案資料夾開啟 PowerShell，執行：

```powershell
.\setup.ps1
```

安裝會下載 Python、requirements-lock.txt 的套件，以及 Ultralytics 官方 YOLO11s 權重，並轉換成 640 與 960 的 OpenVINO 模型。模型與環境都放在專案內，未包含於儲存庫。安裝需要網路與可用磁碟空間，無須以管理員執行分析。

## 設定分析區域

不同攝影機必須重新設定，儲存庫不包含任何實際場域的設定。

```powershell
.\.venv\Scripts\python.exe configure_roi.py 'C:\Videos\sample.mp4'
```

先拖曳框選 Main ROI，按 Enter 確認；再在 Main ROI 內框選 Person Zone，按 Enter 儲存。Esc 可取消。設定存於本機 `zone_config.json`，不提交到 GitHub。

也可以參考 `zone_config.example.json` 手動建立 `zone_config.json`。範例使用完整 736 × 480 畫面，僅說明格式，不代表適合你的攝影機。

## 分析整部影片

把影片拖曳到 **run_yolo.bat**。視窗會顯示進度、YOLO 檢查次數與預估剩餘時間，完成或失敗後均等待按鍵再關閉。錯誤另存 `last_error.log`。

命令列用法：

```powershell
.\.venv\Scripts\python.exe detect_person_yolo.py 'C:\Videos\sample.mp4' --debug
```

省略 `--debug` 可不輸出標示影片，但仍會產生第一幀預覽與報表。

## 流程

1. PyAV 讀取影格及原始 PTS 時間。
2. 在 Main ROI 上縮小、灰階模糊，使用 MOG2 找出變化。
3. 有變化時啟動 YOLO11s，並回查暫存的前 2 秒。
4. 無動作時每 5 秒補查一次；補查發現人物也會回查。
5. 人物出現時持续辨識；前 2 秒暖機期間也辨識，片尾另補查。
6. 以人物框中心是否位於 Person Zone 判斷。0.5 秒內兩次重疊人物框才成立區間，容忍最多 1 秒短暫漏判。
7. 依原片時間順序輸出。未檢查影格標示 NOT CHECKED，不當成無人證據。

暫存上限 120 幀；高幀率來源可能縮短回查窗口。除錯影片保留全部影格，但使用平均 FPS、不含音訊；變動幀率來源請以畫面上的原片時間與報表為準。

## 參數

| 參數 | 預設 | 用途 |
|---|---|---|
| `--mode` | `hybrid` | `thorough` 可改成逐幀 YOLO 比較 |
| `--confidence` | `0.25` | 人物信心門檻 |
| `--gap` | `1` | 短暫漏判容忍秒數 |
| `--check-interval` | `5` | 無動作定期補查秒數 |
| `--pre-roll` | `2` | 觸發前回查秒數 |
| `--size` | `640` | 支援 640、960 |
| `--backend` | `openvino` | 可改為 `pytorch`，目前兩者都使用 CPU |
| `--start` | `0` | 原片起點秒數 |
| `--seconds` | `0` | 0 表示直到片尾 |
| `--config` | 同目錄 zone_config.json | 區域設定路徑 |

## 結果

每次分析建立新的 `results/影片名稱_執行時間/`：

- `person_intervals.txt`、`person_intervals.csv`：人物區間。
- `detections.csv`：人物框、分數與是否在區域內。
- `frames.csv`：逐幀檢查狀態與原因。
- `run.json`：分析設定、完成狀態、運算次數與耗時。
- `first_frame.jpg`：第一幀預覽。
- `debug.mp4`：指定 `--debug` 時產生。

## 驗證與限制

```powershell
.\.venv\Scripts\python.exe -m unittest discover -p 'test_*.py' -v
```

測試涵蓋區間判斷、ROI、MOG2 變化、定期補查、觸發前回查、停止移動後持續辨識、時間順序與 Windows 啟動檔解析。測試使用合成資料，不需要私人影片。

短暫人物若沒有觸發 MOG2，又落在定期補查之間，仍可能漏判。模型也可能誤判，結果用於協助人工查找，不能證明無人進入。未承諾一小時影片固定在 10～20 分鐘完成；效能取決於硬體、背景變化及人物活動量。

## 隱私、授權與版本

`.gitignore` 排除影片、截圖、分析結果、實際區域設定、模型、本機環境與常見機密檔案。GitHub 私人儲存庫不能取代這些排除規則；請勿使用 `git add -f` 上傳敏感資料。

執行預設使用本機模型、設定 YOLO_OFFLINE 並關閉 Ultralytics sync。這不是網路隔離保證；安裝及模型轉換另有網路／遙測注意事項，詳見 [SECURITY.md](SECURITY.md)。套件與模型仍適用其上游授權，詳見 [THIRD_PARTY.md](THIRD_PARTY.md)。
