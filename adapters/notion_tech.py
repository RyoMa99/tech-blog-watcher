"""Notion Blog 技術トピック (www.notion.com/ja/blog/topic/tech) アダプタ。

フィードが存在しないため、Next.js SSRページの <script id="__NEXT_DATA__">
に埋め込まれたJSONの props.pageProps.posts 配列から記事を抽出する。
各postは fields.title / fields.slug を持ち、記事URLは
https://www.notion.com/ja/blog/<slug> になる。
一覧レベルに公開日が含まれないため published は None
(新着判定はURL差分で行われるため問題ない)。
"""

import json
import re
from urllib.parse import urljoin

from adapters._http import get

NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__"[^>]*>(?P<json>.*?)</script>', re.DOTALL
)


def fetch(blog: dict) -> list:
    html = get(blog["url"]).decode("utf-8", errors="replace")

    entries = {}
    m = NEXT_DATA_RE.search(html)
    if m:
        try:
            data = json.loads(m.group("json"))
        except json.JSONDecodeError:
            data = {}
        posts = data.get("props", {}).get("pageProps", {}).get("posts") or []
        for post in posts:
            if not isinstance(post, dict):
                continue
            fields = post.get("fields") or {}
            title = fields.get("title")
            slug = fields.get("slug")
            if not (title and slug):
                continue
            url = urljoin(blog["url"], f"/ja/blog/{slug}")
            entries.setdefault(url, {"title": title.strip(), "url": url, "published": None})

    if not entries:
        raise RuntimeError("Notion Blog (tech): 記事を抽出できなかった(ページ構造が変わった可能性)")
    return list(entries.values())
