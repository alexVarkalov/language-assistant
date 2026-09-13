<script lang="ts">
  import Card from "../components/Card.svelte";
  import GradeBar from "../components/GradeBar.svelte";
  import { ApiError, type Api } from "../lib/api";
  import { t } from "../lib/i18n";
  import * as rs from "../lib/reviewState";
  import { haptic, hapticSuccess } from "../lib/telegram";
  import type { Locale, Quality, QueueCard } from "../lib/types";

  interface Props {
    api: Api;
    locale: Locale;
    cards: QueueCard[];
    totalDue: number;
    ondone: (graded: number, nextReviewAt: string | null) => void;
  }

  let { api, locale, cards, totalDue, ondone }: Props = $props();

  // The parent remounts this screen for every new queue, so capturing the initial props is intended.
  // svelte-ignore state_referenced_locally
  let state = $state<rs.ReviewState>(rs.load(cards, totalDue));
  const card = $derived(rs.current(state));
  const progress = $derived(rs.progress(state));

  $effect(() => {
    if (state.phase === "done") ondone(state.graded, state.lastNextReviewAt);
  });

  function onReveal(): void {
    haptic("light");
    state = rs.reveal(state);
  }

  async function onGrade(quality: Quality): Promise<void> {
    if (card === null || state.phase !== "answer") return;
    haptic("medium");
    state = rs.startGrading(state);
    try {
      const result = await api.grade(card.id, quality);
      hapticSuccess();
      state = rs.gradeSucceeded(state, result.next_review_at);
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) {
        state = rs.skipCurrent(state);
        return;
      }
      state = rs.gradeFailed(state, error instanceof Error ? error.message : String(error));
    }
  }
</script>

{#if card !== null}
  <header>
    <span class="hint">{t(locale, "progress", { done: progress.done, total: progress.total })}</span>
  </header>

  <Card {card} revealed={state.phase !== "prompt"} {locale} onreveal={onReveal} />

  {#if state.error !== null}
    <p class="error">{state.error}</p>
  {/if}

  <GradeBar {locale} enabled={state.phase === "answer"} ongrade={onGrade} />
{/if}

<style>
  header {
    display: flex;
    justify-content: center;
    padding-bottom: 12px;
  }

  .error {
    color: var(--destructive);
    text-align: center;
    font-size: 14px;
  }
</style>
