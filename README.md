# Wiki Race — 知識を巡る星空

Ver.0.5.1 / STABILITY UPDATE

日本語版Wikipediaの記事内のリンクをたどり、指定されたゴールを目指すブラウザゲームです。

## ファイル
- `index.html`: ゲーム本体（HTML・CSS・JavaScript）
- `wrangler.toml`: Cloudflare Workers の静的サイト設定
- `.assetsignore`: 公開対象外ファイル

## 変更履歴

### Ver.0.5.1

- 日本語版Wikipedia APIで厳選634語を照合し、曖昧さ回避ページ8件を置き換えました。リダイレクト先で重複を判定し、無効なランダム出題は選び直します。
- 記事の描画を分割し、リンク一覧は初めて開いた時に生成します。表示用に整形した記事を再利用し、ブラックホールの侵食処理は表示中のリンクに絞りました。
- 主要ボタンのタップ領域を広げ、通信失敗・タイムアウト・無効な記事を区別しました。航行に失敗した場合は、クリック数と履歴を保ったまま再試行またはトップへ戻れます。

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
