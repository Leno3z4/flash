#!/usr/bin/env python3
"""Fail closed if Rust dependencies stop using checked-in registry sources."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CARGO_TOML = ROOT / "Cargo.toml"
CARGO_LOCK = ROOT / "Cargo.lock"

cargo = CARGO_TOML.read_text(encoding="utf-8")
lock = CARGO_LOCK.read_text(encoding="utf-8")

for pattern, label in ((r"\bgit\s*=", "git dependencies"), (r"\bpath\s*=", "path dependencies")):
    if re.search(pattern, cargo):
        raise SystemExit(f"Cargo.toml contains forbidden {label}")

for pattern, label in ((r'source\s*=\s*"git\+', "git-sourced lock entry"), (r'source\s*=\s*"path\+', "path-sourced lock entry")):
    if re.search(pattern, lock):
        raise SystemExit(f"Cargo.lock contains a forbidden {label}")

# Every package pulled from crates.io must have a 64-hex checksum in Cargo.lock.
blocks = re.split(r"(?=\[\[package\]\]\n)", lock)
for block in blocks:
    name = re.search(r'^name = "([^"]+)"$', block, re.MULTILINE)
    if not name:
        continue
    source = re.search(r'^source = "([^"]+)"$', block, re.MULTILINE)
    if source and source.group(1).startswith("registry+"):
        if not re.search(r'^checksum = "[0-9a-f]{64}"$', block, re.MULTILINE):
            raise SystemExit(f"Registry package {name.group(1)} has no checksum")

print("Dependency source policy: PASS")
print("- Cargo.toml contains no git/path dependencies")
print("- Cargo.lock contains no git/path sources")
print("- crates.io packages in Cargo.lock are checksum-pinned")
