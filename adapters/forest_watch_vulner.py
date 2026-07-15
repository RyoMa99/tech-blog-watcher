"""窓の杜 セキュリティ「脆弱性」カテゴリ一覧アダプタ
(forest.watch.impress.co.jp/category/security/vulner/)。

窓の杜のRSSはサイト全体のフィードのみでカテゴリ絞り込みができないため、
カテゴリ一覧ページをスクレイプする。各記事は
<li id="linkid.YYYYMMDD" class="item news ...">...<a href="記事URL">タイトル</a>
という形で並んでおり、li の id に掲載日(YYYYMMDD)が埋め込まれている。
"""

import html as html_lib
import re
from datetime import datetime

from adapters._http import get

ARTICLE_RE = re.compile(
    r'<li id="linkid\.(?P<date>\d{8})"[^>]*>.*?'
    r'href="(?P<href>https://forest\.watch\.impress\.co\.jp/docs/[^"#?]+)">'
    r'(?:<img[^>]*>)?</a></p></div><div class="text"><p class="title">'
    r'<a[^>]*>(?P<title>[^<]+)</a>',
    re.DOTALL,
)


def fetch(blog: dict) -> list:
    html = get(blog["url"]).decode("utf-8", errors="replace")

    entries = {}
    for m in ARTICLE_RE.finditer(html):
        url = m.group("href")
        title = html_lib.unescape(m.group("title")).strip()
        published = datetime.strptime(m.group("date"), "%Y%m%d")
        entries.setdefault(url, {"title": title, "url": url, "published": published})

    if not entries:
        raise RuntimeError(
            "窓の杜 脆弱性: 記事を抽出できなかった(ページ構造が変わった可能性)"
        )
    return list(entries.values())
