"""DMM inside アダプタ。

フィードがなく sitemap.xml の lastmod も新着判定に使えないため、
Next.js の __NEXT_DATA__ JSONから記事一覧を抽出する。

注意: 2026-07-07 の実装時点でサイトがメンテナンス中(503)だったため、
JSON内の記事オブジェクトの正確な形は未検証。記事らしきオブジェクト
(タイトル + 日付 + URL/slug を持つdict)を再帰探索する防御的実装にしてある。
構造が確定したら特定パスの参照に置き換えてよい。
"""

import json
import re
from datetime import datetime
from urllib.parse import urljoin

from adapters._http import get

NEXT_DATA_RE = re.compile(
    r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.DOTALL
)

TITLE_KEYS = ("title", "name")
DATE_KEYS = ("publishedAt", "published_at", "publishDate", "date", "createdAt", "created_at")
LINK_KEYS = ("url", "path", "href", "slug", "link")


def _parse_date(value):
    if not isinstance(value, str):
        return None
    v = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(v)
    except ValueError:
        pass
    m = re.match(r"(\d{4})[-/](\d{2})[-/](\d{2})", value)
    if m:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return None


def _first(d: dict, keys):
    for k in keys:
        if d.get(k):
            return d[k]
    return None


def _walk(node, found: dict, base_url: str):
    if isinstance(node, dict):
        title = _first(node, TITLE_KEYS)
        date_raw = _first(node, DATE_KEYS)
        link = _first(node, LINK_KEYS)
        if isinstance(title, str) and isinstance(link, str) and date_raw:
            published = _parse_date(date_raw)
            if published is not None:
                url = urljoin(base_url, link)
                found.setdefault(url, {"title": title, "url": url, "published": published})
        for v in node.values():
            _walk(v, found, base_url)
    elif isinstance(node, list):
        for v in node:
            _walk(v, found, base_url)


def fetch(blog: dict) -> list:
    html = get(blog["url"]).decode("utf-8", errors="replace")
    m = NEXT_DATA_RE.search(html)
    if not m:
        raise RuntimeError("DMM inside: __NEXT_DATA__ が見つからない(メンテナンス中か構造変更の可能性)")
    data = json.loads(m.group(1))

    found = {}
    _walk(data, found, blog["url"])
    if not found:
        raise RuntimeError("DMM inside: __NEXT_DATA__ から記事らしきオブジェクトを抽出できなかった")
    return list(found.values())
