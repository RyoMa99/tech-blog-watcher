"""Google Developers Blog (日本語版) アダプタ。

日本語版のフィードが存在しないため英語版フィードを読む。
英語版フィードの記事アイテムには日付がない(title/link/description/guidのみ)ので
published は None を返し、新着判定は既読URL差分に委ねる。

日本語版URLは英語版と同一スラッグ(/ja/<slug>/)だが、翻訳の公開は
数週間〜それ以上遅れる(2026-07-07 確認: ENフィード上位10件すべてJA版404)。
そのため:
- 既読判定キー(id)は常に英語版URL — JA版が後日公開されても重複通知しない
- 表示リンク(url)はJA版が実在すればJA、なければENにフォールバック
"""

import urllib.request

import feedparser

from adapters._http import USER_AGENT, get

JA_PREFIX = "https://developers.googleblog.com/ja/"


def _ja_url_if_exists(link: str):
    slug = link.rstrip("/").rsplit("/", 1)[-1]
    ja_url = f"{JA_PREFIX}{slug}/"
    req = urllib.request.Request(ja_url, method="HEAD", headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=10) as res:
            if res.status == 200:
                return ja_url
    except Exception:
        pass
    return None


def fetch(blog: dict) -> list:
    parsed = feedparser.parse(get(blog["feed"]))
    if parsed.bozo and not parsed.entries:
        raise RuntimeError(f"Google Developers Blog: フィードをパースできなかった: {parsed.bozo_exception}")

    entries = []
    for e in parsed.entries:
        link = e.get("link")
        title = e.get("title")
        if not (link and title):
            continue
        entries.append({
            "title": title,
            "url": _ja_url_if_exists(link) or link,
            "id": link,
            "published": None,
        })

    if not entries:
        raise RuntimeError("Google Developers Blog: フィードに記事が1件もない")
    return entries
