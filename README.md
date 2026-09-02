# 螢火 Firefly

> 開源媒體識讀基礎設施 — Open-source media literacy infrastructure
> 授權 License: AGPL-3.0 | 狀態 Status: 設計階段 Design phase (v0.1)

---

## 繁體中文

AI 偵測協同性造假行為並起草「脈絡卡」,人類一鍵仲裁,橋接演算法決定是否顯示。

**核心理念:AI 是書記官,人類是仲裁官。**

- 不判定真假、不評論立場——只讓不可見的協同行為變可見
- 脈絡卡僅呈現機器可驗證欄位:原始出處、最早出現時間、同文帳號數、快照連結
- 橋接演算法(Community Notes / Polis 同源)過濾同溫層噪音:只有跨立場使用者都認可的卡片才顯示
- 系統全透明,使用者全隱私

台灣為第一個實踐場域,架構自始為跨語言、跨國界設計。

### 文件

| # | 文件 | 說明 |
|---|---|---|
| 01 | [專案概述](docs/zh-TW/01-專案概述-v2.md) | **先讀這份** — 所有設計決策的「為什麼」 |
| 02 | [使用者旅程與 UX 流程](docs/zh-TW/02-使用者旅程與UX流程.md) | |
| 03 | [系統架構](docs/zh-TW/03-系統架構文件.md) | |
| 04 | [AI 管線規格](docs/zh-TW/04-AI管線規格.md) | 含欄位白名單與防幻覺設計 |
| 05 | [橋接計分引擎規格](docs/zh-TW/05-橋接計分引擎規格.md) | |
| 06 | [API 規格](docs/zh-TW/06-API規格.md) | |
| 07 | [客戶端技術規格](docs/zh-TW/07-客戶端技術規格.md) | |
| 08 | [資料模型](docs/zh-TW/08-資料模型.md) | 含蒐集邊界三原則 |
| 09 | [資料來源與引用政策](docs/zh-TW/09-資料來源與引用政策.md) | |
| 10 | [治理章程](docs/zh-TW/10-治理章程.md) | 中立性的可驗證承諾 |
| 11 | [營運成本與資金模型](docs/zh-TW/11-營運成本與資金模型.md) | |
| 12 | [透明公開規範](docs/zh-TW/12-透明公開規範.md) | |
| 13 | [隱私與法遵評估](docs/zh-TW/13-隱私與法遵評估.md) | |
| 14 | [風險與威脅模型](docs/zh-TW/14-風險與威脅模型.md) | |
| 15 | [行銷與內容自動化準則](docs/zh-TW/15-行銷與內容自動化準則.md) | |
| 16 | [Claude Code 交付 Prompt](docs/16-claude-code-handoff-prompt.md) | 實作起點 |

### 硬約束

實作時遇困難請停下討論,不得自行變通:

- **欄位白名單**(04):AI 輸出不得含任何立場推論或意圖歸因
- **蒐集邊界**(08):不存 IP、國籍、原始平台識別碼、真實身分;禁止被動閱讀追蹤(含匿名版)
- **徽章邊界**(10):無排行榜、無「高等級使用者觀點」放大
- **失效模式**(14):系統失效時沉默,永不說謊

---

## English

AI detects coordinated inauthentic behavior and drafts "context cards"; humans arbitrate with one tap; a bridging algorithm decides display.

**Core idea: the AI is a clerk, humans are the arbiters.**

- No verdicts on truth, no commentary on stance — we only make invisible coordinated behavior visible
- Context cards contain machine-verifiable fields only: original source, first-seen time, same-content account count, archive links
- A bridging algorithm (same lineage as Community Notes / Polis) filters echo-chamber noise: only cards found helpful across the opinion spectrum are displayed
- Total system transparency, total user privacy

Taiwan is the first deployment ground; the architecture is cross-language and cross-border by design.

### Documentation

Start with [01 Project Overview](docs/en/01-project-overview-v2.en.md). Full set in [`docs/en/`](docs/en/).

### Hard Constraints

Stop and discuss rather than working around:

- **Field whitelist** (04): no stance inference or intent attribution in AI output
- **Collection boundaries** (08): no IP, nationality, raw platform IDs, or real identity stored; passive reading tracking prohibited even anonymized
- **Badge boundaries** (10): no leaderboards, no amplification of "high-tier users' views"
- **Failure modes** (14): the system fails silent, never lies

---

## Status

Design phase. Implementation has not started. See doc 16 for the implementation handoff prompt.

## License

Code: AGPL-3.0. Output data (context cards, signals): CC BY 4.0.
