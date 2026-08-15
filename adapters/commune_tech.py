"""コミューン Tech Blog アダプタ。

tech.commune.co.jp は note.com のマガジン「技術を知る」
(https://note.com/communeinc/m/m048407949a08) にリダイレクトされるようになった。
note.com の全体アカウントRSS (/communeinc/rss) は技術記事以外(広報・イベント告知等)
も混ざるため、マガジンページのReact Server ComponentsペイロードからJSONで
埋め込まれた記事一覧(key/name/noteUrl)を正規表現で抽出する。
公開日は一覧レベルでは取得できないため published は None
(新着判定はURL差分で行われるため問題ない)。
"""

import json
import re

from adapters._http import get

KEY_RE = re.compile(r'\\"key\\":\\"(n[0-9a-f]+)\\"')
NAME_RE = re.compile(r'\\"name\\":\\"((?:[^"\\]|\\.)*?)\\"')
URL_RE = re.compile(r'\\"noteUrl\\":\\"(https://note\.com/[^"\\]+)\\"')
SEARCH_WINDOW = 4000


def _unescape(s: str) -> str:
    return json.loads(f'"{s}"')


def fetch(blog: dict) -> list:
    html = get(blog["url"]).decode("utf-8", errors="replace")

    entries = {}
    for m in KEY_RE.finditer(html):
        key = m.group(1)
        if key in entries:
            continue
        window = html[m.end(): m.end() + SEARCH_WINDOW]
        name_m = NAME_RE.search(window)
        url_m = URL_RE.search(window)
        if not (name_m and url_m):
            continue
        entries[key] = {
            "title": _unescape(name_m.group(1)),
            "url": url_m.group(1),
            "published": None,
        }

    if not entries:
        raise RuntimeError("コミューン: 記事を抽出できなかった(ページ構造が変わった可能性)")
    return list(entries.values())
