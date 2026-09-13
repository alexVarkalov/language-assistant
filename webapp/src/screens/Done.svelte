<script lang="ts">
  import { formatDateTime, t } from "../lib/i18n";
  import { getWebApp } from "../lib/telegram";
  import type { Locale } from "../lib/types";

  interface Props {
    locale: Locale;
    timezone: string;
    graded: number;
    nextReviewAt: string | null;
    canLoadMore: boolean;
    onloadmore: () => void;
  }

  let { locale, timezone, graded, nextReviewAt, canLoadMore, onloadmore }: Props = $props();
</script>

<div class="centered">
  <h1>{t(locale, "done_title")}</h1>
  {#if graded > 0}
    <p>{t(locale, "done_body", { count: graded })}</p>
  {/if}
  {#if nextReviewAt !== null}
    <p class="hint">{t(locale, "done_next", { when: formatDateTime(nextReviewAt, timezone, locale) })}</p>
  {:else}
    <p class="hint">{t(locale, "done_none")}</p>
  {/if}
  {#if canLoadMore}
    <button onclick={onloadmore}>{t(locale, "load_more")}</button>
  {:else}
    <button onclick={() => getWebApp()?.close()}>{t(locale, "close")}</button>
  {/if}
</div>

<style>
  h1 {
    margin: 0;
    font-size: 28px;
  }
</style>
