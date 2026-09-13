<script lang="ts">
  import { t } from "../lib/i18n";
  import type { Locale, Quality } from "../lib/types";

  interface Props {
    locale: Locale;
    enabled: boolean;
    ongrade: (quality: Quality) => void;
  }

  let { locale, enabled, ongrade }: Props = $props();
</script>

<div class="bar">
  <button class="again" disabled={!enabled} onclick={() => ongrade(0)}>{t(locale, "again")}</button>
  <button class="good" disabled={!enabled} onclick={() => ongrade(3)}>{t(locale, "good")}</button>
  <button class="easy" disabled={!enabled} onclick={() => ongrade(5)}>{t(locale, "easy")}</button>
</div>

<style>
  .bar {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 10px;
    padding-top: 16px;
  }

  .again {
    background: var(--destructive);
  }

  .easy {
    filter: saturate(0.7) brightness(1.1);
  }
</style>
