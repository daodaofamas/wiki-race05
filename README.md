# Wiki Race — 知識を巡る星空

Ver.0.5.2 / STAR MAP BALANCE

日本語版Wikipediaの記事内のリンクをたどり、指定されたゴールを目指すブラウザゲームです。

## ファイル
- `index.html`: ゲーム本体（HTML・CSS・JavaScript）
- `star-map.json`: Wikipediaの正式記事IDと記事名を収録した16ジャンルの拡張星図
- `wrangler.toml`: Cloudflare Workers の静的サイト設定
- `.assetsignore`: 公開対象外ファイル

## 変更履歴

### Ver.0.5.2

- 厳選星図と拡張星図の両方で、かんたんは同ジャンル、ふつう・むずかしいは異なるジャンルから出題します。むずかしいは本文リンクのみです。Wikipediaの完全ランダムと自分で設定するお題はジャンル制限の対象外です。
- 厳選634語を含む5,000語を事前に分類しました。旧拡張星図を使っていた端末では、分類済みの星図を自動で読み込み、旧リストと自己ベストを保持します。

### Ver.0.5.1

- 日本語版Wikipedia APIで厳選634語を照合し、曖昧さ回避ページ8件を置き換えました。リダイレクト先で重複を判定し、無効なランダム出題は選び直します。
- 記事の描画を分割し、リンク一覧は初めて開いた時に生成します。表示用に整形した記事を再利用し、ブラックホールの侵食処理は表示中のリンクに絞りました。
- 主要ボタンのタップ領域を広げ、通信失敗・タイムアウト・無効な記事を区別しました。航行に失敗した場合は、クリック数と履歴を保ったまま再試行またはトップへ戻れます。

## 拡張星図の更新

日本語版Wikipedia APIで各ジャンルの公開カテゴリーに直接属する記事を取得します。追加候補は記事へのリンク数、取得できた直近14日間の閲覧数、記事の長さを参考に優先順位を付けます。曖昧さ回避ページ、リダイレクト、記事以外の名前空間を追加候補から外し、正式記事IDで重複を除きます。

複数ジャンルに一致した記事は、該当カテゴリー数が多いジャンルを優先します。同数なら追加枠の充足率が低いジャンルを優先し、1記事を1ジャンルに登録します。日本の地理に一致した記事は世界の地理の追加候補から外します。ゲームは拡張時に配信済みのデータを読み込み、開始時には出題された2記事をWikipediaに照合します。

```sh
python3 tests/generate_star_map.py --cache /tmp/wiki-race-star-map
```

APIの応答を指定したディレクトリに保存するため、同じディレクトリで中断した生成を再開できます。新しく取得する場合は空のディレクトリを指定してください。

## 回帰テスト

PythonとPlaywrightのChromiumで実行できます。

```sh
python3 -m pip install playwright
python3 -m playwright install chromium
python3 tests/regression.py
```

インストール済みのChromiumを使う場合は、実行時に `CHROMIUM_PATH` で実行ファイルのパスを指定できます。

## Cloudflare Workers Builds
既存の Worker `misty-masuder` を Settings → Builds → Connect から GitHub に接続します。
Production branch: `main` / Root directory: `/` / Build command: 空欄 / Deploy command: `npx wrangler deploy`。
Worker 名が異なる場合は `wrangler.toml` の name を実際の名前に変更してください。

今後は main ブランチへの変更で自動デプロイできます。GitHub に秘密情報を登録する必要はありません。

公式ガイド: https://developers.cloudflare.com/workers/ci-cd/builds/

Wikipedia の記事と画像には各出典・ライセンスが適用されます。ゲームは非公式です。
