# Threads API 可行性探測 — 第一階段 / Threads API Feasibility Probe — Phase 1

日期 / Date: 2026-09-03
分支 / Branch: `claude/firefly-project-planning-q24ahc`
性質 / Scope: 唯讀探測（環境變數 + 網路可達性），未呼叫任何需要 token 的端點。
Read-only probe (env vars + reachability). No token-bearing endpoint was called.

## 1. 環境變數 / Environment variables

| 變數 / Variable | 已設定 / Set | 備註 / Note |
|---|---|---|
| `THREADS_APP_ID` | 是 / yes | 前 4 碼 / first 4 chars: `9447`（App ID 為公開資訊 / app ids are public） |
| `THREADS_APP_SECRET` | 是 / yes | 值未顯示 / value not shown |
| `THREADS_USER_TOKEN` | 否 / no | 需經第二階段 OAuth 交換取得 / to be obtained via OAuth exchange in Phase 2 |

## 2. 網路可達性 / Reachability

方法 / Method: `curl -sS -m 15 -o /dev/null -w "%{http_code}" <url>`（15 秒逾時 / 15 s timeout）

| 目標 / Target | HTTP 狀態 / Status | 結論 / Conclusion |
|---|---|---|
| `https://graph.threads.net/v1.0/me` | 400 | 可達 / reachable。400 為預期結果（未帶 access token）/ 400 is expected without an access token. |
| `https://www.threads.com/` | 200 | 可達 / reachable |
| `https://archive.org/wayback/available?url=threads.net` | 429 | 可達但被限流 / reachable but rate-limited by archive.org。非代理阻擋 / not a proxy block. |

三個目標皆穿過代理成功建立連線，無 CONNECT/403 隧道錯誤或逾時。
All three targets connected through the proxy; no CONNECT/403 tunnel failure or timeout.

## 3. 下一步 / Next step

等待 OAuth code 後進行第二階段（token 交換 → oEmbed / media / search / mentions 探測）。
Waiting for an OAuth code before Phase 2 (token exchange → oEmbed / media / search / mentions probes).
