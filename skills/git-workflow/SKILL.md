---
name: git-workflow
description: Apply the repository's Git workflow rules when staging, committing, or pushing changes in this ~/.claude repository.
---

# git-workflow

## Instructions

- 1コミットは 1論理変更に限定し、無関係な変更を混ぜない。
- `Co-Authored-By` は付けない。
- `git add -f` や `git add --force` は使わない。
- `git add` と `git commit` は別コマンドで実行する。
- コミット前に実際に動かす、またはテストして動作確認する。
- コミットメッセージは日本語で、subject の 1 行だけを書く。
- push は検証完了後に行い、未確認の変更を送らない。
