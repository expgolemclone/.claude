# qutebrowser + Bitwarden CLI パスワード自動入力セットアップ

## Context
qutebrowserでID/パスワードが自動入力されない問題を解決する。
GUI版Bitwardenは導入済み。Bitwarden CLI (bw) も既にインストール済み。

## やること

### 1. qute-bitwarden userscript を配置
- 公式リポジトリから `qute-bitwarden` スクリプトをダウンロード
- `~/AppData/Roaming/qutebrowser/data/userscripts/` に配置

### 2. バッチラッパー作成 (Windows必須)
- 同ディレクトリに `qute-bitwarden.bat` を作成
- Python経由で `qute-bitwarden` を呼び出す

### 3. config.py にキーバインド追加
- `~/AppData/Roaming/qutebrowser/config/config.py` に `Alt+p` バインドを追記

### 4. 使い方メモ
- 初回: `bw login` でログイン → セッションキー取得
- 以降: ログインページで `Alt+p` を押す

## 対象ファイル
- `~/AppData/Roaming/qutebrowser/data/userscripts/qute-bitwarden` (新規)
- `~/AppData/Roaming/qutebrowser/data/userscripts/qute-bitwarden.bat` (新規)
- `~/AppData/Roaming/qutebrowser/config/config.py` (編集)

## 検証
1. qutebrowserを再起動
2. `bw login` & `bw unlock` でセッションキーを設定
3. 対象サイトで `Alt+p` を押して自動入力されることを確認
