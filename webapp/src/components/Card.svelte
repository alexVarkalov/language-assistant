<script lang="ts">
  import { t } from "../lib/i18n";
  import type { Locale, QueueCard } from "../lib/types";

  interface Props {
    card: QueueCard;
    revealed: boolean;
    locale: Locale;
    onreveal: () => void;
  }

  let { card, revealed, locale, onreveal }: Props = $props();
</script>

<button class="card" class:revealed onclick={onreveal} disabled={revealed} aria-live="polite">
  <div class="face front">
    <span class="lang">{card.prompt_lang}</span>
    <span class="word">{card.prompt_text}</span>
    <span class="hint">{t(locale, "tap_to_reveal")}</span>
  </div>
  <div class="face back">
    <span class="lang">{card.answer_lang}</span>
    <span class="word">{card.answer_text}</span>
    <span class="hint">{card.prompt_text}</span>
  </div>
</button>

<style>
  .card {
    flex: 1;
    position: relative;
    width: 100%;
    min-height: 240px;
    padding: 0;
    background: transparent;
    color: inherit;
    perspective: 1200px;
    opacity: 1;
  }

  .card:disabled {
    opacity: 1;
  }

  .face {
    position: absolute;
    inset: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 12px;
    padding: 24px;
    border-radius: var(--radius);
    background: var(--bg-secondary);
    backface-visibility: hidden;
    transition: transform 0.45s ease;
  }

  .front {
    transform: rotateY(0deg);
  }

  .back {
    transform: rotateY(180deg);
  }

  .revealed .front {
    transform: rotateY(-180deg);
  }

  .revealed .back {
    transform: rotateY(0deg);
  }

  .lang {
    font-size: 12px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--hint);
  }

  .word {
    font-size: 32px;
    font-weight: 600;
    line-height: 1.2;
    overflow-wrap: anywhere;
  }
</style>
