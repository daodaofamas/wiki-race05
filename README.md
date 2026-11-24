# Wiki Race — 知識を巡る星空

Ver.0.5 / FLIGHT GUIDE

日本語版Wikipediaの記事内のリンクをたどり、指定されたゴールを目指すブラウザゲームです。

## ファイル
- `index.html`: ゲーム本体（HTML・CSS・JavaScript）
- `wrangler.toml`: Cloudflare Workers の静的サイト設定
- `.assetsignore`: 公開対象外ファイル

## Cloudflare Workers Builds
既存の Worker `misty-masuder` を Settings → Builds → Connect から GitHub に接続します。
Production branch: `main` / Root directory: `/` / Build command: 空欄 / Deploy command: `npx wrangler deploy`。
Worker 名が異なる場合は `wrangler.toml` の name を実際の名前に変更してください。

今後は main ブランチへの変更で自動デプロイできます。GitHub に秘密情報を登録する必要はありません。

公式ガイド: https://developers.cloudflare.com/workers/ci-cd/builds/

Wikipedia の記事と画像には各出典・ライセンスが適用されます。ゲームは非公式です。
