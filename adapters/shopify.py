"""Shopify Engineering (shopify.engineering/latest) アダプタ。

フィードが存在しない(/blog.atom はトップへリダイレクト、/feed 等は404)。
サーバーレンダリング済みの記事一覧HTML
(タイトルの<a href="/slug">の直後に<p class="richtext ...">Jun 17, 2026</p>
という日付が続く)を正規表現で抽出する。
"""

import html as html_lib
import re
from datetime import datetime
from urllib.parse import urljoin

from adapters._http import get

# title には他のタグが混ざりうるが、別のアンカーを跨がないよう </a を含まない範囲に限定する
ENTRY_RE = re.compile(
    r'<a[^>]* href="(?P<href>/[^"]+)"[^>]*>(?P<title>(?:(?!</a).)*)</a></div>'
    r'<p class="richtext[^"]*">(?P<date>[^<]+)</p>',
    re.DOTALL,
)
TAG_RE = re.compile(r"<[^>]+>")


def fetch(blog: dict) -> list:
    html = get(blog["url"]).decode("utf-8", errors="replace")

    entries = {}
    for m in ENTRY_RE.finditer(html):
        title = html_lib.unescape(TAG_RE.sub("", m.group("title"))).strip()
        if not title:
            continue
        url = urljoin(blog["url"], m.group("href"))
        try:
            published = datetime.strptime(m.group("date").strip(), "%b %d, %Y")
        except ValueError:
            published = None
        entries.setdefault(url, {"title": title, "url": url, "published": published})

    if not entries:
        raise RuntimeError("Shopify Engineering: 記事を抽出できなかった(ページ構造が変わった可能性)")
    return list(entries.values())
