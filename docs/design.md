# tech-blog-watcher 設計書

テックブログの新着記事を毎朝チェックして通知するシステムの設計資料。
2026-07-06 時点で対象45サイト全てに実際にアクセスし、フィードの有無・形式を検証した結果に基づく。

## 1. 要件

- 対象は登録されたテックブログ群(現時点で45サイト)。各ブログの更新頻度は多くて1日1記事程度
- 毎日 **日本時間 08:00** にチェックし、前回チェック以降(≒直近24時間)に追加された新着記事を報告する
- Claude のスケジュール実行環境(routine / scheduled cloud agent)で動かす
- ブログは今後も適宜追加される。**追加コストが最小**であること

## 2. 事前調査の結果サマリ

45サイトに実際にアクセスして確認した内訳:

| 分類 | サイト数 | 内容 |
|---|---|---|
| HTML内にフィード宣言あり | 39 | はてなブログ系 `/feed`、Zennパブリケーション `/p/<name>/feed`、Hugo/静的サイト系 `atom.xml` / `index.xml` など |
| フィード宣言なし・直接発見 | 4 | azukiazusa.dev → `/rss.xml`、Nulab → `/ja/blog/feed/`、Classmethod → `/feed/`、Stripe → `/blog/feed.rss` |
| フィードなし(スクレイプ必要) | 2 | Wantedly stories、inside.dmm.com |

つまり **43/45 サイトは RSS/Atom フィードで確実に取得可能**。全43フィードについて、実際に取得して最新記事の日付が抽出できることを検証済み(§9 の一覧参照)。

### 特殊ケース(4件)

1. **Wantedly stories** — フィードなし。ただしページHTMLに `"published_at":"2026-06-16T11:00:24+09:00"` 形式のJSONが埋め込まれており、確実に抽出できる。なお `<link rel="alternate">` に見える `projects.xml` は求人フィードであり誤り
2. **inside.dmm.com** — フィードなし。Next.js サイトで `__NEXT_DATA__` のJSONから記事一覧を取得する。`sitemap.xml` は存在するが `lastmod` が全URL共通のビルド時刻で新着判定に使えないことを確認済み。**→ 2026-07-07 に監視対象から除外**(実装時にメンテナンス中で検証できず、ユーザー判断で削除)
3. **Google Developers Blog (/ja)** — 日本語版のフィードが存在しない。英語版フィード(`/feeds/posts/default?alt=rss`)は有効だが、**記事アイテムに日付が入っていない**(title / link / description / guid のみ)。→ 日付ではなく既読URL差分で新着判定する。日本語版URLは英語版と同一スラッグ(`/ja/<slug>/`)だが、**翻訳の公開は数週間以上遅れる**(2026-07-07 実装時確認: ENフィード上位10件すべてJA版404)。そのため既読判定キーは常に英語版URLとし、表示リンクはJA版が実在すればJA・なければENにフォールバックする(実装: `adapters/google_ja.py`)
4. **Stripe (engineering)** — engineering カテゴリ限定のフィードがなく、ブログ全体フィード(`/blog/feed.rss`)のみ。engineering ページのHTMLには `datetime` 属性があるためスクレイプも可能だが、engineering 記事は年数本と超低頻度のため、当面は全体フィードで代用しタイトル/URLで目視判別できるレベルのノイズを許容する

### 入力リストの正規化

- `developer.hatenastaff.com` が重複していたため1件に統合
- Henry は記事URL(`https://dev.henry.jp/entry/auto-approval`)だったためブログトップ(`https://dev.henry.jp/`)に正規化

→ 実質 **45サイト** を対象とする(その後 DMM inside を除外し **44サイト**、上記参照)。

## 3. アーキテクチャ

```
GitHubリポジトリ: tech-blog-watcher/
├── blogs.yaml          # ブログ登録簿(追加はここに1エントリ書くだけ)
├── check.py            # チェッカー本体(決定的スクリプト、依存は feedparser 程度)
├── adapters/           # フィードがない/特殊なサイト用の個別アダプタ
│   ├── wantedly.py     #   埋め込みJSONから published_at を抽出
│   └── google_ja.py    #   ENフィード + 既読差分 + JAリンクフォールバック
├── state/seen.json     # 既読記事URL(実行のたびに commit して永続化)
├── reports/            # 日次ダイジェスト(Markdown、日付ファイル名)
└── docs/design.md      # 本書
```

### 役割分担

フィード取得・パース・新着判定は**すべて決定的なスクリプト側**に置く(安く・速く・確実)。Claude routine の役割は以下:

1. `check.py` を実行する
2. 新着記事のダイジェストを整形する(オプションで各記事を読んで1行要約を付与 — Claude 環境で動かす付加価値)
3. `state/seen.json` と `reports/` を commit する
4. **自己修復**: フィードが404になった、サイト構造が変わった等の場合、その場で原因を調査して `blogs.yaml` やアダプタを修正して commit する。これが単純な cron ではなく Claude routine で動かす最大のメリット

## 4. 新着判定ロジック

**「既読URL差分」を主、「24時間窓」を従**とする。

