# Memory

## ルールファイル運用方針

- `.claude\rules\` 配下に拡張子ごとのコーディングルールを配置
- CLAUDE.md には共通ルールのみ記載。言語固有ルールは `rules/{拡張子}.md` に書く
- PostToolUse hook によりファイル編集時に対象拡張子のルールが自動注入される
- 新しい拡張子のプロジェクトが増えたら `{拡張子}.md` を新規作成（既存フォーマットに倣う）
- 確認済みルールファイル: python.md, rust.md, markdown.md, ps1.md, git.md, mermaid.md

## ユーザー設定

- Mermaid図はダークモード用テーマを使用（mermaid.md に定義済み）
