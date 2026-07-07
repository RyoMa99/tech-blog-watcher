"""cursor.com/ja/blog アダプタ。

フィードが存在しない(/rss.xml 等の定番パスは実在せず、Next.jsのcatch-all
ルートがダミーHTMLを200で返すだけ)。ページの記事一覧HTML
(<a class="blog-directory__row" href="/ja/blog/...">の中に
<time dateTime="ISO8601">と概要<p>タイトル</p>が入っている)から抽出する。
"""

import html as html_lib
import re
from datetime import datetime
from urllib.parse import urljoin

from adapters._http import get

ENTRY_RE = re.compile(
    r'class="blog-directory__row[^"]*" href="(?P<href>/ja/blog/[^"]+)"><article[^>]*>.*?'
    r'<time dateTime="(?P<date>[^"]+)">.*?'
    r'<p class="type-base text-theme-text text-pretty">(?P<title>.*?)</p>',
    re.DOTALL,
)


def fetch(blog: dict) -> list:
    html = get(blog["url"]).decode("utf-8", errors="replace")

    entries = {}
    for m in ENTRY_RE.finditer(html):
        url = urljoin(blog["url"], m.group("href"))
        try:
            published = datetime.fromisoformat(m.group("date").replace("Z", "+00:00"))
        except ValueError:
            published = None
        entries.setdefault(url, {
            "title": html_lib.unescape(m.group("title")).strip(),
            "url": url,
            "published": published,
        })

    if not entries:
        raise RuntimeError("cursor.com/ja/blog: 記事を抽出できなかった(ページ構造が変わった可能性)")
    return list(entries.values())
