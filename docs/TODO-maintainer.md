# 維護者待辦 / Maintainer TODO

> 更新:2026-09-03。Wave 1(1.1–1.5)與 D-014 已實作於分支 `claude/firefly-project-planning-q24ahc`。
> 本清單只列「需要維護者本人動手」與「需要維護者決定」的事項。工程細節見 `docs/verification/wave1-verification.md`。

## A. 需要你動手(帳號、憑證、部署)

### A1. 上線前必做
- [ ] **合併分支**:開 PR 把 `claude/firefly-project-planning-q24ahc` 併入 `main`;GitHub Actions CI 會跑 75 個測試。
- [ ] **產生密鑰**填入 `.env`(每個都獨立隨機,32 bytes 以上):`DEVICE_TOKEN_PEPPER`、`LINE_ID_HMAC_KEY`、`SERVICE_TOKEN`、`THREADS_WEBHOOK_VERIFY_TOKEN`、`LINE_PUSH_ENC_KEY`(Fernet,指令在驗證文件 1.3b)。
- [ ] **VPS 部署**:網域、HTTPS 憑證、`PUBLIC_BASE_URL`;`docker compose up --build`;`curl /healthz`。
- [ ] **嵌入模型**:`pip install -e "backend[ml]"`(或在 Dockerfile 加入),確認叢集 `signal_summary.embedder` 顯示 `e5:intfloat/multilingual-e5-base`。
- [ ] **LINE 官方帳號**:建立 Messaging API channel → `LINE_CHANNEL_SECRET`、`LINE_CHANNEL_ACCESS_TOKEN` → Webhook URL `https://<host>/v1/line/webhook` 按 Verify → 富選單按鈕 postback `queue:today`(顯示文字「今日佇列」)。
- [ ] **網域訊號種子**:把 A/B 級來源(如 Doublethink Lab 報告)的網域填入 `config/domain_signals.yaml`,執行 `python -m firefly.cli seed-domains`。
- [ ] **隱私權政策定稿**:以 `docs/legal/privacy-policy-draft.md` 為底,填聯絡方式,安排法務諮詢(文件 13),公開網址。

### A2. Threads(受 Meta 審核時程影響)
- [ ] 註冊官方帳號 **@firefly_tw**,簡介寫「自動回覆機器人|開源|發文紀錄公開」。
- [ ] **App Review 送審**:app 切上線模式;隱私權政策網址;資料刪除說明網址;示範影片(提及 → 回覆 → 卡片頁投票,≤ 3 分鐘);送審 oEmbed Read、`threads_keyword_search`、`threads_manage_mentions`、`threads_manage_replies` + `threads_content_publish`。材料:`docs/app-review/threads-app-review.md`。
- [ ] 審核通過後:取得長效 user token 填 `THREADS_USER_TOKEN`;`config/firefly.yaml` 的 `threads.enabled` 改 true。
- [ ] **驗證 mention webhook**:App Dashboard 訂閱 `mentions` 指向 `https://<host>/v1/threads/webhook`;用另一帳號 @ 測試帳號;觀察 24 小時。結果決定 B3。
- [ ] 填 `ingestion.tags` 標籤清單(攝入策略 B)。

### A3. 治理與資料
- [ ] **30 天公示**:把 `docs/governance/notice-D-014.md` 以公開 PR 發布。期滿前 `line.onboarding_push_enabled` 維持 false。
- [ ] **Wayback 存證**:申請 archive.org S3 keys 填 `WAYBACK_ACCESS_KEY` / `WAYBACK_SECRET_KEY`,實測 Threads 頁面存檔效果後再開 `stage0.archive_enabled`。
- [ ] **備份**:決定異地位置;設定每日加密備份與每季還原演練(文件 08)。

## B. 需要你決定

| # | 事項 | 目前狀態 | 我的建議 |
|---|---|---|---|
| B1 | 校準參數:θ_join、K、θ_helpful + λ_i + λ_f、N_min、min_votes_per_rater、MIN_COVERAGE、資格門檻(min_lookups、min_account_age_hours)、sync_window_minutes、burst_zscore_threshold | 皆為初始值,標 TODO(calibrate) | 上線後累積 2 週真實資料,再以審計 log 回放校準;每次變更走公開 PR |
| B2 | LLM 步驟是否啟用(`card.llm_enabled`)與模型 | 關閉。啟用需 `ANTHROPIC_API_KEY` | 維持關閉,直到出現「original_source 追溯失敗」的實際案例 |
| B3 | Threads Bot 主路線:即時 webhook 或 5 分鐘輪詢 | 兩條路線都已實作 | 依 A2 實測結果決定;webhook 未到就以輪詢為主 |
| B4 | Redis 是否持久化 | 目前不落地。重啟會清掉引導期名單、額度計數器、快取 | 維持不落地。隱私加分,損失可接受 |
| B5 | Phase A → B 切換門檻(`phase_a_max_active_arbiters` = 100) | 初始值 | 維持,並在儀表板公開目前活躍仲裁者數 |
| B6 | 開放資料 k-匿名化的 k 值與季度發布流程(文件 05、12) | 未實作 | Wave 2 實作;k 初始 5 |
| B7 | 網域與品牌:API 網域、卡片頁網域 | 文件 06 寫「待定」 | 先決定,`PUBLIC_BASE_URL` 與隱私政策都要用 |
| B8 | Wave 2 排序 | 未開始 | 建議順序:透明儀表板與開放資料 → 分享目標 App(Android)→ 仲裁佇列分頁 → B2B 端點 |
| B9 | 財務紀錄匯入方式(`finance_record`;金流平台選擇,文件 11) | 表已建,無資料 | 先手動 CSV 匯入,Phase 1 再接金流 |

## C. 可以交給我的下一批工作(等你指示)

- 透明儀表板(文件 12)與開放資料端點補齊(`/open/finance`、k-匿名投票矩陣匯出)。
- Runbook:緊急下線、備份還原、灌票事件處置、金鑰輪替、法律索資應對(文件 14 清單)。
- Dockerfile 加入 e5 模型與 `ml` extra;CI 加 e5 煙霧測試(選用)。
- 校準工具:從 audit log 回放,產出 θ_join / θ_helpful 的靈敏度報告。
- Wave 2 各項(依 B8 決定的順序)。

## D. 交接給其他模型 / Hand-off prompt for a new session

A 段是人工作業,不需要模型。B 段是你的決定,任何模型都只能提供建議。C 段可交給較省用量的模型。建議:runbook、儀表板、Dockerfile、文件更新用 Sonnet;橋接校準工具與 Wave 2 App 架構用 Opus。

新工作階段的起始 prompt(複製即可):

```
你是「螢火 Firefly」專案的實作工程師。先完整閱讀 docs/zh-TW/01-專案概述-v2.md,
再讀 docs/zh-TW/17-實作決議紀錄.md(所有已定案決議,不得推翻)、docs/TODO-maintainer.md、
docs/verification/wave1-verification.md。硬約束見文件 04、08、10、14;遇實作困難停下回報,不得自行變通。
Wave 1 已完成於 backend/(75 個測試,cd backend && pytest -q 必須全綠)。
本次任務:<填入 C 段的一項>。完成後附驗證步驟,程式註解雙語,commit 訊息不含模型名稱。
```
