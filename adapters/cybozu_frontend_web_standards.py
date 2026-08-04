"""サイボウズ フロントエンド Publication (zenn.dev/p/cybozu_frontend) の
「Web 標準動向」月次まとめ記事のみを抽出するアダプタ。

Publicationの全体フィードには週次まとめや個別の技術記事も混ざっているため、
タイトルが「Web 標準動向」で始まる記事だけをフィルタする
(例: 「Web 標準動向 2026年7月版」)。
"""

import re
from datetime import datetime, timezone

import feedparser

from adapters._http import get

TITLE_RE = re.compile(r"^Web\s*標準動向")


def fetch(blog: dict) -> list:
    parsed = feedparser.parse(get(blog["feed"]))
    if parsed.bozo and not parsed.entries:
        raise RuntimeError(f"Web標準動向: フィードをパースできなかった: {parsed.bozo_exception}")

    entries = []
    for e in parsed.entries:
        title = e.get("title")
        link = e.get("link")
        if not (title and link) or not TITLE_RE.match(title):
            continue
        published = None
        for key in ("published_parsed", "updated_parsed"):
            st = e.get(key)
            if st:
                published = datetime(*st[:6], tzinfo=timezone.utc)
                break
        entries.append({"title": title, "url": link, "published": published})

    if not entries:
        raise RuntimeError("Web標準動向: 記事を抽出できなかった(タイトル形式が変わった可能性)")
    return entries
