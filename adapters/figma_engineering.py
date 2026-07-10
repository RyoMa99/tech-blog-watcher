"""Figma Engineering (www.figma.com/ja-jp/blog/engineering/) アダプタ。

エンジニアリングタグの一覧ページは Next.js SSR で、初回表示は直近12件のみ
(残りは「さらに読み込み」でクライアント取得)。RSS/Atom フィードは無い。
<article aria-label="タイトル"> 内の記事リンクと <time dateTime="YYYY年M月D日">
から抽出する。新着監視は先頭ページで十分(新記事は常に先頭に載る)。
"""

import html as html_lib
import re
from datetime import datetime

from adapters._http import get

ARTICLE_RE = re.compile(
    r'<article aria-label="(?P<title>[^"]+)">.*?'
    r'href="(?P<href>https://www\.figma\.com/ja-jp/blog/[^"#?]+/?)"[^>]*>.*?'
    r'dateTime="(?P<date>\d{4}年\d{1,2}月\d{1,2}日)"',
    re.DOTALL,
)
DATE_RE = re.compile(r"(\d{4})年(\d{1,2})月(\d{1,2})日")


def fetch(blog: dict) -> list:
    html = get(blog["url"]).decode("utf-8", errors="replace")

    entries = {}
    for m in ARTICLE_RE.finditer(html):
        url = m.group("href").rstrip("/") + "/"
        title = html_lib.unescape(m.group("title")).strip()
        dm = DATE_RE.match(m.group("date"))
        published = (
            datetime(int(dm.group(1)), int(dm.group(2)), int(dm.group(3))) if dm else None
        )
        entries.setdefault(url, {"title": title, "url": url, "published": published})

    if not entries:
        raise RuntimeError(
            "Figma Engineering: 記事を抽出できなかった(ページ構造が変わった可能性)"
        )
    return list(entries.values())
