#!/usr/bin/env python3
"""
Threads OAuth 授權碼交換 / Threads OAuth code exchange
螢火 Firefly | AGPL-3.0

用途 / Purpose
  把瀏覽器授權後拿到的一次性 code 換成 user access token,再換成 60 天長效 token。
  token 只寫入 --out 指定的檔案,不印到畫面。
  Exchange the one-time code from the browser for a user access token, then for a
  60-day long-lived token. The token is written only to the --out file, never printed.

需要的環境變數 / Required environment variables
  THREADS_APP_ID, THREADS_APP_SECRET

執行 / Run
  python3 scripts/threads_oauth.py --code XXXX --redirect-uri https://localhost/callback --out /path/token.txt
"""
import argparse
import json
import os
import sys
import urllib.parse
import urllib.request

GRAPH = "https://graph.threads.net"


def post(url: str, data: dict) -> dict:
    body = urllib.parse.urlencode(data).encode()
    with urllib.request.urlopen(urllib.request.Request(url, data=body), timeout=20) as r:
        return json.loads(r.read().decode())


def get(url: str, params: dict) -> dict:
    with urllib.request.urlopen(url + "?" + urllib.parse.urlencode(params), timeout=20) as r:
        return json.loads(r.read().decode())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--code", required=True)
    ap.add_argument("--redirect-uri", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    app_id, secret = os.environ.get("THREADS_APP_ID"), os.environ.get("THREADS_APP_SECRET")
    if not (app_id and secret):
        print("THREADS_APP_ID and THREADS_APP_SECRET are required", file=sys.stderr)
        sys.exit(2)
    code = a.code.removesuffix("#_")
    try:
        short = post(f"{GRAPH}/oauth/access_token", {
            "client_id": app_id, "client_secret": secret, "grant_type": "authorization_code",
            "redirect_uri": a.redirect_uri, "code": code,
        })
    except urllib.error.HTTPError as e:  # type: ignore[attr-defined]
        print("short-lived exchange failed:", e.read().decode()[:500], file=sys.stderr)
        sys.exit(1)
    token = short["access_token"]
    kind = "short-lived (1h)"
    try:
        long = get(f"{GRAPH}/access_token", {
            "grant_type": "th_exchange_token", "client_secret": secret, "access_token": token,
        })
        token, kind = long["access_token"], f"long-lived ({long.get('expires_in')}s)"
    except Exception as e:  # noqa: BLE001
        print("long-lived exchange failed, keeping short-lived token:", type(e).__name__, file=sys.stderr)
    with open(a.out, "w") as f:
        f.write(token)
    os.chmod(a.out, 0o600)
    print(f"ok: {kind} token for user_id={short.get('user_id')} written to {a.out}")


if __name__ == "__main__":
    main()