純粋な時刻窓(実行時刻から24時間前まで)だけでは以下の穴がある:

1. Google Developers Blog のようにフィードに日付がないサイトが判定不能
2. 実行が1日失敗すると、その日の記事が永久に取りこぼされる
3. フィード側の日付ずれ(予約投稿の日付繰り上げ等)で漏れ・重複が発生する

そのため:

- **新着 = `state/seen.json` に存在しないURL** を判定の主軸とする
- 日付はダイジェストでの表示とソートに使う
- **初回実行時**は全記事を既読登録して通知ゼロで開始する(過去記事の洪水を防ぐ)
- 実行が遅延・失敗しても次回実行で確実に拾え、重複通知も発生しない(冪等)

挙動としては「毎朝8時、前回チェック以降の新着」となり、要件と実質同一。

### seen.json の形式(案)

```json
{
  "https://tech.layerx.co.jp/entry/xxxx": { "first_seen": "2026-07-07", "blog": "layerx" }
}
```

古いエントリは肥大化防止のため一定期間(例: 180日)で刈り込む。

## 5. blogs.yaml の形式

```yaml
- name: LayerX
  url: https://tech.layerx.co.jp/
  feed: https://tech.layerx.co.jp/feed

- name: Wantedly
  url: https://www.wantedly.com/companies/wantedly/stories
  adapter: wantedly      # feed の代わりに adapter を指定

- name: Google Developers Blog (ja)
  url: https://developers.googleblog.com/ja/
  feed: https://developers.googleblog.com/feeds/posts/default?alt=rss
  adapter: google_ja     # feed + 後処理アダプタの併用
```

### ブログの追加運用

- 基本は `blogs.yaml` に1エントリ追加するだけ
- routine への指示に「URLだけ渡されたらフィードを自動発見して登録する」手順を含めておけば、**Claude に「このブログ追加して」と言うだけで登録できる**。発見手順は本調査と同じ:
  1. ページHTMLの `<link rel="alternate" type="application/(rss|atom)+xml">` を見る
  2. なければ `/feed` `/rss` `/rss.xml` `/atom.xml` `/index.xml` `/feed.xml` 等の定番パスを試す
  3. それでもなければスクレイプアダプタを検討する

## 6. スケジュール実行

- Claude scheduled cloud agent(routine)で cron `0 8 * * *`(Asia/Tokyo)
- 状態(seen.json)とレポートの永続化は本リポジトリへの commit で行う
- routine の1回の実行フロー:
  1. リポジトリを取得
  2. `python check.py` → `reports/YYYY-MM-DD.md` と更新済み `state/seen.json` を生成
  3. 新着があればダイジェストを通知(通知先は §8 未決)
  4. 変更を commit & push
  5. フィード取得に失敗したサイトがあれば調査し、修正を commit(自己修復)

### 代替案(参考)

チェッカー本体は決定的スクリプトなので、GitHub Actions(cron)でも同じことが無料で動く。Claude routine を使う理由は「自己修復」と「要約などの整形」。コスト最適化したくなったら、Actions で日次実行 + 失敗時のみ Claude を呼ぶハイブリッドに移行できる構成にしておく。

## 7. 出力(ダイジェスト)形式

`reports/YYYY-MM-DD.md`:

```markdown
# テックブログ新着 2026-07-07 (3件)

## LayerX
- [記事タイトル](https://tech.layerx.co.jp/entry/xxxx) — 2026-07-06 14:31
## ZOZO
- [記事タイトル](https://techblog.zozo.com/entry/yyyy) — 2026-07-06 11:30
```

新着ゼロの日はレポートを作らない(または「新着なし」の1行)。

## 8. 未決事項

1. **ダイジェストの受け取り方法** — Slack通知(MCP連携) / メール / リポジトリの `reports/` を見に行く、のいずれか。Slack が推奨
2. **記事の1行要約を付けるか** — 付ける場合は routine が各記事を読むためトークンコスト増
3. **Stripe の engineering フィルタ** — 当面は全体フィードで運用し、ノイズが気になればページスクレイプに切り替え

## 9. 対象ブログ一覧(検証済みフィードURL)

2026-07-06 に全URLの取得と最新記事日付の抽出を検証済み。

