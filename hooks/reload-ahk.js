const path = require("path");
const { execSync } = require("child_process");

const AHK_DIR = "C:\\Users\\0000250059\\Documents\\AutoHotkey";
const AHK_EXE = path.join(AHK_DIR, ".tools", "AutoHotkey-v2", "AutoHotkey64.exe");

let raw = "";
process.stdin.on("data", (c) => (raw += c));
process.stdin.on("end", () => {
  const input = JSON.parse(raw);
  const filePath = (input.tool_input || {}).file_path || (input.tool_input || {}).path || "";

  if (!filePath.endsWith(".ahk")) return;

  // Kill all AHK processes
  try {
    execSync("taskkill /F /IM AutoHotkey64.exe", { stdio: "ignore" });
  } catch {}

  // Restart all launcher scripts
  const fs = require("fs");
  const files = fs.readdirSync(AHK_DIR).filter((f) => f.endsWith("-launcher.ahk"));
  for (const f of files) {
    const script = path.join(AHK_DIR, f);
    execSync(`start "" "${AHK_EXE}" "${script}"`, { stdio: "ignore", shell: true });
  }
});
