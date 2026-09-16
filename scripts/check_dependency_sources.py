#!/usr/bin/env python3
"""Fail closed if the resolved Rust dependency graph leaves the registry."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CARGO_LOCK = ROOT / "Cargo.lock"

metadata = json.loads(
    subprocess.check_output(
        ["cargo", "metadata", "--locked", "--format-version", "1"],
        cwd=ROOT,
        text=True,
    )
)

for package in metadata["packages"]:
    source = package.get("source")
    if source is None:
        # Workspace/local package.
        continue
    if source.startswith(("git+", "path+")):
        raise SystemExit(
            f"Package {package['name']} uses forbidden source: {source}"
        )
    if not source.startswith("registry+"):
        raise SystemExit(
            f"Package {package['name']} uses an unapproved source: {source}"
        )

# Every registry package resolved in Cargo.lock must have a 64-hex checksum.
lock = CARGO_LOCK.read_text(encoding="utf-8")
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
print("- Resolved dependencies are registry-sourced or local workspace packages")
print("- Cargo.lock contains no git/path sources")
print("- crates.io registry packages in Cargo.lock are checksum-pinned")
