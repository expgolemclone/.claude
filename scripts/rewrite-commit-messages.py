#!/usr/bin/env python3
"""Filter script for git filter-branch --msg-filter."""

import re
import sys

msg = sys.stdin.read()

# Remove Co-Authored-By lines and any preceding blank lines
msg = re.sub(r"\n+Co-Authored-By:[^\n]*", "", msg, flags=re.IGNORECASE)

# Replace standalone "Claude" references (not part of filenames)
msg = re.sub(r"\bClaude\b", "AI", msg)

# Replace CLAUDE.md filename references
msg = msg.replace("CLAUDE.md", "instructions file")

# Clean up trailing whitespace
msg = msg.rstrip() + "\n"

sys.stdout.write(msg)
