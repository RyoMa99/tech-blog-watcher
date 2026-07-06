"""Wantedly stories アダプタ。

フィードがないため、ページHTMLに埋め込まれたJSONの
"posts":[{"post_path":..., "title":..., "published_at":...}] 配列から記事を抽出する。
(<link rel="alternate"> の projects.xml は求人フィードなので使わない)
"""

import json
from datetime import datetime
from urllib.parse import urljoin

from adapters._http import get

MARKER = '"posts":['


def fetch(blog: dict) -> list:
    html = get(blog["url"]).decode("utf-8", errors="replace")

    entries = {}
    decoder = json.JSONDecoder()
    pos = 0
    while True:
        idx = html.find(MARKER, pos)
        if idx == -1:
            break
        try:
            posts, _ = decoder.raw_decode(html, idx + len(MARKER) - 1)
        except json.JSONDecodeError:
            pos = idx + len(MARKER)
            continue
        for post in posts:
            if not isinstance(post, dict):
                continue
            path = post.get("post_path")
            title = post.get("title")
            published_at = post.get("published_at")
            if not (path and title and published_at):
                continue
            url = urljoin(blog["url"], path)
            try:
                published = datetime.fromisoformat(published_at)
            except ValueError:
                published = None
            entries.setdefault(url, {"title": title, "url": url, "published": published})
        pos = idx + len(MARKER)

    if not entries:
        raise RuntimeError("Wantedly: 埋め込みJSONから記事を抽出できなかった(ページ構造が変わった可能性)")
    return list(entries.values())
