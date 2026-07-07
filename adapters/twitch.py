"""Twitch Blog (blog.twitch.tv/en/) アダプタ。

フィードが見当たらないため、SSRページの記事リンク
(/en/YYYY/MM/DD/slug/ 形式。日付はURLから取る)を正規表現で抽出する。
HTML属性はクォート無し(href=/en/... など)の箇所があり、href と class の
順序も一定でないため、<a>タグ全体を取ってから属性を個別に探す。
タイトルは aria-label="タイトル, Jun 17, 2026" 属性(先頭に "Featured"、
末尾に ". 概要" が付くことがある)を優先し、無ければアンカー本文を使う。
"""

import html as html_lib
import re
from datetime import datetime
from urllib.parse import urljoin

from adapters._http import get

ANCHOR_RE = re.compile(r"<a\s(?P<attrs>[^>]*)>(?P<body>.*?)</a>", re.DOTALL)
HREF_RE = re.compile(r'href=(?:"(?P<q>/en/\d{4}/\d{2}/\d{2}/[^"]+)"|(?P<uq>/en/\d{4}/\d{2}/\d{2}/[^\s>]+))')
ARIA_RE = re.compile(r'aria-label="(?P<label>[^"]*)"', re.DOTALL)
DATE_IN_URL_RE = re.compile(r"/en/(\d{4})/(\d{2})/(\d{2})/")
# aria-label 末尾の ", Jun 17, 2026" (月名は省略形/フル両方) と、その後に続く概要文を落とす
LABEL_DATE_RE = re.compile(r",\s*[A-Z][a-z]+\s+\d{1,2},\s+\d{4}(?:\..*)?$", re.DOTALL)
TAG_RE = re.compile(r"<[^>]+>")


def fetch(blog: dict) -> list:
    html = get(blog["url"]).decode("utf-8", errors="replace")

    entries = {}
    for m in ANCHOR_RE.finditer(html):
        attrs = m.group("attrs")
        href_m = HREF_RE.search(attrs)
        if not href_m:
            continue
        href = href_m.group("q") or href_m.group("uq")

        aria_m = ARIA_RE.search(attrs)
        if aria_m:
            title = LABEL_DATE_RE.sub("", aria_m.group("label"))
            title = re.sub(r"^Featured\s+", "", title)
        else:
            title = TAG_RE.sub("", m.group("body"))
        title = " ".join(html_lib.unescape(title).split())
        if not title or title.lower() == "post":
            continue

        url = urljoin(blog["url"], href)
        date_m = DATE_IN_URL_RE.search(href)
        published = datetime(int(date_m.group(1)), int(date_m.group(2)), int(date_m.group(3)))
        entries.setdefault(url, {"title": title, "url": url, "published": published})

    if not entries:
        raise RuntimeError("Twitch Blog: 記事を抽出できなかった(ページ構造が変わった可能性)")
    return list(entries.values())
