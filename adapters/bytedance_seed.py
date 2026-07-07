"""ByteDance Seed Blog (seed.bytedance.com/en/blog) アダプタ。

フィードがなく記事カードに<a href>もない(JSナビゲーション)ため、SSRページに
埋め込まれた _ROUTER_DATA スクリプト内JSONの
"article_list":[{"ArticleMeta": {"PublishDate": ミリ秒エポック, ...},
"ArticleSubContentEn": {"Title": ..., "TitleKey": スラッグ}, ...}] 配列から抽出する。
英語版は ArticleSubContentEn のみを見る(ArticleSubContentZh は中国語版なので使わない)。
記事URLは https://seed.bytedance.com/en/blog/<TitleKey>。
"""

import json
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

from adapters._http import get

MARKER = '"article_list":['
NON_ASCII_RE = re.compile(r"[^\x00-\x7f]")  # 中国語スラッグの混入除け


def fetch(blog: dict) -> list:
    html = get(blog["url"]).decode("utf-8", errors="replace")

    entries = {}
    decoder = json.JSONDecoder()
    pos = 0
    while True:
        idx = html.find(MARKER, pos)
        if idx == -1:
            break
        try:
            articles, _ = decoder.raw_decode(html, idx + len(MARKER) - 1)
        except json.JSONDecodeError:
            pos = idx + len(MARKER)
            continue
        for article in articles:
            if not isinstance(article, dict):
                continue
            meta = article.get("ArticleMeta") or {}
            content_en = article.get("ArticleSubContentEn") or {}
            title = (content_en.get("Title") or "").strip()
            title_key = (content_en.get("TitleKey") or "").strip()
            if not (title and title_key) or NON_ASCII_RE.search(title_key):
                continue
            url = urljoin(blog["url"], f"/en/blog/{title_key}")
            publish_ms = meta.get("PublishDate")
            if isinstance(publish_ms, (int, float)) and publish_ms > 0:
                published = datetime.fromtimestamp(publish_ms / 1000, tz=timezone.utc)
            else:
                published = None
            entries.setdefault(url, {"title": title, "url": url, "published": published})
        pos = idx + len(MARKER)

    if not entries:
        raise RuntimeError("ByteDance Seed: 埋め込みJSONから記事を抽出できなかった(ページ構造が変わった可能性)")
    return list(entries.values())
