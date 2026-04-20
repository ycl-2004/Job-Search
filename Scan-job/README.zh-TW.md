# Scan-job

[English](README.md) | [繁體中文](README.zh-TW.md)

這個資料夾現在主要是 `Job Searching/cli.py` 裡 Task 5 工作流的本地支援層。

你可以把它理解成：

- 掃描職缺的腳本放這裡
- tracker / pipeline / reports / outputs 的資料放這裡
- HTML 模板、PDF 轉檔、dashboard 與 maintenance 工具放這裡
- 真正給你操作的入口，還是在主專案的 Task 5 terminal menu

## 現在真正重要的是什麼

目前本地流程大致是：

1. 設定 `cv.md`、`config/profile.yml`、`portals.yml`
2. 從主專案進入 Task 5，做 scan / process / status / outputs
3. 讓這個資料夾負責保存 `reports/`、`output/`、`jds/`、`data/`
4. 只有在需要檢查或維護時，才直接跑這裡的 `.mjs` scripts

## 快速開始

```bash
cd "Job Searching/Scan-job"
npm install
npx playwright install chromium
npm run doctor
```

必要個人檔案：

- `cv.md`
- `config/profile.yml`
- `portals.yml`

選填但很有幫助：

- `article-digest.md`
- `modes/_profile.md`
- `interview-prep/story-bank.md`

## 主要指令

| 指令 | 用途 |
|------|------|
| `npm run doctor` | 檢查本地環境是否齊全 |
| `npm run scan` | 直接跑原始 portal scanner |
| `npm run pdf -- input.html output.pdf` | 把 HTML 履歷轉成 PDF |
| `npm run verify` | 檢查 tracker 一致性 |
| `npm run clean-pipeline` | 重整 pipeline layout |
| `npm run normalize` | 標準化 tracker 狀態 |
| `npm run dedup` | 去除 tracker 重複項 |
| `npm run merge` | 合併 batch tracker additions |

詳細說明看 `docs/SCRIPTS.md`。

## 目錄重點

```text
Scan-job/
├── cv.md
├── article-digest.md
├── config/
├── interview-prep/
├── data/
├── reports/
├── output/
├── jds/
├── templates/
├── fonts/
├── dashboard/
├── modes/_profile.md
└── *.mjs
```

## 哪些地方可以改，哪些不要亂放

- 個人事實、求職偏好、targeting 設定放在 `cv.md`、
  `config/profile.yml`、`article-digest.md`、`portals.yml`、`interview-prep/*`、`data/*`
- 共用邏輯放在 scripts、templates、dashboard
- `modes/_profile.md` 只保留你自己的 framing / tailoring 筆記

延伸閱讀：

- `DATA_CONTRACT.md`
- `docs/CUSTOMIZATION.md`
- `docs/SCRIPTS.md`
