# Threads App Review 申請材料草稿 / Threads App Review submission draft

> 狀態:草稿(D-003)。實測(2026-09-03)確認 oEmbed、keyword_search、TAG search 在審核前皆無真實資料。
> Status: draft (D-003). Verified 2026-09-03: oEmbed, keyword_search and TAG search return no real data before review.

## 申請項目 / Items to request

| 項目 / Item | 用途 / Purpose | 端點 / Endpoint |
|---|---|---|
| Threads oEmbed Read(功能 / feature) | 使用者提交單一公開貼文網址時讀取文字與作者 / read text + author of a single public post a user submits | `GET /oembed` |
| `threads_keyword_search` | 找出發布相同或近似內容的其他公開貼文(叢集養成)/ find other public posts with the same content | `GET /keyword_search` |
| `threads_manage_mentions` | 讀取 @ 提及以回覆脈絡卡 / read mentions to reply with a context card | `GET /me/mentions`, webhook `mentions` |
| `threads_manage_replies` + `threads_content_publish` | 在提及的貼文下公開回覆 / publicly reply under the mentioning post | `POST /me/threads`, `POST /me/threads_publish` |

## 使用情境說明(送審用)/ Use-case description (for the submission)

**繁中**
螢火(Firefly)是一個開源(AGPL-3.0)的媒體識讀工具。使用者在 Threads 上提及 @firefly_tw 並附上一則公開貼文的連結,或透過 LINE 傳送連結,系統回覆一張「脈絡卡」:該內容最早出現的時間、可追溯的原始出處、發布相同或近似內容的帳號數、快照連結。系統不判定內容真假、不評論立場、不標記任何個人;只呈現機器可驗證的事實欄位。所有演算法、參數與 AI 呼叫紀錄公開;不儲存 IP、國籍、真實身分或平台原始識別碼。Threads 資料只透過官方 API 取得,且只取公開貼文;所有自動回覆皆公開留存發文紀錄。

**English**
Firefly is an open-source (AGPL-3.0) media-literacy tool. When a user mentions @firefly_tw on Threads with a link to a public post, or sends the link via LINE, the system replies with a "context card": the earliest time the content appeared, its traceable origin, the number of accounts that posted identical or near-identical content, and archive links. The system never judges truth, comments on stance, or labels individuals; it shows machine-verifiable fields only. Algorithms, parameters and every AI call are public; no IP, nationality, real identity or raw platform identifier is stored. Threads data is obtained only through the official API and only for public posts; every automated reply is kept in a public posting log.

## 審核者測試步驟 / Reviewer test instructions

1. 以測試帳號在任一公開貼文下回覆「@firefly_tw https://www.threads.com/@<user>/post/<id>」。
2. 系統於一分鐘內回覆脈絡卡摘要與卡片頁連結(`https://<host>/cards/<id>`)。
3. 卡片頁可匿名投「有幫助/沒幫助」。
4. 發文紀錄可於 `https://<host>/v1/open/audit-log` 查閱(event=threads_reply)。

## 送審 checklist(文件 7.2)/ Submission checklist

- [ ] App 切到上線模式 / App in Live mode
- [ ] 隱私權政策網址(見 `docs/legal/privacy-policy-draft.md` 上線版)/ Privacy policy URL
- [ ] 資料刪除說明網址 / Data deletion instructions URL
- [ ] 示範影片:提及 → 回覆 → 卡片頁投票(≤ 3 分鐘,顯示 App 名稱)/ Demo video
- [ ] 官方帳號 @firefly_tw 簡介明寫「自動回覆機器人|開源|發文紀錄公開」/ bio disclosure
- [ ] Webhook 端點 `https://<host>/v1/threads/webhook` 已可回應驗證(GET hub.challenge)/ webhook verification reachable
- [ ] 回覆上限與 feature flag 已設定(config `threads.*`)/ caps and kill switch configured
