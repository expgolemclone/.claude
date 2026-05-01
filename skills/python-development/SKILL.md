---
name: python-development
description: Apply the Python toolchain, dependency, typing, and testing conventions when editing Python code in this ~/.claude repository.
---

# python-development

## Instructions

- Python のツールチェーンは `uv` を使う。
- プロジェクト設定は `pyproject.toml` に集約し、PEP 621 形式を前提にする。
- 依存は pure Python か Rust 実装を優先し、C 拡張は代替がない場合だけ採用する。
- C 拡張を使う依存は、対象 Python と OS の組み合わせで wheel 提供があるものだけを前提にする。
- lockfile の更新は `uv lock` で行う。
- 仮想環境を前提に実行し、場当たり的にグローバル環境へ入れない。
- テストフレームワークは `pytest` を使い、`unittest` や `nose` は増やさない。
- 動的な `dict` や広い `Mapping` より、必要に応じて `TypedDict` を優先する。
- 型や責務があるオブジェクトでは、`__repr__` や `__str__` など関連する dunder method を実装する。
