const fs = require("fs");
const path = require("path");
const os = require("os");

const RULES_DIR = path.join(os.homedir(), ".claude", "rules");

let raw = "";
process.stdin.on("data", (c) => (raw += c));
process.stdin.on("end", () => {
  const input = JSON.parse(raw);
  const toolInput = input.tool_input || {};

  let rulesContent = "";

  // Bash tool: git command → inject git.toml
  const command = toolInput.command || "";
  if (command && /^\s*git\s/.test(command)) {
    rulesContent = readRule("git.toml");
    if (rulesContent) output(rulesContent);
    return;
  }

  // Edit/Write tool: file extension → inject {ext}.toml
  const filePath = toolInput.file_path || toolInput.path || "";
  if (!filePath) return;

  const ext = path.extname(filePath).replace(".", "").toLowerCase();
  if (!ext) return;

  rulesContent = readRule(ext + ".toml");

  // .md → also inject mmd.toml
  if (ext === "md") {
    const mmd = readRule("mmd.toml");
    if (mmd) rulesContent = rulesContent ? rulesContent + "\n\n" + mmd : mmd;
  }

  if (rulesContent) output(rulesContent);
});

function readRule(filename) {
  const p = path.join(RULES_DIR, filename);
  try {
    const content = fs.readFileSync(p, "utf8").trim();
    return content || "";
  } catch {
    return "";
  }
}

function output(ctx) {
  console.log(
    JSON.stringify({
      hookSpecificOutput: {
        hookEventName: "PreToolUse",
        additionalContext: ctx,
      },
    })
  );
}
