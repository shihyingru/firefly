# 隱私權政策(草稿)/ Privacy Policy (draft)

> 文件 13 待辦。本草稿由工程面的資料事實產生;上線前須經法務諮詢。/ Doc-13 to-do. Generated from engineering facts; requires legal review before launch.

## 我們蒐集什麼 / What we collect

| 項目 / Item | 內容 / Detail | 保存 / Retention |
|---|---|---|
| 裝置代號 / Device handle | 隨機產生的不透明代號,伺服器只存其雜湊 / random opaque token, only its hash is stored | 永久(可自助刪除)/ permanent (self-service delete) |
| LINE 代號 / LINE handle | LINE userId 的 HMAC-SHA256;原值不儲存、不可反查 / HMAC of the LINE userId; the raw id is never stored | 同上 / same |
| 投票 / Votes | 代號對卡片的「有幫助/沒幫助」/ helpful or not per card | 永久、匿名;公開資料經 k-匿名化 / permanent, anonymous |
| 查詢計數 / Lookup count | 每個代號的查詢**次數**,不記錄查詢了什麼 / a count only, never which URLs | 永久 / permanent |
| 防濫用 / Abuse control | IP 的雜湊桶,只在 Redis / hashed IP bucket in Redis only | ≤ 24 小時 / ≤ 24 hours |
| 公開貼文快照 / Public post snapshots | 公開貼文文字、公開帳號代號、發文時間 / public text, public handle, post time | 永久(證據性質;可申訴遮蔽)/ permanent (evidence; redaction on appeal) |

## 我們不蒐集什麼 / What we never collect

IP(超過 24 小時)、國籍、真實姓名、聯絡方式、任何平台原始識別碼、閱讀或瀏覽行為(含匿名版)、第三方分析 SDK。
IP beyond 24 hours, nationality, real names, contact details, raw platform identifiers, reading or browsing behaviour (even anonymized), third-party analytics.

## 你的權利 / Your rights

- 刪除:清除裝置代號即斷開與投票的關聯;LINE 使用者封鎖官方帳號後可要求刪除代號。/ Delete: clearing the device token severs the link to votes; LINE users may request handle deletion after blocking the account.
- 申訴:貼文作者可申請遮蔽快照文字(留雜湊與存證指標)。/ Appeal: post authors may request redaction of snapshot text.
- 透明:所有演算法參數、AI 呼叫紀錄、卡片狀態變更皆公開。/ Transparency: all parameters, AI calls and card state changes are public.

## 聯絡 / Contact

（待填 / TBD)
