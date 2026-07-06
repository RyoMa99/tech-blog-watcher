"""HTTP取得の共通ヘルパー。check.py と各アダプタから使う。"""

import gzip
import time
import urllib.request

USER_AGENT = (
    "Mozilla/5.0 (compatible; tech-blog-watcher/1.0; "
    "+https://github.com/RyoMa99/tech-blog-watcher)"
)

DEFAULT_TIMEOUT = 30


RETRIES = 2  # 一時的なDNS失敗・タイムアウト対策


def get(url: str, timeout: int = DEFAULT_TIMEOUT) -> bytes:
    """URLをGETしてボディを返す。リダイレクトは urllib が追従する。"""
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "*/*",
            "Accept-Encoding": "gzip",
        },
    )
    last_exc = None
    for attempt in range(RETRIES + 1):
        if attempt:
            time.sleep(2 * attempt)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as res:
                body = res.read()
                if res.headers.get("Content-Encoding") == "gzip":
                    body = gzip.decompress(body)
                return body
        except Exception as exc:
            last_exc = exc
    raise last_exc
