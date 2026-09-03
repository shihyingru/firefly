# 06|API 規格

> 螢火 Firefly|v0.1|2026-07-20|AGPL-3.0
> Base:`https://api.firefly.example/v1`(域名待定)|全 HTTPS|JSON

## 認證

- 消費端:匿名裝置代號(首次呼叫核發 opaque token;不綁個資)
- 貢獻者:裝置代號升級綁定(累積投票後可選具名);Bearer token
- B2B:API key,獨立額度與計價
- 內部入口(LINE/Threads bot 伺服端):service token

## 消費端端點

### POST /devices
核發匿名裝置代號(決議 2026-09-03,見文件 17)。
```json
req: {}                                   // 不帶任何裝置資訊
res 201: { "device_token": "opaque…" }   // 伺服端僅存 token 雜湊與建立時間
```

### POST /lookup
查詢連結,回脈絡卡或狀態。
```json
req: { "url": "https://www.threads.com/@user/post/xxx" }
res 200: { "card": {…}, "cluster_id": "cl_8f2", "status": "displayed|candidate|no_signal" }
res 202: { "status": "processing", "retry_after": 5 }   // 新叢集起草中
res 422: { "status": "unfetchable" }                    // 非公開/已刪除
```

### GET /cards/{card_id}
完整卡片。欄位即文件 04 之白名單:earliest_seen、original_source、account_count、timing_chart(數據點陣列)、archive_links、domain_note、sample_excerpt(逐字節錄)、arbitration(i_c、vote_count、spectrum_coverage)。

### POST /cards/{card_id}/votes
```json
req: { "helpful": true }
res: { "accepted": true }        // 冪等:同代號重複投票覆寫
```

### GET /queue?limit=5
仲裁佇列(需貢獻者 token)。Phase B 後端按光譜平衡策略出題。Phase A(無立場向量)改用操作性策略:排除該貢獻者已投過的卡,有效投票數最少的 candidate 卡優先,同數隨機(決議 2026-09-03)。

### POST /clusters/{id}/flags
具名貢獻者標記聚類錯誤或提交補充出處。

## B2B 端點(第二階段)

- GET /signals/domains:網域訊號清單(含版本、證據連結)
- GET /signals/clusters?since=:活躍叢集摘要流
- 消費端所有資料 B2B 同樣可得;B2B 付費買的是額度、SLA 與推播,不是獨占資料(中立性:資料人人可驗)

## 開放資料端點

- GET /open/cards.jsonl:全量已顯示卡片(每日快照)
- GET /open/audit-log:卡片狀態變更與 prompt 審計
- GET /open/finance:營運收支(文件 12 定義格式)

## 通用規範

- 額度:匿名 60 req/hr;貢獻者 300;B2B 依約。429 附 Retry-After
- 版本策略:URL 版本化;破壞性變更提前 90 天公告
- 錯誤格式:`{ "error": { "code": "...", "message_zh": "...", "message_en": "..." } }`
- 全端點 CORS 開放 GET 之開放資料;寫入端點僅白名單來源
