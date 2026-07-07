"""Anthropic News (www.anthropic.com/news) アダプタ。

フィードが存在しないため、ページHTMLの記事カード
(<a href="/news/...">の中に<time>日付</time>とtitleクラスの要素が入っている)
を正規表現で抽出する。
"""

import re
from datetime import datetime
from urllib.parse import urljoin

from adapters._http import get

LINK_RE = re.compile(r'<a href="(?P<href>/news/[^"]+)"[^>]*>(?P<body>.*?)</a>', re.DOTALL)
TIME_RE = re.compile(r"<time[^>]*>([^<]+)</time>")
TITLE_RE = re.compile(r'class="[^"]*title[^"]*"[^>]*>([^<]+)<')


def fetch(blog: dict) -> list:
    html = get(blog["url"]).decode("utf-8", errors="replace")

    entries = {}
    for m in LINK_RE.finditer(html):
        body = m.group("body")
        time_m = TIME_RE.search(body)
        title_m = TITLE_RE.search(body)
        if not (time_m and title_m):
            continue
        url = urljoin(blog["url"], m.group("href"))
        try:
            published = datetime.strptime(time_m.group(1).strip(), "%b %d, %Y")
        except ValueError:
            published = None
        entries.setdefault(url, {"title": title_m.group(1).strip(), "url": url, "published": published})

    if not entries:
        raise RuntimeError("Anthropic News: 記事を抽出できなかった(ページ構造が変わった可能性)")
    return list(entries.values())
