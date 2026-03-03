簡潔に書きます。

---

## 指示: Claude Code ルールファイルの運用について

`.claude\rules\` 配下に、拡張子ごとのコーディングルールを配置しました。

```
.claude\rules\
├── cs.md      # C# 規約
├── c.md       # C 規約
├── md.md      # Markdown 規約
└── ...
```

### 運用ルール

1. **CLAUDE.md には共通ルールのみ記載する。** 言語固有のルールは該当する `rules\{拡張子}.md` に書くこと。
2. **ルールを追加・変更したい場合は該当ファイルを直接編集する。** CLAUDE.md を肥大化させない。
3. **新しい拡張子のプロジェクトが増えた場合は `{拡張子}.md` を新規作成する。** 既存ファイルのフォーマットに倣うこと。

### 仕組み（参考）

PostToolUse hookにより、Claudeがファイルを編集した際に対象の拡張子を判定し、該当するルールファイルの内容をコンテキストに自動注入しています。CLAUDE.md 本体のサイズを抑えつつ、必要なルールだけが適用される構成です。

以上。不明点があれば聞いてください。

---
## 条件付きコンテキスト注入をhookで実現
PreToolUse hookで特定拡張子のファイル編集を検知したら、hookの出力（stdout）で追加のルールやプロンプトを返す。hookのstdoutはClaudeへのフィードバックとして渡されます。

```bash
#!/bin/bash
INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // .tool_input.path // empty')

if [[ "$FILE_PATH" == *.cs ]]; then
  cat .claude/rules/csharp-rules.md
elif [[ "$FILE_PATH" == *.rs ]]; then
  cat .claude/rules/rust-rules.md
fi
```