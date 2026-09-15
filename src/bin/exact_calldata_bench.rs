#![forbid(unsafe_code)]

use std::time::{Duration, Instant};

use opensea_mint::{
    chain::ChainGateway,
    config::LoadedConfig,
    opensea::{parse_collection_locator, WalletOpenSeaClient},
    signing::WalletSigner,
};

const COLLECTION: &str = "rare-friends-genesis";
const TOKEN_ID: &str = "0";
const QUANTITY: u64 = 1;
const SAMPLES: usize = 8;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let loaded = LoadedConfig::load()?;
    let wallet_key = loaded
        .wallet_key()
        .ok_or("WALLET_KEY is required for exact calldata benchmark")?;
    let signer = WalletSigner::from_private_key(wallet_key)?;
    let wallet = signer.identity().address;

    let gateway = ChainGateway::new(Duration::from_millis(
        loaded.app.opensea.request_timeout_ms,
    ))?;
    let probe = gateway.probe_rpc(&loaded.app.rpc_url).await?;
    println!("chain_id={}", probe.chain_id);
    println!("wallet={}", wallet);

    let mut client = WalletOpenSeaClient::new(&loaded.app.opensea)?;
    let locator = parse_collection_locator(COLLECTION)?;
    let collection = client.resolve_collection(&locator, probe.chain_id).await?;
    println!("collection={}", collection.slug);

    client
        .authenticate(&signer, wallet, probe.chain_id, COLLECTION)
        .await?;
    println!("authenticated=true");

    let stage = collection
        .stages
        .iter()
        .find(|stage| stage.stage_index == 0)
        .ok_or("PUBLIC_SALE stage 0 not present in collection metadata")?;
    println!(
        "stage_index={} stage_type={}",
        stage.stage_index, stage.stage_type
    );

    let mut samples_ms = Vec::with_capacity(SAMPLES);
    let mut expected_not_open = 0usize;

    for index in 0..SAMPLES {
        let started = Instant::now();
        let result = client
            .mint_transaction_action(
                &collection,
                stage,
                wallet,
                TOKEN_ID,
                QUANTITY,
                probe.chain_id,
            )
            .await;
        let elapsed_ms = started.elapsed().as_secs_f64() * 1000.0;
        samples_ms.push(elapsed_ms);

        match result {
            Ok(action) => println!(
                "exact_calldata_{:02}: {:.2} ms result=VALID target={} value={} calldata_bytes={}",
                index + 1,
                elapsed_ms,
                action.target,
                action.value,
                action.calldata.len(),
            ),
            Err(error) if error.to_string().contains("not currently accepting mints") => {
                expected_not_open += 1;
                println!(
                    "exact_calldata_{:02}: {:.2} ms result=STAGE_NOT_OPEN",
                    index + 1,
                    elapsed_ms
                );
            }
            Err(error) => {
                println!(
                    "exact_calldata_{:02}: {:.2} ms result=ERROR {}",
                    index + 1,
                    elapsed_ms,
                    error
                );
            }
        }
    }

    let min = samples_ms.iter().copied().fold(f64::INFINITY, f64::min);
    let max = samples_ms.iter().copied().fold(f64::NEG_INFINITY, f64::max);
    let mut sorted = samples_ms.clone();
    sorted.sort_by(f64::total_cmp);
    let median = if sorted.len() % 2 == 0 {
        (sorted[sorted.len() / 2 - 1] + sorted[sorted.len() / 2]) / 2.0
    } else {
        sorted[sorted.len() / 2]
    };

    println!("exact_calldata_min_ms={min:.2}");
    println!("exact_calldata_median_ms={median:.2}");
    println!("exact_calldata_max_ms={max:.2}");
    println!("expected_stage_not_open={expected_not_open}/{SAMPLES}");

    Ok(())
}
