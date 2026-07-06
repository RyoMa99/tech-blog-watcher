#!/usr/bin/env python3
"""tech-blog-watcher チェッカー本体。

blogs.yaml の各ブログからフィード(またはアダプタ)で記事一覧を取得し、
state/seen.json にないURLを新着として reports/YYYY-MM-DD.md に出力する。

- 新着判定の主軸は既読URL差分。日付は表示とソートにのみ使う(docs/design.md §4)
- 初回実行(seen.json なし)は全記事を既読登録して通知ゼロで開始する
- 取得に失敗したブログがあっても他は処理し、終了コード1で失敗を知らせる

使い方:
    python check.py [--dry-run]   # --dry-run: seen.json とレポートを書き込まない
"""

import argparse
import importlib
import json
import sys
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

import feedparser
import yaml

from adapters._http import get

ROOT = Path(__file__).resolve().parent
BLOGS_PATH = ROOT / "blogs.yaml"
SEEN_PATH = ROOT / "state" / "seen.json"
REPORTS_DIR = ROOT / "reports"

JST = timezone(timedelta(hours=9), "JST")
SEEN_RETENTION_DAYS = 180
MAX_WORKERS = 10


def fetch_feed_entries(blog: dict) -> list:
    """RSS/Atomフィードから記事一覧を取得する。"""
    parsed = feedparser.parse(get(blog["feed"]))
    if parsed.bozo and not parsed.entries:
        raise RuntimeError(f"フィードをパースできなかった: {parsed.bozo_exception}")
    if not parsed.entries:
        raise RuntimeError("フィードに記事が1件もない")

    entries = []
    for e in parsed.entries:
        link = e.get("link")
        title = e.get("title")
        if not (link and title):
            continue
        published = None
        for key in ("published_parsed", "updated_parsed"):
            st = e.get(key)
            if st:
                published = datetime(*st[:6], tzinfo=timezone.utc)
                break
        entries.append({"title": title, "url": link, "published": published})
    return entries


def fetch_blog(blog: dict) -> list:
    if "adapter" in blog:
        mod = importlib.import_module(f"adapters.{blog['adapter']}")
        entries = mod.fetch(blog)
    else:
        entries = fetch_feed_entries(blog)
    # naiveな日付はJST扱いに正規化しておく(比較・表示のため)
    for entry in entries:
        p = entry.get("published")
        if p is not None and p.tzinfo is None:
            entry["published"] = p.replace(tzinfo=JST)
    return entries


def load_seen() -> dict:
    if SEEN_PATH.exists():
        return json.loads(SEEN_PATH.read_text(encoding="utf-8"))
    return {}


def prune_seen(seen: dict, current_urls: set, today: datetime.date) -> dict:
    """古い既読エントリを削除する。ただし現在もフィードに載っているURLは
    削除しない(削除すると次回また新着扱いになるため)。"""
    cutoff = today - timedelta(days=SEEN_RETENTION_DAYS)
    kept = {}
    for url, meta in seen.items():
        if url in current_urls:
            kept[url] = meta
            continue
        try:
            first_seen = datetime.strptime(meta["first_seen"], "%Y-%m-%d").date()
        except (KeyError, ValueError):
            first_seen = today  # 壊れたエントリは今日付で保持
        if first_seen >= cutoff:
            kept[url] = meta
    return kept


def format_report(date_str: str, new_by_blog: list) -> str:
    total = sum(len(entries) for _, entries in new_by_blog)
    lines = [f"# テックブログ新着 {date_str} ({total}件)", ""]
    for blog_name, entries in new_by_blog:
        lines.append(f"## {blog_name}")
        for e in sorted(
            entries, key=lambda e: e["published"] or datetime.min.replace(tzinfo=JST), reverse=True
        ):
            if e["published"]:
                stamp = e["published"].astimezone(JST).strftime("%Y-%m-%d %H:%M")
                lines.append(f"- [{e['title']}]({e['url']}) — {stamp}")
            else:
                lines.append(f"- [{e['title']}]({e['url']})")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="seen.json とレポートを書き込まない")
    args = parser.parse_args()

    blogs = yaml.safe_load(BLOGS_PATH.read_text(encoding="utf-8"))
    seen = load_seen()
    first_run = not seen
    now = datetime.now(JST)
    today = now.date()
    date_str = today.isoformat()

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = [(blog, pool.submit(fetch_blog, blog)) for blog in blogs]
        results = []  # (blog, entries or None)
        failures = []  # (blog, error message)
        for blog, future in futures:
            try:
                results.append((blog, future.result()))
            except Exception as exc:  # 個別の失敗は全体を止めない
                failures.append((blog, f"{type(exc).__name__}: {exc}"))
                traceback.print_exc(file=sys.stderr)

    new_by_blog = []  # blogs.yaml の順
    current_urls = set()
    new_count = 0
    for blog, entries in results:
        new_entries = []
        for e in entries:
            # 既読判定キー。通常はURLそのもの。表示URLが不安定なサイト
            # (google_ja など)はアダプタが安定した id を別途返す
            key = e.get("id") or e["url"]
            current_urls.add(key)
            if key not in seen:
                seen[key] = {"first_seen": date_str, "blog": blog["name"]}
                new_entries.append(e)
        if new_entries:
            new_by_blog.append((blog["name"], new_entries))
            new_count += len(new_entries)

    seen = prune_seen(seen, current_urls, today)

    if not args.dry_run:
        SEEN_PATH.parent.mkdir(parents=True, exist_ok=True)
        SEEN_PATH.write_text(
            json.dumps(seen, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    if first_run:
        print(f"初回実行: {len(seen)}件を既読登録した(通知なしで開始)")
    elif new_count == 0:
        print(f"新着なし ({len(results)}/{len(blogs)} ブログをチェック)")
    else:
        report = format_report(date_str, new_by_blog)
        if not args.dry_run:
            REPORTS_DIR.mkdir(parents=True, exist_ok=True)
            report_path = REPORTS_DIR / f"{date_str}.md"
            if report_path.exists():
                # 同日の再実行では既存レポートを消さず追記する
                existing = report_path.read_text(encoding="utf-8").rstrip()
                report_path.write_text(f"{existing}\n\n---\n\n{report}", encoding="utf-8")
            else:
                report_path.write_text(report, encoding="utf-8")
            print(f"レポート: {report_path.relative_to(ROOT)}")
        print(report)

    if failures:
        print(f"\n取得失敗 {len(failures)}件:", file=sys.stderr)
        for blog, msg in failures:
            print(f"  FAILED {blog['name']}: {msg}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
