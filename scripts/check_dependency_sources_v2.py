#!/usr/bin/env python3
"""Fail closed if Rust dependencies stop using checked-in registry sources."""
from __future__ import annotations
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
cargo = (ROOT / "Cargo.toml").read_text(encoding="utf-8")
lock = (ROOT / "Cargo.lock").read_text(encoding="utf-8")

deps = cargo.split("[dependencies]", 1)[1].split("[dev-dependencies]", 1)[0]
if re.search(r"\bgit\s*=", deps):
    raise SystemExit("Cargo.toml contains forbidden git dependencies")
if re.search(r"\bpath\s*=", deps):
    raise SystemExit("Cargo.toml contains forbidden path dependencies")

for pattern, label in ((r'source\s*=\s*"git\+', "git-sourced lock entry"),
                       (r'source\s*=\s*"path\+', "path-sourced lock entry")):
    if re.search(pattern, lock):
        raise SystemExit(f"Cargo.lock contains a forbidden {label}")

blocks = re.split(r"(?=\[\[package\]\]\n)", lock)
for block in blocks:
    name = re.search(r'^name = "([^"]+)"$', block, re.MULTILINE)
    source = re.search(r'^source = "([^"]+)"$', block, re.MULTILINE)
    if name and source and source.group(1).startswith("registry+"):
        if not re.search(r'^checksum = "[0-9a-f]{64}"$', block, re.MULTILINE):
            raise SystemExit(f"Registry package {name.group(1)} has no checksum")

print("Dependency source policy: PASS")
