#!/usr/bin/env python3
"""
Threads 資料取得可行性探測 / Threads data-access feasibility probe
螢火 Firefly | AGPL-3.0

用途 / Purpose
  在你的本機執行,回報 Stage 0 與 Threads Bot 所需的每一條資料路徑是否可用。
  Run on your own machine. It reports whether each data path that Stage 0 and
  the Threads bot need is available.

  本腳本只讀取,不發文,不回覆,不寫入任何資料。
  This script only reads. It does not post, reply, or store anything.

需要的環境變數 / Required environment variables
  THREADS_USER_TOKEN   測試帳號的 user access token(App Roles 中的 Threads tester 可直接授權,免 App Review)
                       user access token of a tester account (Threads testers under App Roles can grant scopes without App Review)
  THREADS_APP_ID       選填 / optional:app id,用於 oEmbed 的 app token
  THREADS_APP_SECRET   選填 / optional:app secret

參數 / Arguments
  --url      一則「不是你自己發的」公開貼文 URL / a public post URL NOT authored by the tester account
  --keyword  關鍵字 / a keyword to search (default: 台灣)
  --tag      主題標籤 / a topic tag to search (default: 新聞)

執行 / Run
  python3 scripts/threads_probe.py --url https://www.threads.com/@someone/post/XXXXXXXXXXX

輸出 / Output
  人類可讀摘要 + 一段 JSON 報告(貼回對話即可)。
  Human-readable summary + one JSON report (paste it back into the conversation).
"""
import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

GRAPH = "https://graph.threads.net/v1.0"
UA = "Mozilla/5.0 (firefly-probe; +https://github.com/shihyingru/firefly)"
MEDIA_FIELDS = "id,text,username,timestamp,permalink,shortcode,topic_tag,link_attachment_url,media_type"
ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"


def http_get(url: str, params: dict | None = None, timeout: int = 20) -> dict:
    """GET 並回傳 {status, body, json, error}。不拋例外。/ GET; never raises."""
    if params:
        url = url + ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    out = {"url": redact(url), "status": None, "json": None, "body": None, "error": None}
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read().decode("utf-8", "replace")
            out["status"] = r.status
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        out["status"] = e.code
    except Exception as e:  # noqa: BLE001
        out["error"] = f"{type(e).__name__}: {e}"
        return out
    out["body"] = body
    try:
        out["json"] = json.loads(body)
    except ValueError:
        pass
    return out


def redact(url: str) -> str:
    """把 token 從紀錄中遮掉 / hide tokens in the report."""
    return re.sub(r"(access_token=)[^&]+", r"\1<redacted>", url)


def shortcode_to_id(shortcode: str) -> int:
    """Instagram/Threads 短碼 → 數字 ID(base64 變體)。/ shortcode → numeric id."""
    n = 0
    for ch in shortcode:
        n = n * 64 + ALPHABET.index(ch)
    return n


def parse_post_url(url: str):
    m = re.search(r"threads\.(?:net|com)/@([^/]+)/post/([A-Za-z0-9_-]+)", url)
    return (m.group(1), m.group(2)) if m else (None, None)


def probe_oembed(url: str, app_token: str | None):
    """A. oEmbed:是否回傳貼文文字、作者、時間?/ does it return text, author, timestamp?"""
    if not app_token:
        return {"skipped": "no THREADS_APP_ID/THREADS_APP_SECRET"}
    r = http_get(f"{GRAPH}/oembed", {"url": url, "access_token": app_token})
    res = {"status": r["status"], "error": r["error"]}
    j = r["json"] or {}
    res["keys"] = sorted(j.keys()) if isinstance(j, dict) else None
    html = j.get("html", "") if isinstance(j, dict) else ""
    res["html_len"] = len(html)
    # 觀察:嵌入 HTML 是否含貼文文字與時間 / does the embed html carry text and a time?
    res["html_has_time_tag"] = bool(re.search(r"<time|datetime=", html))
    res["html_visible_text_sample"] = re.sub(r"<[^>]+>", " ", html)[:300].strip()
    res["timestamp_like_fields"] = [k for k in j if re.search(r"time|date", k, re.I)] if isinstance(j, dict) else []
    if r["status"] != 200:
        res["body_head"] = (r["body"] or "")[:300]
    return res


def probe_media_by_id(url: str, user_token: str):
    """B. 非本人貼文能否用 GET /{media_id} 讀取?/ can we read someone else's public post by id?"""
    _, shortcode = parse_post_url(url)
    if not shortcode:
        return {"skipped": "url is not a threads post url"}
    mid = shortcode_to_id(shortcode)
    r = http_get(f"{GRAPH}/{mid}", {"fields": MEDIA_FIELDS, "access_token": user_token})
    res = {"decoded_id": mid, "status": r["status"], "error": r["error"]}
    j = r["json"] or {}
    if r["status"] == 200:
        res["fields_present"] = sorted(k for k in j if j.get(k) not in (None, ""))
    else:
        res["api_error"] = j.get("error") if isinstance(j, dict) else (r["body"] or "")[:300]
    return res


