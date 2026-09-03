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
| 17 | [實作決議紀錄](docs/zh-TW/17-實作決議紀錄.md) | 實作階段的設計決議(append-only) |

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

## 快速上手 / Quickstart(Wave 1.1:後端核心 / backend core)

```bash
cp .env.example .env            # 填入密鑰 / fill in secrets
docker compose up --build       # db(pgvector)+ redis + migrate + api + worker
curl localhost:8000/healthz
```

不用 Docker 的本機開發 / Local development without Docker:

```bash
python3 -m venv .venv && .venv/bin/pip install -e "backend[dev]"
export DATABASE_URL=postgresql+asyncpg://postgres@127.0.0.1:5432/firefly REDIS_URL=redis://127.0.0.1:6379/0
(cd backend && ../.venv/bin/alembic upgrade head)
(cd backend && ../.venv/bin/uvicorn firefly.main:app --reload)
```

測試(需本機 PostgreSQL+pgvector 與 Redis)/ Tests (need local PostgreSQL+pgvector and Redis):

```bash
(cd backend && ../.venv/bin/python -m pytest -q)
```

示範資料(走完整 Stage 0-3)/ Demo data (full Stage 0-3):`FIREFLY_EMBEDDER=hash .venv/bin/python scripts/seed_demo.py`

嵌入模型 / Embedding model:正式環境安裝 `pip install -e "backend[ml]"` 後自動使用 multilingual-e5-base;無模型時退回字元 n-gram 雜湊嵌入,並記錄於叢集 signal_summary.embedder。/ Production installs the `ml` extra and uses multilingual-e5-base; without it the pipeline falls back to hashed char n-grams and records that in the cluster's signal_summary.

| 路徑 / Path | 內容 / What |
|---|---|
| `config/firefly.yaml` | 所有可調參數(θ_join、θ_helpful、K、N_min、λ…),版本化、公開 / all tunables, versioned |
| `backend/firefly/models.py` | 文件 08 資料模型 / doc-08 data model |
| `backend/firefly/api/routes.py` | 文件 06 端點 / doc-06 endpoints |
| `backend/tests/test_privacy_guard.py` | 「明確不存」守衛 / never-stored guard |
| `backend/firefly/bots/line.py` | LINE Bot webhook(文件 7.1)/ LINE bot webhook |
| `backend/firefly/bots/threads.py` | Threads Bot:webhook + mentions 輪詢 + 發文 log(文件 7.2)/ Threads bot |
| `backend/firefly/api/pages.py` | 卡片網頁(投票落點)/ card web page |
| `docs/app-review/`、`docs/legal/` | Meta App Review 材料與隱私權政策草稿 / review materials, privacy draft |
| `backend/firefly/pipeline/` | Stage 0-3:adapters、stage1_fingerprint、stage2_cluster、stage3_card、card_schema、llm、ingest |
| `backend/tests/data/injection_corpus.jsonl` | 文件 14 T5 注入迴歸語料(中/英/日/混淆)/ injection corpus |
| `config/fingerprint_rules.yaml`、`config/domain_signals.yaml` | 排版規則庫、網域訊號種子 / rule library, domain seeds |
| `docs/zh-TW/17-實作決議紀錄.md` | 實作決議 D-001… / decision record |

## Status

Wave 1 in progress: 1.1 backend core, 1.2 AI pipeline, 1.3 LINE bot, 1.4 Threads bot done; 1.5 bridging engine next. See doc 16 for the handoff prompt and doc 17 for decisions.

## License

Code: AGPL-3.0. Output data (context cards, signals): CC BY 4.0.
