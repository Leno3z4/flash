import { Container, getContainer } from "@cloudflare/containers";

type Env = {
  MINT_CONTAINER: DurableObjectNamespace<RareFriendsMintContainer>;
  MINT_WALLET_KEY: string;
  MINT_RPC_URL: string;
};

const LAUNCH_DATE_UTC = "2026-09-16";
const COLLECTION = "rare-friends-genesis";

export class RareFriendsMintContainer extends Container<Env> {
  // The Rust process waits for the scheduled mint window, so keep the VM
  // alive well past the 15:00 GMT+1 public-stage start.
  sleepAfter = "2h";

  override onStart(): void {
    console.log("Rare Friends mint container started");
  }

  override onStop(): void {
    console.log("Rare Friends mint container stopped");
  }
}

export default {
  async fetch(): Promise<Response> {
    return new Response("Rare Friends mint scheduler is running.");
  },

  async scheduled(
    controller: ScheduledController,
    env: Env,
  ): Promise<void> {
    const scheduledDate = new Date(controller.scheduledTime)
      .toISOString()
      .slice(0, 10);

    if (scheduledDate !== LAUNCH_DATE_UTC) {
      console.log(`Skipping scheduled run on ${scheduledDate}`);
      return;
    }

    const container = getContainer(env.MINT_CONTAINER);
    await container.start({
      envVars: {
        MINT_WALLET_KEY: env.MINT_WALLET_KEY,
        MINT_RPC_URL: env.MINT_RPC_URL,
        MINT_COLLECTION: COLLECTION,
        MINT_TARGET_DATE: LAUNCH_DATE_UTC,
      },
    });
  },
};