def probe_keyword_search(q: str, user_token: str, search_mode: str | None = None):
    """C. 關鍵字 / 標籤搜尋:欄位是否含 timestamp、username、permalink?"""
    params = {"q": q, "search_type": "RECENT", "fields": MEDIA_FIELDS, "limit": 10, "access_token": user_token}
    if search_mode:
        params["search_mode"] = search_mode
    r = http_get(f"{GRAPH}/keyword_search", params)
    res = {"q": q, "search_mode": search_mode, "status": r["status"], "error": r["error"]}
    j = r["json"] or {}
    data = j.get("data") if isinstance(j, dict) else None
    if isinstance(data, list):
        res["count"] = len(data)
        present = set()
        for item in data:
            present |= {k for k in item if item.get(k) not in (None, "")}
        res["fields_present_union"] = sorted(present)
        res["distinct_usernames"] = len({d.get("username") for d in data})
        res["sample"] = [{k: d.get(k) for k in ("username", "timestamp", "permalink")} for d in data[:3]]
    else:
        res["api_error"] = j.get("error") if isinstance(j, dict) else (r["body"] or "")[:300]
    return res


def probe_mentions(user_token: str):
    """D. mentions 端點(輪詢備援路線)/ mentions endpoint (polling fallback)."""
    r = http_get(f"{GRAPH}/me/mentions", {"fields": MEDIA_FIELDS, "limit": 5, "access_token": user_token})
    j = r["json"] or {}
    res = {"status": r["status"], "error": r["error"]}
    if r["status"] == 200:
        res["count"] = len(j.get("data", []))
        res["fields_present_union"] = sorted({k for d in j.get("data", []) for k in d})
    else:
        res["api_error"] = j.get("error") if isinstance(j, dict) else (r["body"] or "")[:300]
    return res


def probe_public_page(url: str):
    """E. 公開網頁(僅供對照;文件 13 規定 Threads 不爬非 API 資料,此路徑不作為實作依據)
    Public web page (reference only; doc 13 forbids non-API scraping of Threads, this path is not an implementation basis)."""
    r = http_get(url)
    res = {"status": r["status"], "error": r["error"]}
    body = r["body"] or ""
    res["bytes"] = len(body)
    res["login_wall"] = bool(re.search(r"/login|accounts/login", body)) and not re.search(r'og:description', body)
    m = re.search(r'<meta property="og:description" content="([^"]*)"', body)
    res["og_description"] = (m.group(1)[:200] if m else None)
    res["has_taken_at"] = '"taken_at"' in body
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--keyword", default="台灣")
    ap.add_argument("--tag", default="新聞")
    a = ap.parse_args()

    user_token = os.environ.get("THREADS_USER_TOKEN")
    app_id, app_secret = os.environ.get("THREADS_APP_ID"), os.environ.get("THREADS_APP_SECRET")
    app_token = f"TH|{app_id}|{app_secret}" if app_id and app_secret else None
    if not user_token:
        print("THREADS_USER_TOKEN is required", file=sys.stderr)
        sys.exit(2)

    report = {
        "A_oembed": probe_oembed(a.url, app_token),
        "B_media_by_id_not_owned": probe_media_by_id(a.url, user_token),
        "C1_keyword_search": probe_keyword_search(a.keyword, user_token),
        "C2_tag_search": probe_keyword_search(a.tag, user_token, search_mode="TAG"),
        "D_mentions_polling": probe_mentions(user_token),
        "E_public_page_reference_only": probe_public_page(a.url),
        "F_webhook": {
            "note": "Webhook 需公開 HTTPS 端點與 App Dashboard 訂閱,無法離線測試。"
                    "步驟:1) App Dashboard → Webhooks → Threads → 訂閱 mentions、replies;"
                    "2) 指向 /v1/threads/webhook(後端實作後提供);3) 用另一帳號 @ 測試帳號,觀察是否收到事件。"
                    "/ Needs a public HTTPS endpoint and a dashboard subscription; cannot be tested offline."
        },
    }

    print("=== 摘要 / Summary ===")
    A = report["A_oembed"]
    print(f"A oEmbed: status={A.get('status')} keys={A.get('keys')} timestamp_like={A.get('timestamp_like_fields')} html_time_tag={A.get('html_has_time_tag')}")
    B = report["B_media_by_id_not_owned"]
    print(f"B GET /{{id}} (not owned): status={B.get('status')} fields={B.get('fields_present')} err={B.get('api_error')}")
    for k in ("C1_keyword_search", "C2_tag_search"):
        C = report[k]
        print(f"{k}: status={C.get('status')} count={C.get('count')} fields={C.get('fields_present_union')} err={C.get('api_error')}")
    D = report["D_mentions_polling"]
    print(f"D mentions: status={D.get('status')} count={D.get('count')} err={D.get('api_error')}")
    E = report["E_public_page_reference_only"]
    print(f"E public page (reference only): status={E.get('status')} og_description={'yes' if E.get('og_description') else 'no'} taken_at={E.get('has_taken_at')}")
    print("\n=== JSON 報告(請貼回)/ JSON report (paste back) ===")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
