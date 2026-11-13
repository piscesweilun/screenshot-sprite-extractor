# Screenshot Sprite Extractor

用於批次分析截圖、擷取 UI 圖示或「圖示＋文字」、計算共同裁切範圍、透明去背、重新命名及驗證 Sprite frames 的跨模型 Agent Skill。

適用於以下需求：

- 使用者提供 ZIP、7z 或圖片資料夾。
- 只知道目標的大致位置，需要分析精確截取座標。
- 多張圖片必須使用相同尺寸及對齊中心。
- 需要將黑底或其他單色背景轉成透明 PNG。
- 圖片順序代表不同功能、語言或狀態，需要批次重新命名。

## Skill 會先確認

1. 截圖壓縮檔或圖片資料夾的位置。
2. 目標的大致區域，以及座標原點。
3. 使用全批次共同裁切框、分類共同框或逐張緊密裁切。
4. 是否去背及背景顏色。
5. 功能、語言與檔名排列規則。

## 處理流程

1. 解壓並統計圖片數量、尺寸、格式及順序。
2. 產生 contact sheet，檢查長文字、RTL、CJK 及排列異常。
3. 在指定 ROI 內計算每張圖片的前景邊界及共同聯集。
4. 加入安全邊界，回報 `(x, y, width, height)`。
5. 批次裁切、透明去背及重新命名。
6. 驗證圖片數量、尺寸、Alpha、邊界與檔名唯一性。
7. 輸出 PNG 資料夾、ZIP、分析報告與命名對照表。

圖示與文字採用可重現的像素處理，不使用生成式影像重新繪製，避免文字、符號與反鋸齒邊緣變形。

## 需求

- Python 3.9+
- Pillow

```bash
python -m pip install -r requirements.txt
```

處理 `.7z` 時，系統另需安裝 7-Zip 或相容的解壓縮工具。

## 安裝

### Codex

個人層級：

```text
Windows: %USERPROFILE%\.codex\skills\screenshot-sprite-extractor\
macOS/Linux: ~/.codex/skills/screenshot-sprite-extractor/
```

專案層級：

```text
<專案>/.codex/skills/screenshot-sprite-extractor/
```

### Claude Code

```text
個人：~/.claude/skills/screenshot-sprite-extractor/
專案：<專案>/.claude/skills/screenshot-sprite-extractor/
```

### Gemini CLI

```bash
gemini skills install https://github.com/piscesweilun/screenshot-sprite-extractor.git
```

或放置於：

```text
個人：~/.gemini/skills/screenshot-sprite-extractor/
專案：<專案>/.gemini/skills/screenshot-sprite-extractor/
```

安裝後執行：

```text
/skills reload
/skills list
```

### 通用 Agent Skills 路徑

```text
個人：~/.agents/skills/screenshot-sprite-extractor/
專案：<專案>/.agents/skills/screenshot-sprite-extractor/
```

## 使用範例

```text
使用 screenshot-sprite-extractor 處理我提供的截圖壓縮檔。請先詢問我要擷取的大致區域、是否使用共同範圍、是否去背，以及檔名排列規則；確認後輸出透明 PNG、截取座標與驗證結果。
```

Codex 可明確指定 Skill：

```text
使用 $screenshot-sprite-extractor 處理這個截圖壓縮檔。
```

## 隨附工具

詳細指令請參考 [`references/cli.md`](references/cli.md)。

```bash
# 分析共同前景與建議裁切框
python scripts/sprite_extract.py analyze --help

# 裁切、去背及重新命名
python scripts/sprite_extract.py extract --help

# 驗證輸出
python scripts/sprite_extract.py validate --help
```

## 已驗證案例

曾以 `90` 張、每張 `1920×170` 的多語言 UI 截圖測試：

- 正確分析共同前景聯集。
- 正確產生統一 `400×73` 裁切框。
- 成功輸出90張透明 PNG。
- 尺寸及透明四角驗證錯誤為0。

