let raw = "";
process.stdin.on("data", (c) => (raw += c));
process.stdin.on("end", () => {
  const input = JSON.parse(raw);
  const command = (input.tool_input || {}).command || "";

  // 引用符内の文字列を除去して、実際のコマンド部分のみを検査する
  // (コミットメッセージ等に含まれる "git add -f" での誤検知を防止)
  const stripped = command
    .replace(/"[^"]*"/g, '""')
    .replace(/'[^']*'/g, "''");

  if (/\bgit\s+add\b/.test(stripped) && /\s(-f|--force)\b/.test(stripped)) {
    console.log(
      JSON.stringify({
        decision: "block",
        reason:
          "git add -f (--force) は禁止されています。.gitignore のルールを迂回する強制ステージングは許可されていません。",
      })
    );
  }
});