| # | ブログ | 取得方法 |
|---|---|---|
| 1 | [azukiazusa.dev](https://azukiazusa.dev/blog/) | `https://azukiazusa.dev/rss.xml` |
| 2 | [kakakakakku blog](https://kakakakakku.hatenablog.com/) | `https://kakakakakku.hatenablog.com/feed` |
| 3 | [Future Tech Blog](https://future-architect.github.io/) | `https://future-architect.github.io/atom.xml` |
| 4 | [LayerX](https://tech.layerx.co.jp/) | `https://tech.layerx.co.jp/feed` |
| 5 | [Hatena Developer Blog](https://developer.hatenastaff.com/) | `https://developer.hatenastaff.com/feed` |
| 6 | [MonotaRO](https://tech-blog.monotaro.com/) | `https://tech-blog.monotaro.com/feed` |
| 7 | [konifar-zatsu](https://konifar-zatsu.hatenadiary.jp/) | `https://konifar-zatsu.hatenadiary.jp/feed` |
| 8 | [MIXI (Zenn)](https://zenn.dev/p/mixi) | `https://zenn.dev/p/mixi/feed` |
| 9 | [asken](https://tech.asken.inc/) | `https://tech.asken.inc/feed` |
| 10 | [DRESS CODE (Zenn)](https://zenn.dev/p/dress_code) | `https://zenn.dev/p/dress_code/feed` |
| 11 | [CyberAgent](https://developers.cyberagent.co.jp/blog/) | `https://developers.cyberagent.co.jp/blog/feed/` |
| 12 | [コドモン](https://tech.codmon.com/) | `https://tech.codmon.com/feed` |
| 13 | [Wantedly stories](https://www.wantedly.com/companies/wantedly/stories) | **adapter: wantedly**(埋め込みJSON) |
| 14 | [タイミー](https://tech.timee.co.jp/) | `https://tech.timee.co.jp/feed` |
| 15 | [LINEヤフー](https://techblog.lycorp.co.jp/ja) | `https://techblog.lycorp.co.jp/ja/feed/index.xml` |
| 16 | [SMARTCAMP (Zenn)](https://zenn.dev/p/smartcamp) | `https://zenn.dev/p/smartcamp/feed` |
| 17 | [hacomono](https://techblog.hacomono.jp/) | `https://techblog.hacomono.jp/feed` |
| 18 | [エムスリーキャリア](https://m3career-eng.hatenablog.com/) | `https://m3career-eng.hatenablog.com/feed` |
| 19 | [songmu.jp](https://songmu.jp/riji/) | `https://songmu.jp/riji/atom.xml` |
| 20 | [そーだいなるらくがき帳](https://soudai.hatenablog.com/) | `https://soudai.hatenablog.com/feed` |
| 21 | [シナプス](https://tech.synapse.jp/) | `https://tech.synapse.jp/feed` |
| 22 | [YOUTRUST](https://tech.youtrust.co.jp/) | `https://tech.youtrust.co.jp/feed` |
| 23 | [ZOZO](https://techblog.zozo.com/) | `https://techblog.zozo.com/feed` |
| 24 | [freee](https://developers.freee.co.jp/) | `https://developers.freee.co.jp/feed` |
| 25 | [Findy](https://tech.findy.co.jp/) | `https://tech.findy.co.jp/feed` |
| 26 | [虎の穴ラボ](https://toranoana-lab.hatenablog.com/) | `https://toranoana-lab.hatenablog.com/feed` |
| 27 | [Uzabase](https://tech.uzabase.com/archive/category/blog) | `https://tech.uzabase.com/feed/category/Blog` |
| 28 | [Henry](https://dev.henry.jp/) | `https://dev.henry.jp/feed` |
| 29 | [syu-m-5151](https://syu-m-5151.hatenablog.com/) | `https://syu-m-5151.hatenablog.com/feed` |
| 30 | [bootjp.me](https://bootjp.me/) | `https://bootjp.me/feed` |
| 31 | [blog.inorinrinrin.com](https://blog.inorinrinrin.com/) | `https://blog.inorinrinrin.com/feed` |
| 32 | [BASE](https://devblog.thebase.in/) | `https://devblog.thebase.in/feed` |
| 33 | [DeNA](https://engineering.dena.com/blog/) | `https://engineering.dena.com/blog/index.xml` |
| 34 | [Google Developers Blog (ja)](https://developers.googleblog.com/ja/) | ENフィード + **adapter: google_ja**(日付なし・既読差分判定) |
| 35 | [Netflix TechBlog](https://netflixtechblog.com/) | `https://netflixtechblog.com/feed` |
| 36 | [AWS Japan Blog](https://aws.amazon.com/jp/blogs/news/) | `https://aws.amazon.com/jp/blogs/news/feed/` |
| 37 | [Mercari Engineering](https://engineering.mercari.com/blog/) | `https://engineering.mercari.com/blog/feed.xml` |
| 38 | [コミューン](https://tech.commune.co.jp/) | `https://tech.commune.co.jp/feed` |
| 39 | [Discord Blog](https://discord.com/blog/) | `https://discord.com/blog/rss.xml` |
| 40 | ~~[DMM inside](https://inside.dmm.com/)~~ | 2026-07-07 除外(§2参照) |
| 41 | [CARTA HOLDINGS](https://techblog.cartaholdings.co.jp/) | `https://techblog.cartaholdings.co.jp/feed` |
| 42 | [Nulab](https://nulab.com/ja/blog/) | `https://nulab.com/ja/blog/feed/` |
| 43 | [DevelopersIO](https://dev.classmethod.jp/) | `https://dev.classmethod.jp/feed/` |
| 44 | [Stripe Engineering](https://stripe.com/blog/engineering) | `https://stripe.com/blog/feed.rss`(全体フィードで代用、§2参照) |
| 45 | [STORES Product Blog](https://product.st.inc/) | `https://product.st.inc/feed` |
