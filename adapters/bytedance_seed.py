"""ByteDance Seed Blog (seed.bytedance.com/en/blog) アダプタ。

サイトが完全なクライアントサイドレンダリング(SSRに記事データを埋め込まない構成)へ
移行したため、フロントJS (main.*.js) が呼んでいる内部API
GET /api/get_article_list_v2?article_type=2&count=&page_token=0&order_desc=true
から直接取得する。レスポンスは
{"sub_article_list": [{"ArticleMeta": {"PublishDate": ミリ秒エポック, ...},
"ArticleSubContentEn": {"Title": ..., "TitleKey": スラッグ}, ...}], "has_more": bool,
"total": int} で、article_type=2 が Blog(1 は Publication)。
英語版は ArticleSubContentEn のみを見る(ArticleSubContentZh は中国語版なので使わない)。
記事URLは https://seed.bytedance.com/en/blog/<TitleKey>。
"""

import json
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

from adapters._http import get

API_URL = "https://seed.bytedance.com/api/get_article_list_v2?article_type=2&count=50&page_token=0&order_desc=true"
NON_ASCII_RE = re.compile(r"[^\x00-\x7f]")  # 中国語スラッグの混入除け


def fetch(blog: dict) -> list:
    body = get(API_URL)
    try:
        data = json.loads(body)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"ByteDance Seed: APIレスポンスがJSONとして解釈できなかった({exc})") from exc

    entries = {}
    for article in data.get("sub_article_list") or []:
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

    if not entries:
        raise RuntimeError("ByteDance Seed: APIから記事を抽出できなかった(レスポンス構造が変わった可能性)")
    return list(entries.values())
