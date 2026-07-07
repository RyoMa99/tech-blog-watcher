"""claude.com/ja/blog アダプタ。

フィードが存在しないため、Webflow CMSリストのHTML
(<h2>タイトル</h2><div class="u-text-style-caption...">日付</div> の直後に
記事へのリンク<a href="/ja/blog/...">が続く)から記事を抽出する。
"""

import html as html_lib
import re
from datetime import datetime
from urllib.parse import urljoin

from adapters._http import get

ENTRY_RE = re.compile(
    r'role="listitem" class="marquee_cms_blog_list_item w-dyn-item">'
    r'<div class="marquee_cms_blog_list_item_content"><h2[^>]*>(?P<title>.*?)</h2>'
    r'<div class="u-text-style-caption[^"]*">(?P<date>[^<]+)</div></div>.*?'
    r'href="(?P<href>/ja/blog/[^"]+)"[^>]*class="clickable_link',
    re.DOTALL,
)


def fetch(blog: dict) -> list:
    html = get(blog["url"]).decode("utf-8", errors="replace")

    entries = {}
    for m in ENTRY_RE.finditer(html):
        url = urljoin(blog["url"], m.group("href"))
        try:
            published = datetime.strptime(m.group("date").strip(), "%B %d, %Y")
        except ValueError:
            published = None
        entries.setdefault(url, {
            "title": html_lib.unescape(m.group("title")).strip(),
            "url": url,
            "published": published,
        })

    if not entries:
        raise RuntimeError("claude.com/ja/blog: 記事を抽出できなかった(ページ構造が変わった可能性)")
    return list(entries.values())
