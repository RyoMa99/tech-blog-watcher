"""manager.dev (managerdotdev.beehiiv.com) アダプタ。

beehiiv のニュースレターだが RSS が無効化されており、
/feed も rss.beehiiv.com/feeds/<id>.xml も 404 を返す。
アーカイブページ (/archive) のHTMLに埋め込まれた JSON の "posts" 配列
(web_title / slug / scheduled_at)から記事一覧を抽出する。
記事URLは https://managerdotdev.beehiiv.com/p/<slug>。
"""

import json
from datetime import datetime
from urllib.parse import urljoin

from adapters._http import get

POSTS_KEY = '"posts":'


def _extract_posts_json(html: str) -> list:
    """HTML中の "posts":[...] を括弧の対応を数えて切り出しJSONとして読む。"""
    key_at = html.find(POSTS_KEY)
    if key_at == -1:
        return []
    start = html.find("[", key_at)
    if start == -1:
        return []

    depth = 0
    for i in range(start, len(html)):
        ch = html[i]
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(html[start : i + 1])
                except json.JSONDecodeError:
                    return []
    return []


def _parse_published(post: dict):
    raw = post.get("scheduled_at") or post.get("override_scheduled_at")
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def fetch(blog: dict) -> list:
    html = get(blog["url"]).decode("utf-8", errors="replace")

    entries = {}
    for post in _extract_posts_json(html):
        if not isinstance(post, dict):
            continue
        title = post.get("web_title")
        slug = post.get("slug")
        if not (title and slug):
            continue
        url = urljoin(blog["url"], f"/p/{slug}")
        entries.setdefault(
            url,
            {"title": title.strip(), "url": url, "published": _parse_published(post)},
        )

    if not entries:
        raise RuntimeError("manager.dev: 記事を抽出できなかった(ページ構造が変わった可能性)")
    return list(entries.values())
