<script lang="ts">
  import { onMount } from "svelte";

  import { ApiError, createApi, type Api } from "./lib/api";
  import { t } from "./lib/i18n";
  import { getWebApp } from "./lib/telegram";
  import type { Locale, Me, QueueResponse } from "./lib/types";
  import Blocked from "./screens/Blocked.svelte";
  import Done from "./screens/Done.svelte";
  import NotInTelegram from "./screens/NotInTelegram.svelte";
  import Review from "./screens/Review.svelte";

  type Screen = "loading" | "not_in_telegram" | "blocked" | "error" | "review" | "done";

  let screen = $state<Screen>("loading");
  let locale = $state<Locale>("en");
  let me = $state<Me | null>(null);
  let queue = $state<QueueResponse | null>(null);
  let api = $state<Api | null>(null);
  let errorMessage = $state("");
  let gradedCount = $state(0);
  let lastNextReviewAt = $state<string | null>(null);

  const firstCardId = (() => {
    const raw = new URLSearchParams(window.location.search).get("card");
    const parsed = raw === null ? NaN : Number(raw);
    return Number.isInteger(parsed) && parsed > 0 ? parsed : null;
  })();

  async function boot(): Promise<void> {
    const tg = getWebApp();
    if (tg === null || tg.initData === "") {
      screen = "not_in_telegram";
      return;
    }
    tg.ready();
    tg.expand();
    api = createApi(tg.initData);
    await loadQueue();
  }

  async function loadQueue(): Promise<void> {
    if (api === null) return;
    screen = "loading";
    try {
      me = await api.me();
      locale = me.locale;
      queue = await api.queue(50, firstCardId);
      screen = queue.cards.length === 0 ? "done" : "review";
    } catch (error) {
      if (error instanceof ApiError && error.status === 403) {
        screen = "blocked";
        return;
      }
      errorMessage = error instanceof Error ? error.message : String(error);
      screen = "error";
    }
  }

  function handleDone(graded: number, nextReviewAt: string | null): void {
    gradedCount += graded;
    lastNextReviewAt = nextReviewAt;
    screen = "done";
  }

  onMount(() => {
    void boot();
  });
</script>

{#if screen === "loading"}
  <div class="centered"><p class="hint">{t(locale, "loading")}</p></div>
{:else if screen === "not_in_telegram"}
  <NotInTelegram {locale} />
{:else if screen === "blocked"}
  <Blocked {locale} />
{:else if screen === "error"}
  <div class="centered">
    <p>{t(locale, "error_generic")}</p>
    <p class="hint">{errorMessage}</p>
    <button onclick={() => void loadQueue()}>{t(locale, "retry")}</button>
  </div>
{:else if screen === "review" && api !== null && queue !== null && me !== null}
  <Review {api} {locale} cards={queue.cards} totalDue={queue.total_due} ondone={handleDone} />
{:else if me !== null}
  <Done
    {locale}
    timezone={me.timezone}
    graded={gradedCount}
    nextReviewAt={lastNextReviewAt}
    canLoadMore={queue !== null && queue.total_due > queue.cards.length}
    onloadmore={() => void loadQueue()}
  />
{/if}
