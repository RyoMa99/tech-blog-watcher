# tech-blog-watcher

テックブログ(51サイト)の新着記事を毎朝チェックして通知するシステム。
設計の詳細は [docs/design.md](docs/design.md) を参照。

## セットアップ

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## 実行

```sh
.venv/bin/python check.py            # 通常実行
.venv/bin/python check.py --dry-run  # state/レポートを書き込まずに試す
```

- 新着があれば `reports/YYYY-MM-DD.md` を生成し、ダイジェストを標準出力に表示する
- 既読URLは `state/seen.json` に記録される(初回実行は全記事を既読登録して通知ゼロで開始)
- 取得に失敗したブログがあると標準エラーに `FAILED <ブログ名>: <理由>` を出力し、終了コード1で終わる(成功したブログの処理は継続される)

## ブログの追加

`blogs.yaml` に1エントリ追記するだけ:

```yaml
- name: ブログ名
  url: https://example.com/blog/
  feed: https://example.com/blog/feed
```

フィードURLの見つけ方(docs/design.md §5 参照):

1. ページHTMLの `<link rel="alternate" type="application/(rss|atom)+xml">` を見る
2. なければ `/feed` `/rss` `/rss.xml` `/atom.xml` `/index.xml` `/feed.xml` 等の定番パスを試す
3. それでもなければ `adapters/` にスクレイプアダプタを書き、`feed:` の代わりに `adapter: <モジュール名>` を指定する

## 構成

| パス | 役割 |
|---|---|
| `blogs.yaml` | ブログ登録簿 |
| `check.py` | チェッカー本体(既読URL差分で新着判定) |
| `adapters/` | フィードがない/特殊なサイト用アダプタ(wantedly / google_ja / anthropic_news / claude_blog / cursor_blog) |
| `state/seen.json` | 既読記事URL(実行のたびに commit して永続化、180日で刈り込み) |
| `reports/` | 日次ダイジェスト(Markdown) |

## スケジュール実行(Claude routine)

毎日 08:00 JST に以下を実行する:

1. `python check.py` を実行する
2. 新着があればダイジェストを通知する
3. `state/seen.json` と `reports/` の変更を commit & push する
4. 終了コードが1(取得失敗あり)の場合、原因を調査して `blogs.yaml` やアダプタを修正して commit する(自己修復)
