<script lang="ts">
  import { t } from "../lib/i18n";
  import type { Locale } from "../lib/types";

  let { locale }: { locale: Locale } = $props();
</script>

<div class="centered">
  <p>{t(locale, "not_in_telegram")}</p>
</div>
