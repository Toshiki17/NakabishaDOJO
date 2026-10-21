# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 概要

中飛車の定跡を学ぶ将棋学習ツール「中飛車道場」（単一HTMLファイル）を、SwiftUI + WKWebView で包んだ iPhone アプリ。ビルドツール・パッケージ管理・テスト・リンターはない。

## 編集の流れ

1. アプリの中身は `web/nakabisha_sp.html`（スマホ版）だけ。直すのはここ。
2. `python3 scripts/build_web.py` で `ios/www/`（`index.html`・`fonts.css`・`fonts/`）を作り直す。`ios/www/` は生成物なので手で直さない。生成物もコミットする（アプリはこれを同梱する）。
3. 動作確認はブラウザで `ios/www/index.html` を開くか、Playwright（Chromium は導入済み）で操作する。

- `web/nakabisha.html` は PC 版で、アプリには入らない。ロジックはスマホ版と別コピーなので、片方の修正はもう片方に自動では反映されない。
- `build_web.py` は元HTMLの特定の文字列（`<title>`、`#kifFile` の `accept` 属性、「ブラウザに保存」の文言など）を `replace_once` で置換する。元HTMLのそれらを変えるとスクリプトが止まるので、スクリプト側も合わせて直す。
- フォントは Google Fonts から、ページで使う文字を含むサブセットだけをダウンロードする（ネット接続が必要）。新しい文字を使ったらビルドし直さないと、アプリでその字だけ書体が変わる。

## `web/nakabisha_sp.html` の構造

`<style>` + 1つの `<script>` に全部入っている（約76万バイト）。

- `EV`・`AUTO`（`/*AUTO_DATA*/`）・`OPPDEV`（`/*OPPDEV*/`）は1行で数十万文字ある事前計算データ。ファイル全体や該当行をそのまま読まず、`grep -n` と `cut` で位置を確かめてから部分的に扱う。
- `LINES`（定跡の手順。`U()`/`O()` で手を定義）、`EXT`、`BR` が定跡データ。
- `initial`/`play`/`legality`/`notate` などが盤面ルール、`E`（IIFE）が簡易探索エンジン（`search`・`bestMoves`）。
- 状態は `S`、記録は localStorage キー `nakabisha-dojo3`（クリア記録・腕試しの成績）。キー名を変えると既存ユーザーの記録が消える。

## iOS アプリ（`ios/`）

- `ios/project.yml` は XcodeGen の定義。`.xcodeproj` はコミットせず `cd ios && xcodegen generate` で作る（Mac が必要）。
- `DojoWebView.swift`：同梱ページを `app://local/index.html` という独自スキームで配信（`BundleSchemeHandler`）。`file://` より localStorage が確実に残るため。外部URLは Safari で開き、`alert`/`confirm` はネイティブのダイアログで出す。
- Bundle ID は `io.github.toshiki17.nakabishadojo`。

## CI（`.github/workflows/ios.yml`）

- すべての push / PR で、macOS 上でシミュレータ向けビルド（署名なし）。この環境（Linux）では Swift のビルド確認はできないので、CI の結果で確かめる。
- 手動実行（workflow_dispatch）で、アーカイブして App Store Connect（TestFlight）へアップロード。Secrets `ASC_KEY_ID`・`ASC_ISSUER_ID`・`ASC_KEY_P8`・`APPLE_TEAM_ID` が必要。ストアへ出る操作なので、実行前に必ず確認を取る。

## 画像の書き出し（Playwright）

```sh
NODE_PATH=$(npm root -g) node scripts/render_assets.js       # design/icon.html → AppIcon.png
NODE_PATH=$(npm root -g) node scripts/render_screenshots.js  # ios/www/index.html → appstore/screenshots/
```

スクリーンショットは画面の要素（`#toolbar [data-act=...]`、`[data-mode="test"]`、`#msg .choice` など）を操作して撮るので、UIを変えたらスクリプトも合わせる。

## その他

- `appstore/metadata.md`：App Store の文面。`docs/privacy.md`・`docs/manual.md`：プライバシーポリシーと使い方（サポートURLから参照される）。
- アプリはデータを収集しない前提（`PrivacyInfo.xcprivacy`、ストアの「データの収集なし」）。通信や解析を加えるとこの申告が変わる。
