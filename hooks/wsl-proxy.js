const { spawn, execSync } = require("child_process");
const fs = require("fs");
const path = require("path");
const os = require("os");
const net = require("net");

const PROXY_PORT = 8888;
const PID_FILE = path.join(os.tmpdir(), "claude-wsl-proxy.pid");
const MODE = process.argv[2]; // "pre" or "post"

let raw = "";
process.stdin.on("data", (c) => (raw += c));
process.stdin.on("end", async () => {
  try {
    const input = JSON.parse(raw);
    const command = (input.tool_input || {}).command || "";

    if (!shouldActivate(command)) return;

    if (MODE === "pre") {
      await handlePre();
    } else if (MODE === "post") {
      handlePost();
    }
  } catch (e) {
    // Fail silently to avoid blocking Claude
    process.stderr.write(`wsl-proxy hook error: ${e.message}\n`);
  }
});

function shouldActivate(command) {
  if (!command.includes("nixos-rebuild")) return false;
  // WSL invocation or direct sudo nixos-rebuild (inside WSL)
  return command.includes("wsl") || /sudo\s+nixos-rebuild/.test(command);
}

async function handlePre() {
  const inUse = await isPortInUse(PROXY_PORT);
  if (inUse) {
    // Proxy already running — just give feedback
    outputFeedback();
    return;
  }

  // Start proxy
  const child = spawn("proxy", ["--hostname", "0.0.0.0", "--port", String(PROXY_PORT)], {
    detached: true,
    stdio: "ignore",
    windowsHide: true,
  });
  child.unref();

  fs.writeFileSync(PID_FILE, String(child.pid), "utf8");

  // Wait for proxy to be ready
  await waitForPort(PROXY_PORT, 3000);

  outputFeedback();
}

function handlePost() {
  let pid;
  try {
    pid = parseInt(fs.readFileSync(PID_FILE, "utf8").trim(), 10);
  } catch {
    // No PID file — we didn't start the proxy, leave it alone
    return;
  }

  try {
    process.kill(pid, "SIGTERM");
  } catch {
    // Process already gone
  }

  try {
    fs.unlinkSync(PID_FILE);
  } catch {
    // Ignore
  }
}

function isPortInUse(port) {
  return new Promise((resolve) => {
    const server = net.createServer();
    server.once("error", (err) => {
      resolve(err.code === "EADDRINUSE");
    });
    server.once("listening", () => {
      server.close(() => resolve(false));
    });
    server.listen(port, "0.0.0.0");
  });
}

function waitForPort(port, timeoutMs) {
  const start = Date.now();
  return new Promise((resolve) => {
    const tryConnect = () => {
      if (Date.now() - start > timeoutMs) {
        resolve(false);
        return;
      }
      const sock = net.createConnection({ port, host: "127.0.0.1" });
      sock.once("connect", () => {
        sock.destroy();
        resolve(true);
      });
      sock.once("error", () => {
        setTimeout(tryConnect, 200);
      });
    };
    tryConnect();
  });
}

function outputFeedback() {
  const msg = [
    "WSL proxy started on port 8888.",
    "nixos-rebuild command must include proxy env vars.",
    "Get the gateway IP inside WSL with: ip route show default | awk '{print $3}'",
    "Then pass: http_proxy=http://<GATEWAY_IP>:8888 https_proxy=http://<GATEWAY_IP>:8888",
    "Example: wsl -d NixOS -- bash -c 'export GW=$(ip route show default | awk \\'\\'{print $3}\\'\\'); sudo http_proxy=http://$GW:8888 https_proxy=http://$GW:8888 nixos-rebuild switch'",
  ].join("\n");

  console.log(
    JSON.stringify({
      hookSpecificOutput: {
        hookEventName: "PreToolUse",
        additionalContext: msg,
      },
    })
  );
}
