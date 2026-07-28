"""Google Cloud "What's new with Google Cloud" アダプタ。

対象ページは個別記事ではなく、週ごとの見出し(<h3>Jul 20 - Jul 24</h3>)の下に
<li> で項目が並ぶ単一の常時更新ページ。項目に個別URLが無いため、
週見出し+項目テキストのハッシュを既読判定キー(id)として使う。
表示リンクはページ自体を指す。
"""

import hashlib
import html as html_lib
import re

from adapters._http import get

WEEK_RE = re.compile(r"<h3>(?P<week>[^<]+)</h3>\s*<ul>(?P<items>.*?)</ul>", re.DOTALL)
LI_RE = re.compile(r"<li>(?P<body>.*?)</li>", re.DOTALL)
STRONG_RE = re.compile(r"<strong>(?P<title>.*?)</strong>", re.DOTALL)
TAG_RE = re.compile(r"<[^>]+>")


def _clean(fragment: str) -> str:
    text = TAG_RE.sub(" ", fragment)
    text = html_lib.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def fetch(blog: dict) -> list:
    html = get(blog["url"]).decode("utf-8", errors="replace")

    entries = []
    for week_m in WEEK_RE.finditer(html):
        week = _clean(week_m.group("week"))
        for li_m in LI_RE.finditer(week_m.group("items")):
            body = li_m.group("body")
            title_m = STRONG_RE.search(body)
            title = _clean(title_m.group("title")) if title_m else _clean(body)[:120]
            if not title:
                continue
            key_src = f"{week}|{title}"
            entry_id = hashlib.sha1(key_src.encode("utf-8")).hexdigest()
            entries.append({
                "title": f"[{week}] {title}",
                "url": blog["url"],
                "id": entry_id,
                "published": None,
            })

    if not entries:
        raise RuntimeError(
            "Google Cloud What's New: 記事を抽出できなかった(ページ構造が変わった可能性)"
        )
    return entries
