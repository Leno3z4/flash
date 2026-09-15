#!/usr/bin/env python3
"""Measure a persistent Robinhood Chain WebSocket connection.

This helper is intentionally standalone and does not sign, submit, or modify
transactions. Provide MINT_WS_URL in the environment when running it.
"""

from __future__ import annotations

import json
import os
import statistics
import time


def main() -> int:
    url = os.environ.get("MINT_WS_URL", "")
    if not url.startswith("wss://"):
        raise SystemExit("MINT_WS_URL must be a wss:// URL")

    try:
        from websocket import create_connection
    except ImportError as exc:
        raise SystemExit("install websocket-client first: python3 -m pip install websocket-client") from exc

    start = time.perf_counter()
    connection = create_connection(url, timeout=10)
    connect_ms = (time.perf_counter() - start) * 1000
    print(f"connection_ms={connect_ms:.2f}")

    connection.send(
        json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "eth_subscribe",
                "params": ["newHeads"],
            }
        )
    )
    response = json.loads(connection.recv())
    if "result" not in response:
        raise SystemExit(f"subscription failed: {response}")

    subscription_id = response["result"]
    print(f"subscription_id={subscription_id}")

    samples: list[float] = []
    for index in range(5):
        started = time.perf_counter()
        while True:
            message = json.loads(connection.recv())
            if message.get("method") == "eth_subscription":
                break
        elapsed_ms = (time.perf_counter() - started) * 1000
        samples.append(elapsed_ms)
        block = message.get("params", {}).get("result", {})
        print(f"head_{index + 1}_receive_loop_ms={elapsed_ms:.2f} block={block.get('number')}")

    print(f"receive_loop_min_ms={min(samples):.2f}")
    print(f"receive_loop_median_ms={statistics.median(samples):.2f}")
    print(f"receive_loop_max_ms={max(samples):.2f}")

    connection.send(
        json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "eth_unsubscribe",
                "params": [subscription_id],
            }
        )
    )
    connection.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
