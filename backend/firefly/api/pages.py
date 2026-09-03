"""
卡片網頁 / Card web page(Threads 回覆連結與 LINE「完整卡片」的落點;投票在此完成)。
無第三方分析、無追蹤;投票用裝置代號(localStorage)呼叫 /v1/devices 與 /v1/cards/{id}/votes。
Plain server-rendered HTML, no third-party analytics; votes use a device token kept in localStorage.
"""
from __future__ import annotations

import html
import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..services.cards import card_public_view, get_visible_card

router = APIRouter()

_PAGE = """<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>脈絡卡 · 螢火 Firefly</title>
<style>body{{font-family:system-ui,-apple-system,"Noto Sans TC",sans-serif;max-width:620px;margin:2rem auto;padding:0 1rem;color:#222}}
.k{{color:#666;font-size:.9rem}} .ex{{background:#f6f6f6;padding:.75rem;border-radius:8px;white-space:pre-wrap}} button{{padding:.6rem 1.2rem;margin-right:.5rem;border-radius:8px;border:1px solid #888;background:#fff;cursor:pointer}}
.tag{{display:inline-block;font-size:.8rem;color:#777;border:1px solid #ddd;border-radius:6px;padding:.1rem .4rem}} footer{{margin-top:2rem;font-size:.8rem;color:#888}}</style></head><body>
<h1>脈絡卡</h1><p class="k">你有注意到 {n} 個帳號發布了相同或近似的內容嗎?</p>
<p><span class="tag">{label}</span></p>
<dl><dt class="k">最早出現</dt><dd>{earliest}</dd><dt class="k">原始出處</dt><dd>{source}</dd><dt class="k">同文帳號數</dt><dd>{n}</dd><dt class="k">網域比對</dt><dd>{domain}</dd><dt class="k">快照</dt><dd>{archives}</dd></dl>
<p class="k">節錄(逐字)</p><div class="ex">{excerpt}</div>
<h2>這張卡對你有幫助嗎?</h2><p><button onclick="vote(true)">有幫助</button><button onclick="vote(false)">沒幫助</button> <span id="msg"></span></p>
<p class="k">有效投票數:{votes}。投票匿名;系統不記錄 IP、國籍或真實身分。</p>
<footer>螢火 Firefly · AGPL-3.0 · 不判定真假,只讓不可見的協同行為變可見 · <a href="/v1/cards/{card_id}">JSON</a></footer>
<script>
async function token(){{let t=null;try{{t=localStorage.getItem('ff_device')}}catch(e){{}}
 if(!t){{const r=await fetch('/v1/devices',{{method:'POST',headers:{{'content-type':'application/json'}},body:'{{}}'}});t=(await r.json()).device_token;try{{localStorage.setItem('ff_device',t)}}catch(e){{}}}}return t}}
async function vote(h){{const t=await token();const r=await fetch('/v1/cards/{card_id}/votes',{{method:'POST',headers:{{'content-type':'application/json','authorization':'Bearer '+t}},body:JSON.stringify({{helpful:h}})}});
 const j=await r.json();document.getElementById('msg').textContent=r.ok?(j.counted?'謝謝你的仲裁。':'已保存;累積幾次查詢後就會計入仲裁。'):'目前無法投票。'}}
</script></body></html>"""


@router.get("/cards/{card_id}", response_class=HTMLResponse, include_in_schema=False)
async def card_page(card_id: uuid.UUID, session: AsyncSession = Depends(get_db)):
    card = await get_visible_card(session, card_id)
    if card is None:
        return HTMLResponse("<!doctype html><meta charset=utf-8><p>這張卡片目前不可用。</p>", status_code=404)
    v = card_public_view(card)
    f = v["fields"]
    es, src = f["earliest_seen"], f["original_source"]
    e = html.escape
    earliest = e(es["at"][:16].replace("T", " ")) + (f' · <a href="{e(es["url"])}">來源</a>' if es.get("url") else "") if es.get("at") else e(es.get("note", "未能確認"))
    source = f'<a href="{e(src["url"])}">{e(src["url"])}</a>' if src.get("traced") else e(src.get("note", "未能追溯"))
    dm = f["domain_note"]["matches"]
    domain = "、".join(f'{e(m["domain"])}({e(m["source_list"])} {e(m["list_version"])})' for m in dm) if dm else "無符合(清單版本 " + e(str(f["domain_note"]["list_version"] or "-")) + ")"
    archives = "、".join(f'<a href="{e(a["archive_url"])}">快照</a>' for a in f["archive_links"]) or "尚無"
    return HTMLResponse(_PAGE.format(n=f["account_count"], label=e(v["arbitration"]["label"]["zh"] or ""), earliest=earliest, source=source, domain=domain, archives=archives, excerpt=e(f.get("sample_excerpt") or ""), votes=v["arbitration"]["vote_count"], card_id=v["card_id"]))
