"""
LINE Flex Message 組裝 / Flex Message builders(文件 7.1、文件 02 文案語氣)。

語氣準則:提問不斷言;不用「假訊息」「闢謠」;查無訊號時明說查無。
Tone: ask, don't assert; never "fake news" / "debunk"; say "no signal" plainly when there is none.
"""
from __future__ import annotations

from ..config import get_settings

LITERACY_TIPS = [
    "看到很多帳號同時說同一件事時,可以先問:最早是誰說的?",
    "分享前,試著找找原始出處。",
    "同一段文字出現在很多地方,不代表它是真的,也不代表它是假的。",
]


def _text(t: str, **kw) -> dict:
    return {"type": "text", "text": t, "wrap": True, **kw}


def card_bubble(card: dict) -> dict:
    """摘要 bubble(出處/時間/帳號數)+ 按鈕列(有幫助/沒幫助 postback、看完整卡片 URI)。"""
    f = card["fields"]
    label = card["arbitration"]["label"]["zh"]
    es = f["earliest_seen"]
    earliest = es["at"][:16].replace("T", " ") if es.get("at") else es.get("note", "未能確認")
    src = f["original_source"]
    source = src["url"] if src.get("traced") else src.get("note", "未能追溯")
    n = f["account_count"]
    excerpt = (f.get("sample_excerpt") or "")[:60]
    base = get_settings().public_base_url.rstrip("/")
    body = [
        _text("脈絡卡", weight="bold", size="lg"),
        _text(f"你有注意到 {n} 個帳號發布了相同或近似的內容嗎?", size="sm", color="#555555"),
        {"type": "separator", "margin": "md"},
        _text(f"最早出現:{earliest}", size="sm", margin="md"),
        _text(f"原始出處:{source}", size="sm"),
        _text(f"同文帳號數:{n}", size="sm"),
    ]
    if excerpt:
        body.append(_text(f"「{excerpt}」", size="xs", color="#888888", margin="md"))
    if label:
        body.append(_text(label, size="xs", color="#999999", margin="md"))
    return {
        "type": "bubble",
        "body": {"type": "box", "layout": "vertical", "contents": body},
        "footer": {
            "type": "box",
            "layout": "horizontal",
            "spacing": "sm",
            "contents": [
                {"type": "button", "style": "primary", "height": "sm", "action": {"type": "postback", "label": "有幫助", "data": f"vote:{card['card_id']}:1", "displayText": "有幫助"}},
                {"type": "button", "style": "secondary", "height": "sm", "action": {"type": "postback", "label": "沒幫助", "data": f"vote:{card['card_id']}:0", "displayText": "沒幫助"}},
                {"type": "button", "style": "link", "height": "sm", "action": {"type": "uri", "label": "完整卡片", "uri": f"{base}/cards/{card['card_id']}"}},
            ],
        },
    }


def card_message(card: dict) -> dict:
    return {"type": "flex", "altText": f"脈絡卡:{card['fields']['account_count']} 個帳號發布相同內容", "contents": card_bubble(card)}


def processing_message(url: str) -> dict:
    """D-008:202 時回「處理中」+「再查一次」按鈕;不 push、不等待。"""
    return {
        "type": "template",
        "altText": "處理中,請稍後再查一次",
        "template": {
            "type": "buttons",
            "text": "正在整理這則貼文的脈絡,通常需要幾秒到一分鐘。",
            "actions": [{"type": "postback", "label": "再查一次", "data": f"relookup:{url}", "displayText": "再查一次"}],
        },
    }


def no_signal_message(tip_index: int = 0) -> dict:
    return {"type": "text", "text": "目前查無協同訊號。\n\n" + LITERACY_TIPS[tip_index % len(LITERACY_TIPS)]}


def unfetchable_message() -> dict:
    return {"type": "text", "text": "無法取得內容。這則貼文可能不是公開的,或已被刪除。"}


def no_url_message() -> dict:
    return {"type": "text", "text": "請貼上一則公開貼文的連結,我會回覆它的脈絡卡。"}


def thanks_message(counted: bool) -> dict:
    tail = "" if counted else "\n(你的投票已保存;累積幾次查詢後就會計入仲裁。)"
    return {"type": "text", "text": "謝謝你的仲裁。一次仲裁會覆蓋整個說法叢集。" + tail}


def welcome_message() -> dict:
    return {"type": "text", "text": "你好,我是螢火。貼上一則公開貼文的連結,我會告訴你:最早出現時間、原始出處、有多少帳號發布相同內容。\n\n我不判定真假,只讓不可見的協同行為變可見。"}
