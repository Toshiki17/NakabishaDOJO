# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 概要

中飛車の定跡を学ぶ将棋学習ツール「中飛車道場」（単一HTMLファイル）を、SwiftUI + WKWebView で包んだ iPhone アプリ。ビルドツール・リンターはない。テストは Playwright（`npm test`）。

## 編集の流れ

1. アプリの中身は `web/nakabisha.html` の1ファイルだけ。直すのはここ（以前あった PC 版・スマホ版の2本立ては廃止し、スマホ版に統一した）。
2. `python3 scripts/build_web.py` で `ios/www/`（`index.html`・`fonts.css`・`fonts/`）を作り直す。`ios/www/` は生成物なので手で直さない。生成物もコミットする（アプリはこれを同梱する）。
3. `npm test` で確かめる（初回は `npm install`）。

- `build_web.py` は元HTMLの特定の文字列（`#kifFile` の `accept` 属性、「ブラウザにだけ保存」の文言）を `replace_once` で置換する。元HTMLのそれらを変えるとスクリプトが止まるので、スクリプト側も合わせて直す。
- フォントは Google Fonts から、ページで使う文字を含むサブセットだけをダウンロードする（ネット接続が必要）。新しい文字を使ったらビルドし直さないと、アプリでその字だけ書体が変わる。

## `web/nakabisha.html` の構造

`<style>` + 1つの `<script>` に全部入っている（約76万バイト）。

- `EV`・`AUTO`（`/*AUTO_DATA*/`）・`OPPDEV`（`/*OPPDEV*/`）は1行で数十万文字ある事前計算データ。ファイル全体や該当行をそのまま読まず、`grep -n` と `cut` で位置を確かめてから部分的に扱う。
- `LINES`（定跡の手順。`U()`/`O()` で手を定義）、`EXT`、`BR` が定跡データ。
- 定跡ツリーはページ読み込み時に組み立てる：`LINES` の `seq` を `buildSeq` で木にし、`EXT`（延長）と `BR`（分岐）を接ぎ木。腕試しは `AUTO`（AIの変化）も足す。`buildSeq` は合法手か確かめないので、打ち間違いはテストで見つける。
- `EV` は水匠で事前計算した評価値（キーは初期局面からの手順を空白区切りにした文字列、値は `top`（上位手・評価値・読み筋）と `all`）。
- `finish`・`setMode` などは後ろで同名関数を定義し直している箇所がある（後の定義が有効）。
- `initial`/`play`/`legality`/`notate` などが盤面ルール、`E`（IIFE）が簡易探索エンジン（`search`・`bestMoves`）。
- 状態は `S`、記録は localStorage キー `nakabisha-dojo3`（クリア記録・腕試しの成績）。キー名を変えると既存ユーザーの記録が消える。

## テスト（`tests/`）

- `npm test`（Node の `node:test` + Playwright）。ページは `ios/www/index.html` を開くので、先にビルドしておく（`build.test.js` が作り直し忘れを検出する）。
- 1ファイルだけ：`node --test tests/data.test.js`。1件だけ：`node --test --test-name-pattern='二歩' tests/rules.test.js`。
- `data.test.js`：定跡・EV・AUTO・OPPDEV のすべての手と読み筋が合法か（成り・不成の条件も）。`rules.test.js`：盤面ルールとエンジン。`ui.test.js`：タップ操作・最後まで進める・腕試し・KIF読み込み。
- ページの関数・変数（`LINES`、`S`、`legality` など）は `page.evaluate` から直接呼べる。
- CI は `.github/workflows/test.yml`（Ubuntu）。

## iOS アプリ（`ios/`）

- `ios/project.yml` は XcodeGen の定義。`.xcodeproj` はコミットせず `cd ios && xcodegen generate` で作る（Mac が必要）。
- `DojoWebView.swift`：同梱ページを `app://local/index.html` という独自スキームで配信（`BundleSchemeHandler`）。`file://` より localStorage が確実に残るため。外部URLは Safari で開き、`alert`/`confirm` はネイティブのダイアログで出す。
- Bundle ID は `io.github.toshiki17.nakabishadojo`。

## CI・公開（`.github/workflows/`）

- `pages.yml`：`main` への push で `ios/www/` を GitHub Pages（https://toshiki17.github.io/NakabishaDOJO/）に公開する。誰でも見られる公開ページなので、`main` に入れる＝公開になる。

`ios.yml`：

- すべての push / PR で、macOS 上でシミュレータ向けビルド（署名なし）。この環境（Linux）では Swift のビルド確認はできないので、CI の結果で確かめる。
- 手動実行（workflow_dispatch）で、アーカイブして App Store Connect（TestFlight）へアップロード。Secrets `ASC_KEY_ID`・`ASC_ISSUER_ID`・`ASC_KEY_P8`・`APPLE_TEAM_ID` が必要。ストアへ出る操作なので、実行前に必ず確認を取る。

## 画像の書き出し（Playwright）

```sh
node scripts/render_assets.js       # design/icon.html → AppIcon.png
node scripts/render_screenshots.js  # ios/www/index.html → appstore/screenshots/
```

スクリーンショットは画面の要素（`#toolbar [data-act=...]`、`[data-mode="test"]`、`#msg .choice` など）を操作して撮るので、UIを変えたらスクリプトも合わせる。

## ShogiGUI の KIF（定跡の打ち込み元）

定跡はユーザーが ShogiGUI で打ち込んだ KIF から取り込む予定（変換スクリプトは未作成）。実際の書き出しで確認した形式：

- 文字コードは Shift-JIS（CP932）。`iconv -f CP932 -t UTF-8` で読む。
- 分岐は本線のあとに `変化：N手` の区切りで続く。アプリの `parseKif` は `変化` で読むのをやめるので、分岐は読めない。
- `*` で始まる行はその直前の手へのコメント。`*分岐:` は分岐名。`*一致率 …` は ShogiGUI が自動で付ける行なので解説ではない。
- `**解析 0 …` は棋譜解析の結果（評価値・読み筋）で、その直前の手を指したあとの局面のもの。棋譜の先頭の `**解析` は初期局面のもの。`○` が付くと実戦の手がエンジンの最善手と一致。

## その他

- `appstore/metadata.md`：App Store の文面。`docs/privacy.md`・`docs/manual.md`：プライバシーポリシーと使い方（サポートURLから参照される）。
- アプリはデータを収集しない前提（`PrivacyInfo.xcprivacy`、ストアの「データの収集なし」）。通信や解析を加えるとこの申告が変わる。
