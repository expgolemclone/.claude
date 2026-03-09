const fs = require("fs");

let raw = "";
process.stdin.on("data", (c) => (raw += c));
process.stdin.on("end", () => {
  const input = JSON.parse(raw);
  const command = (input.tool_input || {}).command || "";

  // git add に -f / --force が含まれるかチェック
  if (/\bgit\s+add\b/.test(command) && /\s(-f|--force)\b/.test(command)) {
    console.log(
      JSON.stringify({
        decision: "block",
        reason:
          "git add -f (--force) は禁止されています。.gitignore のルールを迂回する強制ステージングは許可されていません。",
      })
    );
  }
});
