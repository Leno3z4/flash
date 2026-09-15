#!/usr/bin/env python3
"""Apply the opt-in hot-path lead time without changing the committed Rust source."""
from __future__ import annotations

import os
from pathlib import Path

lead_ms = int(os.environ.get("MINT_FAST_HOT_LEAD_MS", "5000"))
if not 2000 <= lead_ms <= 10000:
    raise SystemExit("MINT_FAST_HOT_LEAD_MS must be between 2000 and 10000")

path = Path("src/command.rs")
text = path.read_text(encoding="utf-8")
old = "const CALLDATA_HOT_LEAD_MS: u64 = 2_000;"
new = f"const CALLDATA_HOT_LEAD_MS: u64 = {lead_ms:,};"
if old not in text:
    raise SystemExit("Expected hot-path constant was not found; refusing to patch")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
print(f"Applied fast hot-path lead: {lead_ms} ms")
