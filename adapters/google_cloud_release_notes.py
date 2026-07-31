"""Google Cloud Release Notes アダプタ。

このフィードは1日1アイテムで、タイトルは "July 28, 2026" のような日付のみ。
実際の変更内容(その日リリースされた全プロダクトの変更点)はアイテム本文に
HTMLで丸ごと入っているが、通常の fetch_feed_entries は title/link/published
しか見ないため中身が読み捨てられてしまう。ここでは本文を簡易Markdown化して
"body" として返し、check.py 側でレポート内に <details> ブロックとして
直接埋め込ませる。
"""

from datetime import datetime, timezone
import html as html_lib
import re

import feedparser

from adapters._http import get

TAG_LI = re.compile(r"<li[^>]*>(.*?)</li>", re.DOTALL)
TAG_H2 = re.compile(r"<h2[^>]*>(.*?)</h2>", re.DOTALL)
TAG_H3 = re.compile(r"<h3[^>]*>(.*?)</h3>", re.DOTALL)
TAG_P = re.compile(r"<p[^>]*>(.*?)</p>", re.DOTALL)
TAG_ANY = re.compile(r"<[^>]+>")


def _text(fragment: str) -> str:
    text = TAG_ANY.sub("", fragment)
    text = html_lib.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _to_markdown(raw_html: str) -> str:
    working = TAG_LI.sub(lambda m: f"\n- {_text(m.group(1))}", raw_html)
    working = TAG_H2.sub(lambda m: f"\n\n## {_text(m.group(1))}\n", working)
    working = TAG_H3.sub(lambda m: f"\n### {_text(m.group(1))}\n", working)
    working = TAG_P.sub(lambda m: f"\n{_text(m.group(1))}\n", working)
    working = TAG_ANY.sub("", working)
    working = html_lib.unescape(working)
    lines = [line.rstrip() for line in working.splitlines()]
    cleaned = []
    for line in lines:
        if line == "" and cleaned and cleaned[-1] == "":
            continue
        cleaned.append(line)
    return "\n".join(cleaned).strip()


def fetch(blog: dict) -> list:
    parsed = feedparser.parse(get(blog["feed"]))
    if parsed.bozo and not parsed.entries:
        raise RuntimeError(f"Google Cloud Release Notes: フィードをパースできなかった: {parsed.bozo_exception}")

    entries = []
    for e in parsed.entries:
        link = e.get("link")
        title = e.get("title")
        if not (link and title):
            continue
        raw_html = ""
        if e.get("content"):
            raw_html = e["content"][0].get("value", "")
        if not raw_html:
            raw_html = e.get("summary", "")
        published = None
        st = e.get("updated_parsed") or e.get("published_parsed")
        if st:
            published = datetime(*st[:6], tzinfo=timezone.utc)
        entries.append({
            "title": title,
            "url": link,
            "id": link,
            "published": published,
            "body": _to_markdown(raw_html) if raw_html else None,
        })

    if not entries:
        raise RuntimeError("Google Cloud Release Notes: フィードに記事が1件もない")
    return entries
