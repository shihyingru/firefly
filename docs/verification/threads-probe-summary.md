# Threads API 可行性探測 — 第二階段摘要 / Threads API Feasibility Probe — Phase 2 Summary

日期 / Date: 2026-09-03
完整輸出 / Full output: [`threads-probe-report.txt`](./threads-probe-report.txt)
性質 / Scope: 唯讀 / read-only。OAuth code 成功換得長效 user token（約 60 天）；token 未寫入 repo，探測完成後已刪除。
The OAuth code was exchanged for a long-lived user token (~60 days); the token was never written under the repo and was deleted after the probe.

探測參數 / Probe inputs: URL `https://www.threads.com/@threadsapi.changelog/post/DT_hJOrDB61`, keyword `台灣`, tag `新聞`.

| 探測 / Probe | HTTP | 關鍵欄位 / Key fields present | 結論 / Conclusion |
|---|---|---|---|
| A. oEmbed | 400 | `error` only. code=10, subcode=4279067, `OAuthException`: "App Does Not Have Sufficient Access Tier" | 目前 app 存取層級不允許 oEmbed / oEmbed is blocked at the app's current access tier. 非權限 scope 問題，是 app tier。 |
| B. GET /{id}（非自有貼文 / not owned） | 400 | `error` only. code=100, subcode=33, `THApiException`: object does not exist / missing permissions | 無法讀取他人貼文的 media 物件 / Cannot read another user's media object by ID. |
| C1. 關鍵字搜尋 / keyword search (`台灣`) | 200 | 無資料 / no data items (`count=0`, `fields=[]`) | 端點可呼叫但回傳空結果 / Endpoint callable, returned zero results. |
| C2. 標籤搜尋 / tag search (`新聞`, `search_mode=TAG`) | 200 | 無資料 / no data items (`count=0`, `fields=[]`) | 端點可呼叫但回傳空結果 / Endpoint callable, returned zero results. |
| D. mentions 輪詢 / mentions polling | 200 | 無資料 / no data items (`count=0`) | 端點可呼叫；測試帳號目前無 mentions / Endpoint callable; test account has no mentions at present. |
| E. 公開網頁（僅參考）/ public page (reference only) | 200 | `og:description` 有 / present（含貼文文字與日期字串）；無 login wall；無 `taken_at` | 公開 HTML 可取得 og 描述文字，但無結構化時間戳 / Public HTML exposes og description text but no structured timestamp. |
| F. Webhook | — | 未測試 / not tested | 需公開 HTTPS 端點與 App Dashboard 訂閱，無法離線驗證 / Needs a public HTTPS endpoint and a dashboard subscription; cannot be verified offline. |

## 觀察 / Observations（僅依據回傳資料 / data only）

- Token 交換流程可用 / The OAuth code → short-lived → long-lived token flow works with the current app credentials.
- A 的錯誤訊息明確指出 app 存取層級不足 / Probe A's error explicitly names insufficient app access tier.
- C1、C2、D 皆為 200 但零筆資料；本次資料無法區分「無符合結果」與「權限/層級導致空回傳」/ C1, C2, D returned 200 with zero items; this run cannot distinguish "no matches" from "empty due to permissions/tier".
- E 的公開網頁未出現登入牆，回傳 574,381 bytes / Probe E's public page returned without a login wall (574,381 bytes).
