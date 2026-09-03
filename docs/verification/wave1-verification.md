# Wave 1 驗證步驟 / Wave 1 verification steps

> 每個模組「如何驗證它正常運作」。所有步驟可在單機完成,不需要任何平台憑證(有憑證的步驟另標)。
> How to verify each module. Everything runs on one machine without platform credentials (credentialed steps are marked).

## 0. 準備 / Setup

```bash
python3 -m venv .venv && .venv/bin/pip install -e "backend[dev]"
# PostgreSQL 16 + pgvector 與 Redis 已在本機執行;或改用 docker compose up db redis
export DATABASE_URL=postgresql+asyncpg://postgres@127.0.0.1:5432/firefly REDIS_URL=redis://127.0.0.1:6379/0
export FIREFLY_INLINE_JOBS=1 FIREFLY_SOURCE_ADAPTER=mock FIREFLY_EMBEDDER=hash
(cd backend && ../.venv/bin/alembic upgrade head)
(cd backend && ../.venv/bin/python -m pytest -q)        # 期望 / expect: 69 passed
(cd backend && ../.venv/bin/uvicorn firefly.main:app --port 8000 &)
```

## 1.1 後端核心 / Backend core

1. `curl localhost:8000/healthz` → `{"ok":true,...}`。
2. `curl -X POST localhost:8000/v1/devices -H 'content-type: application/json' -d '{}'` → `device_token`。
3. `curl -i -X POST localhost:8000/v1/lookup -d '{"url":"https://www.threads.com/@x/post/NOPE"}' -H 'content-type: application/json'` → 第一次 202 processing,第二次 422 unfetchable(mock adapter 查無此貼文)。
4. 隱私守衛:`pytest -q tests/test_privacy_guard.py` → 資料模型無 IP/國籍/真實身分/原始識別碼欄位。
5. 速率限制:連續呼叫 61 次 `/v1/devices` → 第 61 次 429 且帶 `Retry-After`。

## 1.2 AI 管線 / AI pipeline

1. `.venv/bin/python scripts/seed_demo.py` → 印出三則貼文的處理結果(isolated, isolated, formed)與 card_id。
2. `curl -X POST localhost:8000/v1/lookup -d '{"url":"https://www.threads.com/@demo_a/post/DEMO0001"}' -H 'content-type: application/json'` → `status: candidate`,`fields` 恰為七個白名單欄位,`account_count: 3`,`timing_chart` 三筆,`sample_excerpt` 為逐字節錄。
3. `curl localhost:8000/v1/open/audit-log` → 可見 `fetched`、`formed`、`state_changed(draft→candidate)` 事件。
4. 注入迴歸:`pytest -q tests/test_injection_regression.py` → 15 個語料(中/英/日/base64/全形/零寬/同形字/HTML/JSON)全部通過;模擬被注入的 LLM 輸出皆被驗證擋下。
5. 白名單驗證:`pytest -q tests/test_card_validation.py`。
6. 正式嵌入模型(選用):`pip install -e "backend[ml]"` 並移除 `FIREFLY_EMBEDDER=hash` → 叢集 `signal_summary.embedder` 顯示 `e5:intfloat/multilingual-e5-base`。

## 1.3 LINE Bot

1. 設定 `.env` 的 `LINE_CHANNEL_SECRET`、`LINE_CHANNEL_ACCESS_TOKEN`、`LINE_ID_HMAC_KEY`;以 ngrok 之類把 `https://<host>/v1/line/webhook` 填入 LINE Developers 的 Webhook URL,按「Verify」→ 200。
2. 加官方帳號好友 → 收到歡迎訊息。
3. 貼上 `https://www.threads.com/@demo_a/post/DEMO0001`(seed_demo 產生)→ 收到 Flex 脈絡卡;按「有幫助」→ 收到感謝語。
4. 資料庫檢查:`psql -c "select origin, left(origin_key_hash,8), lookup_count from contributor"` → origin=line_hash;整個資料庫找不到你的 LINE userId(`pytest -q tests/test_line_bot.py::test_raw_line_user_id_never_stored`)。
5. 未知貼文 → 「處理中」訊息 + 「再查一次」按鈕;再按一次 → 查無訊號/卡片。

## 1.4 Threads Bot(需 Meta app;真實資料需 App Review)

1. Webhook 驗證:`curl "localhost:8000/v1/threads/webhook?hub.mode=subscribe&hub.verify_token=$THREADS_WEBHOOK_VERIFY_TOKEN&hub.challenge=123"` → `123`。
2. 簽章:`pytest -q tests/test_threads_bot.py`(含 X-Hub-Signature-256 驗證、額度上限、發文 log)。
3. 輪詢路線(需 user token):設 `config/firefly.yaml` `threads.enabled: true`,`python -m firefly.cli poll-mentions` → 輸出各結果代碼計數;`/v1/open/audit-log` 出現 `threads_reply`。
4. 部署後在 App Dashboard 訂閱 `mentions` 指向 `https://<host>/v1/threads/webhook`,用另一帳號 @ 測試帳號 → 觀察 `handled` 計數;若 24 小時內 webhook 未到而輪詢有到,以輪詢為主路線(文件 7.2 決定點)。
5. 卡片網頁:瀏覽器開 `http://localhost:8000/cards/<card_id>` → 顯示欄位與投票按鈕;投票後顯示感謝語。

## 1.5 橋接引擎 / Bridging engine

1. 模擬資料:`pytest -q tests/test_bridging.py` → 橋接卡 i_c > θ_helpful > 陣營卡;陣營分離;300 個養號灌票增益次線性且塌縮同號;Phase A 不裁決;Phase B 顯示與遲滯;突發灌票降權。
2. 實際重算:`python -m firefly.cli recompute` → 印出 `{"phase": "A", "apply_display": false, ...}`;`/v1/open/audit-log` 出現 `recompute` 事件;卡片 `arbitration.i_c` 有值但 state 維持 candidate。
3. 參數同源:`config/firefly.yaml` 的 `theta_helpful`、`lambda_intercept`、`lambda_factor`、`n_min_votes`、`min_votes_per_rater` 皆為 TODO(calibrate);state_changed 事件 payload 記錄當次使用的 θ 與 λ。

## 全容器化 / Containers

`cp .env.example .env && docker compose up --build` → db、redis、migrate、api、worker、scheduler 六個服務;`curl localhost:8000/healthz`。

## 1.3b LINE 引導期推播與自取(D-014)

1. 產生金鑰:`python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())"` → 填入 `.env` 的 `LINE_PUSH_ENC_KEY`。
2. `pytest -q tests/test_line_onboarding.py` → 第 0 天 reply、同意後只有加密值進 Redis、三天推播後刪除、封鎖即刪、每日上限、旗標關閉時無邀請。
3. 富選單:LINE Official Account Manager → 聊天室相關 → 圖文選單 → 新增按鈕,動作類型「Postback」,資料填 `queue:today`,顯示文字「今日佇列」。
4. 手動觸發推播(需 `line.onboarding_push_enabled: true` 且已同意):`python -m firefly.cli line-onboarding-push --force`。
5. 隱私守衛:`redis-cli --scan --pattern 'line:onboard:*'` 只看到加密字串;`psql -c "select count(*) from contributor where origin_key_hash like 'U%'"` 為 0。
