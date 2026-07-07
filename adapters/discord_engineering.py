"""Discord Engineering カテゴリ (discord.com/category/engineering) アダプタ。

全体フィード /blog/rss.xml にはカテゴリ情報が無いため、engineeringカテゴリの
一覧ページ(WebflowのサーバレンダリングHTML)から記事カード
(<a aria-label="タイトル" href="/blog/slug" ...>)を正規表現で抽出する。
カードに公開日は含まれない("December 8, 2025" 風の文字列はPatch Notes系
記事のタイトルの一部)ため published は None
(新着判定はURL差分で行われるため問題ない)。
"""

import html as html_lib
import re
from urllib.parse import urljoin

from adapters._http import get

CARD_RE = re.compile(r'<a aria-label="(?P<title>[^"]+)" href="(?P<href>/blog/[^"?#]+)"')


def fetch(blog: dict) -> list:
    html = get(blog["url"]).decode("utf-8", errors="replace")

    entries = {}
    for m in CARD_RE.finditer(html):
        url = urljoin(blog["url"], m.group("href"))
        entries.setdefault(url, {
            "title": html_lib.unescape(m.group("title")).strip(),
            "url": url,
            "published": None,
        })

    if not entries:
        raise RuntimeError("Discord Engineering: 記事を抽出できなかった(ページ構造が変わった可能性)")
    return list(entries.values())
