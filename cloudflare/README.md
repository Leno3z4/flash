# Cloudflare deployment

This directory contains the Cloudflare Container control layer for the existing `opensea-mint` binary.

## Legacy-code policy

The Rust CLI and transaction code are intentionally unchanged. `mint_runner.py` drives the existing interactive CLI through a pseudo-terminal so the same validation, scheduling, signing, replacement, and receipt-tracking paths remain in use.

## Rare Friends target

The worker is configured for `rare-friends-genesis` and starts the container at `14:30 UTC` on `2026-09-16`, giving the existing scheduler a 30-minute launch buffer before the public-stage start of `15:00 GMT+1`.

The runner refuses to guess if it sees more than one public stage. It selects the displayed `PUBLIC_SALE` stage, token `0` when requested, quantity `1`, and confirms the existing CLI prompt. It also refuses to perform an interactive funding step inside the container.

## Secrets

Set these as Cloudflare Worker secrets; never put them in Git:

```text
MINT_WALLET_KEY
MINT_RPC_URL
```

The container converts those runtime-only values into the legacy `.env` format and deletes that file when the process exits.

## Deploy

From the repository root:

```bash
npm install
npx wrangler login
npx wrangler secret put MINT_WALLET_KEY
npx wrangler secret put MINT_RPC_URL
npx wrangler deploy
```

Cron Triggers use UTC. The schedule is intentionally date-gated so the daily cron does nothing after the Rare Friends launch date.
