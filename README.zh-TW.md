# Scan-job Task 5 整合說明

這個資料夾是 `Daily_Task` 裡專門給 `Scan-job` 用的隔離區。

## 目標

- 把 `Scan-job` 當成 `Daily_Task` 裡的另一個 task 來接。
- 不影響既有 `Task 1 / Task 2 / Task 3 / Task SNR` 的資料夾與執行方式。
- 所有跟 `Scan-job` 有關的 clone、設定、輸出、客製化，都盡量留在 `Job Searching/` 下面。
- 以繁體中文做為這個整合層的預設說明語言。

## 建議目錄結構

```text
Daily_Task/
├── Job Searching/
│   ├── cli.py
│   ├── README.zh-TW.md
│   └── Scan-job/                # 本地 project workspace（來源仍是 Career-Ops upstream）
│       ├── config/
│       ├── docs/
│       ├── modes/
│       ├── reports/
│       ├── output/
│       └── ...
├── task
├── task_command.py
└── ...
```

## 為什麼這樣接

這樣做有三個好處：

1. `Daily_Task` 外層只需要新增 `Task 5` 路由，改動面很小。
2. `Career-Ops` 上游 repo 仍然可以作為來源參考，未來要更新、回滾、比對 upstream 都比較容易。
3. 之後如果你決定不要這個 task，只要移除 `Job Searching/` 和一小段路由即可。

## 第一次接入建議流程

1. 在 `Daily_Task` 根目錄執行 `task 5 status`
2. 執行 `task 5 bootstrap --install`
3. 執行 `task 5 doctor`
4. 依照 doctor 提示補齊這些檔案：
   - `Job Searching/Scan-job/cv.md`
   - `Job Searching/Scan-job/config/profile.yml`
   - `Job Searching/Scan-job/portals.yml`
5. 如果你要用 dashboard，再進 `Job Searching/Scan-job/dashboard/` build Go TUI

## 繁體中文策略

目前這一層先做兩件事：

1. `Task 5` 的本地入口與說明都用繁體中文。
2. `Career-Ops` upstream 來源內的 `modes/` 維持英文，避免額外維護一套繁中 mode 分支。

這樣的好處是：

1. 你平常使用 `Task 5` 時，外層操作與說明仍然可以是繁體中文。
2. 核心 prompt 與 mode routing 直接貼齊 upstream，減少和官方流程漂移。
3. 未來如果要更新上游 `career-ops`，不用再手動合併一套繁中 `modes/`。

換句話說，語言分工會是：

- `Daily_Task` 的 `Task 5` 入口：繁體中文
- `Job Searching/README.zh-TW.md` 與操作說明：繁體中文
- `Job Searching/Scan-job/modes/*.md`：英文
- 你給 Codex/terminal agent 的操作指令：可以用繁體中文，但需要遵守英文 `modes/` 的結構與語意

## 建議的繁中使用方式

如果你之後在 `Job Searching/Scan-job/` 裡直接開 Codex，建議第一句就這樣說：

```text
請以繁體中文和我協作，但保留 Career-Ops 的 modes/ 為英文；沿用既有腳本與流程，只有在必要時才修改上游檔案。
```

如果你想讓它更偏向 `Daily_Task` 的操作習慣，可以再補一段：

```text
請把這個 repo 視為 Daily_Task 的 Task 5，所有本地資料與輸出都留在 Job Searching/Scan-job 下面，不要外溢到其他 task。
```

## 目前這層的主工作流

現在 `Task 5` 的主入口不再偏向 repo 維護，而是偏向每天實際會用的工作台：

1. `task 5 scan`
   - 掃描新職缺
   - 更新 `data/pipeline.md`
   - 更新 `data/scan-runs/YYYY-MM-DD.md`（每天一份、每次 scan 一段）
   - 更新 `data/latest-scan-run.json`（給 status / dashboard 讀最新摘要）
   - 維護 `data/scan-history.tsv`（機器用 dedup 歷史）
2. `task 5 process`
   - 處理最上面的待辦職缺
   - 產生 `reports/*.md`
   - 產生 `output/*.html` / `output/*.pdf`
   - 更新 `data/applications.md`
   - 更新 `data/job-dashboard.md`
   - 把該筆從 `Pendientes` 移到 `Procesadas`
3. `task 5 pipeline`
   - 看 pending / processed / latest scan 摘要
4. `task 5 outputs`
   - 看最新 report、HTML、PDF、每日 scan log 與 tracker 路徑
5. `task 5 maintenance`
   - 進入維護 / 診斷子選單
6. `task 5 dashboard`
   - 產生並顯示整合總表
   - 用一個 Markdown 檔案集中列出 processed / pending / reports / PDF / tracker links

如果你直接輸入 `task 5`，看到的也會是同樣的 workflow 導向主選單。
而且現在會持續留在這個 workflow 裡，讓你可以連續選下一個動作；只有按 `q` 才會退出回到 `Daily_Task`。

另外 `task 5 scan` 在加入新職缺前，會同時參考 `data/pipeline.md` 與 `data/applications.md` 做 dedup，避免已經在 pending / processed / tracker 裡的同公司同職位反覆被加回來。
如果你想把既有的 `pipeline.md` 也整理乾淨，直接跑 `task 5 clean` 就會用最新 layout 重寫並去掉舊重複；這個動作也會出現在主選單和 maintenance 子選單裡。

## 維護與診斷功能

原本的維護動作還在，但都收進 maintenance 心智模型裡：

- `task 5 status`
- `task 5 paths`
- `task 5 bootstrap --install`
- `task 5 doctor`
- `task 5 verify`
- `task 5 pdf`
- `task 5 guide`

## 為什麼用 Markdown dashboard

`Task 5` 的輸出本來就分散在 `reports/`、`output/`、`data/applications.md`、`data/pipeline.md`。
所以這一層另外加了一個 `data/job-dashboard.md` 當作總覽入口，原因是：

- `Markdown` 比 `.txt` 更適合本地 dashboard
- 可以保留 table 結構
- 可以直接放相對連結到 report / HTML / PDF / tracker
- 之後就不用一個資料夾一個資料夾翻

## 目前這層的邊界

- `Scan-job` 本地 workspace 裡的 `cv.md`、`config/profile.yml`、`portals.yml`、`article-digest.md` 都集中在 `Job Searching/Scan-job` 下面管理
- 不打算把 upstream `modes/*.md` 全面翻成繁中，會維持英文 mode prompt，相容 Codex / terminal 工作流
- 這層主打的是本地 workflow orchestration，不是去改寫 upstream 的整套 agent 架構
- `AI_CLI=codex|claude|qwen` 這類 provider abstraction 仍然是後續擴充，不是這一版 Task 5 的目標
- `batch` 那層目前也還沒有完全從 `claude -p` 抽離，所以日常使用仍建議以 `scan / process / pipeline / outputs` 這條線為主

所以這一版現在的定位是：

- 把 `Task 5` 做成比較像 job ops workspace 的本地工作台
- 讓主選單對齊你的日常流程，而不是只對齊 repo 維護
- 保留 upstream `Career-Ops` 的來源相容性，同時把本地 project 名稱統一成 `Scan-job`
