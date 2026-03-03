# Plan: `.hooks/README.md` の作成

## Context
`.hooks/` ディレクトリに README.md が存在しないため、フック群の仕様をドキュメント化する。各ファイルの役割・処理フロー・条件分岐を Mermaid 図付きで詳細に記述する。

## 変更対象
- **新規作成**: `.hooks/README.md`

## 内容
全 5 ファイルの詳細説明 + 4 つの Mermaid フローチャート:

1. **全体フロー** (`pre-commit` → Python 3.12 確認 → 各スクリプト実行)
2. **エンコーディング変換フロー** (`pre_commit_encoding.py`: 検出 → decode → CRLF → CP932 encode → atomic write → git add)
3. **Denylist スキャンフロー** (`pre_commit_denylist.py`: combined regex プリスクリーン → 個別パターン再スキャン)
4. **shift_jis_to_cp932.py フロー** (バイナリ走査 → 問題検出 → バイナリコピー → 検証)

## 検証
- README.md が正しく作成されていること
- Mermaid 図が GitHub / VS Code でレンダリングできること (構文の正しさ)
