---
name: repo-coding-standards
description: Apply the repository-wide coding standards for organization, testing, scraping manners, error handling, and clarification when editing code in this ~/.claude repository.
---

# repo-coding-standards

## Instructions

- 共通処理は専用モジュールや関数に切り出し、重複を放置しない。
- フォルダ構成は意味論で整理し、ルートディレクトリに雑多なファイルを置かない。
- コードは自己文書化を優先し、コメントは意図や理由が必要なときだけ書く。
- テストは TDD を基本とし、`Arrange-Act-Assert` の順で読みやすく構成する。
- lockfile を使う変更では、lockfile もリポジトリに含める。
- スクレイピング処理は `scrape` 系の場所に集約し、無関係な場所へ分散させない。
- スクレイピングは並列数 1 を基本にし、リクエスト間隔は最低でも 1.0 秒空け、明示的な必要がない限りプロキシは使わない。
- `except Exception` や `except BaseException` のような広すぎる例外捕捉は避け、具体的な例外型を扱う。
- 例外を `pass` で握りつぶさず、ログ出力か再送出で失敗を可視化する。
- エラー時に黙って既定値を返して隠蔽せず、失敗は呼び出し元に伝搬させる。
- 依頼の意図が結果に影響する場合は推測で補わず、必要な確認を行う。
