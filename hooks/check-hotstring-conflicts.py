"""PostToolUse hook: .ahk ファイル編集後にホットストリングのプレフィックス競合を検出する."""
import json
import os
import re
import sys
from pathlib import Path

HOTSTRINGS_DIR = Path.home() / "Documents" / "AutoHotkey" / "hotstrings"
HOTSTRING_RE = re.compile(r"^:\*?:(.+?)::", re.MULTILINE)


def main():
    try:
        raw = sys.stdin.read()
        data = json.loads(raw)
        file_path = data.get("tool_input", {}).get("file_path") or data.get("tool_input", {}).get("path") or ""
        if not file_path.endswith(".ahk"):
            return

        # 全 .ahk ファイルからホットストリング定義を収集
        triggers = []  # list of (trigger, file, line_no)
        for ahk_file in HOTSTRINGS_DIR.rglob("*.ahk"):
            try:
                content = ahk_file.read_text(encoding="utf-8")
            except Exception as e:
                print(f"[hotstring-check] failed to read {ahk_file}: {e}", file=sys.stderr)
                continue
            for i, line in enumerate(content.splitlines(), 1):
                m = HOTSTRING_RE.match(line)
                if m:
                    triggers.append((m.group(1), str(ahk_file), i))

        # プレフィックス競合チェック
        conflicts = []
        for i, (t1, f1, l1) in enumerate(triggers):
            for t2, f2, l2 in triggers[i + 1:]:
                if t1 == t2:
                    conflicts.append(f"  DUPLICATE: `{t1}` defined at {f1}:{l1} and {f2}:{l2}")
                elif t2.startswith(t1):
                    conflicts.append(f"  `{t1}` ({f1}:{l1}) is prefix of `{t2}` ({f2}:{l2}) -> `{t2}` will never fire")
                elif t1.startswith(t2):
                    conflicts.append(f"  `{t2}` ({f2}:{l2}) is prefix of `{t1}` ({f1}:{l1}) -> `{t1}` will never fire")

        if conflicts:
            msg = "HOTSTRING PREFIX CONFLICT DETECTED:\n" + "\n".join(conflicts)
            msg += "\n\nShort triggers with `#Hotstring *` consume input before longer ones can match. Fix by renaming the shorter trigger."
            output = {"hookSpecificOutput": {"additionalContext": msg}}
            print(json.dumps(output))

    except Exception as e:
        print(f"[hotstring-check] error: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
