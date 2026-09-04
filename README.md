# 愛媛・松山おすすめMAP 〜YouTube旅Vlog & Xのファン投稿から〜

愛媛県（松山・道後・今治・しまなみ・内子・大洲・宇和島）のおすすめスポットを、エリア別に色分けした地図＋一覧にまとめた静的サイト。
スポットをクリックすると出典（YouTube紹介動画の埋め込み / Xポストへのリンク）がモーダルで見られる。

対象イベント: **ぽこぴーの回覧板 in 愛媛**（2026年10月12日・松山市民会館 大ホール）。
地図には会場マーカー（🎤）を置いてある。

出典は2系統:

1. **YouTube旅Vlog 12本**（初期データ、Gemini 動画解析 → 名寄せ → Places 裏取り）
2. **Xの「#ぽこピーの回覧板」愛媛公演 関連のおすすめ投稿**（日次自動収集、下記パイプライン。**2026-10-11 まで**）

公開URL: https://oneliner22.github.io/ehime-osusume-map/

石川版 https://github.com/oneliner22/ishikawa-osusume-map をそのまま愛媛向けに差し替えたもの。
サイト本体・パイプラインの構造は石川版と同一。

## 構成

- `index.html` — アプリ本体。`data/*.json` を実行時に fetch して描画（ビルド工程なし）
- `data/spots.json` — **スポットデータの正本**（エリア/カテゴリ/座標/説明/出典）
- `data/videos.json` — YouTube出典のメタ情報（動画ID → タイトル/チャンネル）
- `data/config.json` — タイトル・リード文・地図中心/ズーム等
- `data/pipeline.json` — 自動収集パイプラインの設定（クエリ/bbox/受入ゲート/モデル/**更新終了日 until**）
- `data/ledger.json` — 処理済みXポストID・著者判定のキャッシュ（二重入稿防止）
- `data/aliases.json` — 略称→正規スポット名
- `data/pending.json` — 受入ゲート不合格で保留になった候補（地図には出ない）
- `validate.py` — データ整合性チェック（`python validate.py`）
- `tools/build_yt_data.py` — 初期データ（YouTube由来）を組み立てた一回きりのスクリプト

`spots.json` のスポットは `sources` 配列で出典を持つ:

```json
{"type": "youtube", "id": "E9-pVHkqCYA"}
{"type": "x", "url": "https://x.com/<handle>/status/<id>", "author": "<handle>", "date": "2026-09-01", "quote": "..."}
```

X出典のURLは必ず **正規形**（`https://x.com/<handle>/status/<id>`）で持つ。
`"embed": false` が付いた出典は、投稿者のアカウント設定（年齢制限）により埋め込みも未ログイン閲覧も
できないポスト（X の oEmbed が 403 を返すかどうかで日次ジョブが毎日判定し直す）。

自動追加スポットは任意で `address` / `hours` / `url` / `place_id` / `added` / `out_of_pref` を持つ。

## エリア

| id | 名前 | 判定 |
|---|---|---|
| matsuyama | 松山市街（松山城・大街道） | 松山市中心部 |
| dogo | 道後温泉 | 道後温泉本館から約1.3km以内 |
| imabari | 今治・しまなみ海道 | 北緯33.95以北・東経132.85以東 |
| toyo | 新居浜・西条・東予 | 東経133.05以東 |
| iyo | 伊予・内子・大洲・久万高原 | 松山の南〜西（下灘・四国カルスト含む） |
| nanyo | 宇和島・南予 | 北緯33.45以南 |
| other | 県外（しまなみ広島側・香川） | 県外だがマージン付きbbox内 |

日次ジョブは Gemini が既存エリアから選び、どれにも属さなければ新エリアを提案する（石川版と同じ）。

## ローカルプレビュー

fetch を使うため file:// では動かない。リポジトリ直下で:

```
python -m http.server
# → http://localhost:8000/
```

編集後は `python validate.py` で整合性チェック。

## 自動収集パイプライン（Cloud Run Jobs、2026-10-11 まで）

日次で以下を実行し、合格スポットを `spots.json` に直接コミットする（人手レビューなし）:

```
Cloud Scheduler → Cloud Run Job (GCP: salmon-chan)
 0. pipeline.json の until (2026-10-11) を過ぎていたら何もせず終了
 1. xdev で X を検索 (回覧板 (愛媛 OR 松山 OR 道後 OR 今治) -is:retweet)、台帳にない新規ポストを取得
 2. 添付画像をダウンロード（おすすめリストは画像内記載が主流）
 3. Gemini (flash lite) が本文+全画像からスポット候補を抽出（実記載チェックで捏造防止）
 3b. 適格投稿の「本人の続き投稿」(自分のリプ・自己引用RT) を同run内で収穫
 4. aliases + 既存スポットと照合。既存なら sources に言及を追記
 5. Google Places API で裏取り（実在/正規名称/住所/座標/営業時間/営業状況）
 6. 受入ゲート（コード強制）:
    - Places 一致（Gemini pro が同一性を判定）
    - business_status = OPERATIONAL
    - マージン付きbbox内 (lat 32.6-34.6 / lng 131.7-134.1)
    - 著者がbotでない
    - 日次300件のサーキットブレーカー（超過時は全停止+Issue起票）
 7. 不合格は pending.json へ。合格分を commit & push（GitHub Pages が自動配信）
```

公式 (@ponpokoka) の「おすすめ教えて」投稿を検知するとシード登録し、そのリプ・引用RTも収穫する。

### 日次 pending 整理（毎日 7:40 JST、日次ジョブ完了後）

保留候補を Gemini のツールループ（Places再検索・出典ポスト再読）で精査して回収する。
掲載可否の最終判定（place_id の実在根拠・営業状況・bbox）はコード側で強制する。

実装は `pipeline/` 配下（石川版と同じファイル構成）:

- `daily_job.py` — 日次ジョブ本体
- `pending_resolver.py` — 日次 pending 整理ジョブ
- `mcp_client.py` — xdev MCP (streamable HTTP) の最小クライアント
- `refresh_hours.py` — 営業時間を週7日ぶんに入れ直す一回きりのジョブ
- `backfill_places.py` — 既存スポットの Places 裏取り（初期データに使用）
- `deploy.sh` — salmon-chan へのデプロイ一式。Secret (github-token / xdev-mcp-url / places-api-key) は
  石川版と共用なので `SKIP_SECRETS=1 ./pipeline/deploy.sh` で足りる

初回バックフィル（告知〜デプロイ日までの投稿を一括処理）は環境変数で:

```
INGEST_SINCE=2026-03-05T00:00:00Z DAILY_CAP=2000 python pipeline/daily_job.py   # 半年分・10日窓でフルアーカイブ検索
```

運用コマンド:

```
# 手動実行
gcloud run jobs execute ehime-spots-daily --region asia-northeast1 --project central-bulwark-427114-j7 --wait
# ログ確認
gcloud logging read 'resource.type=cloud_run_job AND resource.labels.job_name=ehime-spots-daily' --project central-bulwark-427114-j7 --limit 50 --format 'value(textPayload)'
# 更新期間終了後の後始末 (until 以降ジョブは即終了するので急がなくてよい)
gcloud scheduler jobs delete ehime-spots-daily-trigger --location asia-northeast1 --project central-bulwark-427114-j7
gcloud scheduler jobs delete ehime-spots-pending-trigger --location asia-northeast1 --project central-bulwark-427114-j7
```

失敗・サーキットブレーカー・validate 不合格時は GitHub Issue が自動起票される。

## 出典・クレジット

スポット情報は以下の旅Vlogおよび X のファン投稿に基づく（著作権は各投稿者に帰属）:
華金カップル / KaoruTV / 旅行の達人ヒガキン社長 / ヒガキン社長のグルメ名店巡り / bien旅行 / 平凡な夫婦 /
とももぐ / 中尾明慶のきつねさーん / ドライブ旅行チャンネル / さまぁ〜ずチャンネル / Maibaru Travel

座標は Google Places / 公式サイト等で裏取り。番地が確定できないものは「およその位置」と明記。
