"""Uber Engineering Blog (eng.uber.com) アダプタ。

フィードが全滅している(headで宣言されたfeed URLは404/406でリンク切れ)ため、
静的レンダリング済みHTMLの記事カード
(<a class="blog-card" data-date="YYYY-MM-DD" href="https://www.uber.com/blog/...">
の中に<h3 class="blog-card-title">タイトル</h3>が入っている)を正規表現で抽出する。
"""

import html as html_lib
import re
from datetime import datetime
from urllib.parse import urljoin

from adapters._http import get

ENTRY_RE = re.compile(
    r'<a class="blog-card"[^>]*\bdata-date="(?P<date>[^"]*)"[^>]*\bhref="(?P<href>[^"]+)"[^>]*>.*?'
    r'<h3 class="blog-card-title">(?P<title>.*?)</h3>',
    re.DOTALL,
)


def fetch(blog: dict) -> list:
    html = get(blog["url"]).decode("utf-8", errors="replace")

    entries = {}
    for m in ENTRY_RE.finditer(html):
        url = urljoin(blog["url"], m.group("href"))
        try:
            published = datetime.strptime(m.group("date").strip(), "%Y-%m-%d")
        except ValueError:
            published = None
        entries.setdefault(url, {
            "title": html_lib.unescape(m.group("title")).strip(),
            "url": url,
            "published": published,
        })

    if not entries:
        raise RuntimeError("Uber Engineering: 記事を抽出できなかった(ページ構造が変わった可能性)")
    return list(entries.values())
