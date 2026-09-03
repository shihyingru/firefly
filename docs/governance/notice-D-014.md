# 公示:新增資料項「引導期推播代號」/ Public notice: new data item "onboarding push handle"

> 依文件 10「任何新增資料蒐集項目須經公開 PR + 30 天公示」。公示起日:(合併本 PR 之日)。生效:公示期滿且 `line.onboarding_push_enabled` 改為 true 後。
> Per doc 10, any new data-collection item requires a public PR + 30-day notice. Notice starts on the merge date; takes effect after the period ends and `line.onboarding_push_enabled` is set to true.

## 蒐集什麼 / What is collected

LINE userId,以伺服器 Fernet 金鑰加密,只存 Redis。/ The LINE userId, encrypted with a server-side Fernet key, in Redis only.

## 為什麼 / Why

讓新加入的仲裁者在前 3 天每天收到 5 張待仲裁卡,養成習慣;之後改由富選單自取。LINE push 需要 userId;既有的 HMAC 代號無法反查。/ New arbiters receive 5 cards daily for the first 3 days; afterwards they self-serve. LINE push needs the userId; the existing HMAC handle cannot be reversed.

## 邊界 / Boundaries

| 項目 | 承諾 |
|---|---|
| 同意 | 使用者按「好」才登錄;按「不用」或不按皆不登錄 |
| 期限 | TTL = 3 天 + 1 小時;到期自動刪除 |
| 位置 | 只在 Redis;不進 PostgreSQL;不進備份 |
| 刪除 | 封鎖或解除好友即刪;push 失敗即刪 |
| 用途 | 只用於這 3 次推播;不用於任何其他目的 |
| 審計 | 只公開人次總數(onboarding_enrolled、onboarding_push_run);不記個人 |
| 金鑰 | 環境變數 LINE_PUSH_ENC_KEY;輪替寫入 runbook |

## 對應變更 / Related changes

文件 02、07、08、17(D-014);程式 `backend/firefly/bots/line_onboarding.py`;測試 `backend/tests/test_line_onboarding.py`。
