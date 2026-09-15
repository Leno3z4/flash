FROM rust:1.97.1-bookworm AS builder

WORKDIR /app
COPY . .
RUN cargo build --release --locked --bin opensea-mint

FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONUNBUFFERED=1 \
    RUST_BACKTRACE=1

RUN useradd --create-home --uid 10001 mint
WORKDIR /app

COPY --from=builder /app/target/release/opensea-mint /usr/local/bin/opensea-mint
COPY cloudflare/mint_runner.py /opt/mint_runner.py

RUN chown -R mint:mint /app /opt/mint_runner.py
USER mint

ENTRYPOINT ["python3", "/opt/mint_runner.py"]
