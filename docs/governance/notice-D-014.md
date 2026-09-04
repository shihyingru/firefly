# 公示:新增資料項「引導期推播代號」/ Public notice: new data item "onboarding push handle"

> 依文件 10「使用者資料治理」:任何新增資料蒐集項目須經公開 PR ＋ 30 天公示,不得以功能迭代名義夾帶。
> Per doc 10, any new data-collection item requires a public PR and a 30-day notice, and must not be bundled into a feature iteration.

| 欄位 / Field | 值 / Value |
|---|---|
| 決議 / Decision | D-014(文件 17)|
| 公示起日 / Notice opens | 2026-09-04 |
| 公示迄日 / Notice closes | 2026-10-04 |
| 目前狀態 / Current status | **公示中。尚未蒐集任何資料。** / Open. No data is being collected. |
| 生效條件 / Takes effect when | 公示期滿,且維護者另以公開 PR 將 `line.onboarding_push_enabled` 改為 true |

> 起迄日以本 PR 合併日為準。若合併日不是 2026-09-04,維護者須在合併時把上表兩個日期一起改正。
> The dates are anchored to this PR's merge date. If the merge lands on another day, the maintainer corrects both dates on merge.

## 公示期間的保證 / What holds during the notice period

`config/firefly.yaml` 的 `line.onboarding_push_enabled` 為 `false`。程式的 `enabled()` 同時要求這個旗標與金鑰 `LINE_PUSH_ENC_KEY`,兩者缺一就完全不啟用。任何人可自行確認:

```bash
grep -n 'onboarding_push_enabled' config/firefly.yaml     # 應為 false / expect false
```

## 蒐集什麼 / What is collected

LINE userId,以伺服器 Fernet 金鑰加密後,只存 Redis。/ The LINE userId, encrypted with a server-side Fernet key, stored in Redis only.

## 為什麼 / Why

讓新加入的仲裁者在前 3 天每天收到 5 張待仲裁卡,養成習慣;之後改由富選單自取。LINE push 需要 userId;既有的 HMAC 代號單向不可逆,無法用於推播。
New arbiters receive 5 cards daily for the first 3 days, then self-serve from the rich menu. LINE push needs the userId; the existing HMAC handle is one-way and cannot be used to push.

## 邊界與可驗證性 / Boundaries, and how to verify each one

每一條承諾都由測試強制,CI 每次推送都會執行。任何人可重跑:`cd backend && pytest -q tests/test_line_onboarding.py`。
Every promise below is enforced by a test that CI runs on every push. Anyone can re-run them.

| 項目 | 承諾 | 驗證測試 / Enforcing test |
|---|---|---|
| 同意 | 使用者按「好」才登錄;按「不用」或不按皆不登錄 | `test_flag_off_means_no_offer_no_enrol_no_push` |
| 加密 | 只存密文;明文 userId 不落地 | `test_day0_reply_with_queue_and_offer_then_enrol_encrypted` |
| 位置 | 只在 Redis;不進 PostgreSQL;Redis 不持久化,故不進備份 | 同上(斷言整個資料庫查無該 userId)|
| 期限 | TTL = 3 天 + 1 小時;到期自動刪除 | 同上(斷言 `0 < TTL ≤ 3×86400+3600`)|
| 期滿刪除 | 第 3 次推播附自取說明並立即刪除 | `test_daily_push_three_days_then_delete` |
| 封鎖即刪 | push 失敗即刪除 | `test_blocked_user_dropped_and_no_new_cards_skips` |
| 解除好友即刪 | unfollow 事件即刪除 | `test_unfollow_unenrols_and_self_serve_queue` |
| 用量上限 | 每日推播人數上限;超量沉默 | `test_daily_cap` |
| 用途 | 只用於這 3 次推播;不用於任何其他目的 | — (程式無其他呼叫點 / no other call site) |
| 審計 | 只公開人次(`onboarding_enrolled`、`onboarding_push_run`);不記個人 | `test_daily_push_three_days_then_delete`(斷言審計 payload 查無該 userId)|

## 尚未完成的配套 / Outstanding commitment

金鑰 `LINE_PUSH_ENC_KEY` 的輪替程序將寫入營運 runbook(文件 14 清單)。**該 runbook 尚未撰寫。**
維護者應在旗標改為 true 之前完成它。此處據實列出,不作已完成之陳述。
The key-rotation procedure for `LINE_PUSH_ENC_KEY` belongs in the operations runbook (doc 14). That runbook does not exist yet. It should be written before the flag is turned on. Stated here as outstanding rather than done.

## 意見回饋 / How to comment

於本 PR 留言。公示期內的所有意見與回覆都留在 PR 討論串,公開可見。
維護者若因意見修改或撤回本案,將在 PR 內說明理由,並重新起算公示期。
Comment on this PR. All comments and replies stay in the public thread. If the maintainer changes or withdraws this proposal in response, the reason is recorded in the thread and the notice period restarts.

## 公示期滿後的步驟 / After the notice closes

期滿本身不啟用任何功能。維護者須另開一個公開 PR,在該 PR 內同時完成:

1. 確認公示期間的意見皆已回覆
2. 完成金鑰輪替 runbook
3. 將 `line.onboarding_push_enabled` 改為 true
4. 於文件 17 追加一筆決議,記錄實際生效日

The notice closing does not by itself enable anything. A separate public PR must do all four steps above.

## 對應變更 / Related changes

文件 02、07、08、17(D-014);程式 `backend/firefly/bots/line_onboarding.py`、`backend/firefly/bots/line.py`;測試 `backend/tests/test_line_onboarding.py`。
