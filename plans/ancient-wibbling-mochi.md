# mpv.net で YouTube プレイリストの自動連続再生を有効化

## Context
mpv はデフォルトで YouTube プレイリストURL を受け取っても単一動画のみ再生する。`ytdl-raw-options=yes-playlist=` を mpv.conf に設定することで、yt-dlp にプレイリスト全体を展開させ、連続自動再生を実現する。

## 対象ファイル
- `C:\Users\0000250059\AppData\Roaming\mpv.net\mpv.conf`（新規作成）

## 変更内容
```
ytdl-raw-options=yes-playlist=
```

## 検証手順
1. プレイリスト付きURL でmpvnet を起動
2. 1曲目の再生終了後、自動的に次の曲が再生されることを確認
