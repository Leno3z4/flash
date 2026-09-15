#!/usr/bin/env python3
"""Drive the existing interactive CLI from a non-interactive runner.

The live mode feeds the same answers a human would provide. The dry-run mode
uses the existing `Calldata` command to authenticate the configured wallet and
fetch/validate OpenSea mint calldata without signing or broadcasting a transaction.
"""

from __future__ import annotations

import json
import os
import pty
import re
import select
import subprocess
import sys
import tempfile
import time
from pathlib import Path

COLLECTION = os.environ.get("MINT_COLLECTION", "rare-friends-genesis")
TARGET_DATE = os.environ.get("MINT_TARGET_DATE", "2026-09-16")
WALLET_KEY = os.environ.get("MINT_WALLET_KEY", "")
RPC_URL = os.environ.get("MINT_RPC_URL", "https://rpc.mainnet.chain.robinhood.com")
DRY_RUN = os.environ.get("MINT_DRY_RUN", "0").lower() in {"1", "true", "yes"}

PUBLIC_STAGE_RE = re.compile(
    rb"^\s*(\d+)\.\s+Stage\s+\d+\s*\|\s*PUBLIC_SALE\s*\|",
    re.MULTILINE,
)


def fail(message: str) -> "NoReturn":
    print(f"[mint-runner] ERROR: {message}", file=sys.stderr, flush=True)
    raise SystemExit(1)


def write_ephemeral_env() -> Path:
    if not WALLET_KEY:
        fail("MINT_WALLET_KEY is not set")

    env_path = Path(".env")
    values = [
        f"WALLET_KEY={WALLET_KEY}",
        f"RPC_URL={RPC_URL}",
        "FEE_AUTOMATIC=true",
        "GAS_LIMIT=300000",
    ]
    for name in (
        "SCHEDULE_REFRESH_INTERVAL_SECONDS",
        "TRANSACTION_MAX_ATTEMPTS",
        "PENDING_TIMEOUT_SECONDS",
        "RECEIPT_POLL_BASE_DELAY_MS",
        "RECEIPT_POLL_MAX_DELAY_MS",
        "REPLACEMENT_BUMP_BPS",
        "OPENSEA_REQUEST_TIMEOUT_MS",
        "ELIGIBILITY_REQUEST_TIMEOUT_MS",
        "OPENSEA_MAX_ATTEMPTS",
        "OPENSEA_RETRY_INTERVAL_MS",
        "OPENSEA_CALLDATA_MAX_ATTEMPTS",
    ):
        value = os.environ.get(f"MINT_{name}")
        if value:
            values.append(f"{name}={value}")

    env_path.write_text("\n".join(values) + "\n", encoding="utf-8")
    return env_path


def run_dry_run() -> int:
    env_path = write_ephemeral_env()
    manifest_path: Path | None = None
    try:
        if not WALLET_KEY:
            fail("MINT_WALLET_KEY is not set")

        manifest = {
            "version": 1,
            "wallets": [{"private_key": WALLET_KEY, "quantity": 1}],
        }
        fd, path = tempfile.mkstemp(prefix="rare-friends-dry-run-", suffix=".json")
        os.close(fd)
        manifest_path = Path(path)
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        os.chmod(manifest_path, 0o600)

        print("[mint-runner] DRY RUN: no transaction will be signed or broadcast", flush=True)
        print(f"[mint-runner] collection: {COLLECTION}", flush=True)
        print(f"[mint-runner] rpc: {RPC_URL}", flush=True)

        result = subprocess.run(
            [
                "./target/release/opensea-mint",
                "calldata",
                "--collection",
                COLLECTION,
                "--wallets",
                str(manifest_path),
                "--token-id",
                "0",
            ],
            cwd=".",
            env={**os.environ, "MINT_RUNNER": "1"},
            text=True,
            check=False,
        )
        if result.returncode != 0:
            fail(f"dry-run calldata inspection failed with code {result.returncode}")
        print(f"[mint-runner] DRY RUN PASSED for {TARGET_DATE}", flush=True)
        return 0
    finally:
        try:
            if manifest_path is not None:
                manifest_path.unlink(missing_ok=True)
        finally:
            env_path.unlink(missing_ok=True)


def send(master: int, text: str) -> None:
    os.write(master, (text + "\n").encode("utf-8"))
    print(
        f"[mint-runner] answered: {text if text != WALLET_KEY else '<redacted>'}",
        flush=True,
    )


def run_live() -> int:
    env_path = write_ephemeral_env()
    master, slave = pty.openpty()
    env = os.environ.copy()
    env["MINT_RUNNER"] = "1"

    child = subprocess.Popen(
        ["./target/release/opensea-mint", "mint"],
        stdin=slave,
        stdout=slave,
        stderr=slave,
        cwd=".",
        env=env,
        close_fds=True,
    )
    os.close(slave)

    output = bytearray()
    collection_sent = False
    phase_sent = False
    token_sent = False
    quantity_sent = False
    approval_sent = False
    deadline = time.monotonic() + int(
        os.environ.get("MINT_INTERACTION_TIMEOUT_SECONDS", "2700")
    )

    try:
        while child.poll() is None:
            if time.monotonic() > deadline:
                child.kill()
                fail("CLI interaction timed out")

            ready, _, _ = select.select([master], [], [], 1.0)
            if not ready:
                continue

            try:
                chunk = os.read(master, 8192)
            except OSError:
                break
            if not chunk:
                break

            output.extend(chunk)
            sys.stdout.buffer.write(chunk)
            sys.stdout.buffer.flush()

            if not collection_sent and b"Mint target:" in output:
                send(master, COLLECTION)
                collection_sent = True
                continue

            if not phase_sent and b"Phases:" in output:
                matches = PUBLIC_STAGE_RE.findall(bytes(output))
                if not matches:
                    child.kill()
                    fail(
                        "CLI presented phase selection, but no PUBLIC_SALE stage was found"
                    )
                if len(matches) != 1:
                    child.kill()
                    fail(
                        "More than one PUBLIC_SALE stage was presented; refusing to guess"
                    )
                send(master, matches[0].decode("ascii"))
                phase_sent = True
                continue

            if not token_sent and b"Token ID:" in output:
                send(master, "0")
                token_sent = True
                continue

            if not quantity_sent and b"Quantity:" in output:
                send(master, "1")
                quantity_sent = True
                continue

            if not approval_sent and b"Answer [y/N]:" in output:
                send(master, "y")
                approval_sent = True
                continue

            if b"Funding:" in output:
                child.kill()
                fail(
                    "Wallet is underfunded for the prepared transaction; refusing to guess funding steps"
                )

    finally:
        try:
            os.close(master)
        except OSError:
            pass
        try:
            env_path.unlink(missing_ok=True)
        except OSError:
            pass

    return_code = child.wait()
    if return_code != 0:
        print(
            f"[mint-runner] opensea-mint exited with code {return_code}",
            file=sys.stderr,
            flush=True,
        )
    else:
        print(
            f"[mint-runner] mint process completed for {TARGET_DATE}",
            flush=True,
        )
    return return_code


def run() -> int:
    if DRY_RUN:
        return run_dry_run()
    return run_live()


if __name__ == "__main__":
    raise SystemExit(run())
