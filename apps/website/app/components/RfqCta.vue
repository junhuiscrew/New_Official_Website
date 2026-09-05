<!-- 组件职责：提供本地化 RFQ 转化区，并仅携带允许的公开来源上下文。 -->
<script setup lang="ts">
import { computed } from 'vue'

import { rfqUrl } from '~/composables/useLocalePath'
import { useTelemetry } from '~/composables/useTelemetry'
import { ui } from '~/i18n/ui'
import type { LocaleSlug, PublicContentType } from '~/types/public'

const props = defineProps<{
  locale: LocaleSlug
  sourceType?: PublicContentType
  sourceSlug?: string
}>()
const labels = computed(() => ui[props.locale])
const href = computed(() =>
  rfqUrl({ locale: props.locale, type: props.sourceType, slug: props.sourceSlug }),
)
const telemetry = useTelemetry()
</script>

<template>
  <section class="rfq-cta" data-home-section="rfq" aria-labelledby="homepage-rfq-title">
    <div class="public-container rfq-cta__inner">
      <div>
        <p class="eyebrow">{{ labels.cta.requestQuote }}</p>
        <h2 id="homepage-rfq-title">{{ labels.home.rfqTitle }}</h2>
        <p>{{ labels.home.rfqSummary }}</p>
      </div>
      <a
        :href="href"
        @click="
          telemetry.track('rfq_cta_click', {
            locale,
            sourceType,
            sourceSlug,
          })
        "
      >
        {{ labels.cta.requestQuote }}
      </a>
    </div>
  </section>
</template>

<style scoped>
.rfq-cta {
  padding-block: var(--space-16);
  color: var(--color-white);
  background: var(--color-navy-900);
}

.rfq-cta__inner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-8);
}

.rfq-cta__inner > div {
  display: grid;
  gap: var(--space-3);
}

.rfq-cta h2,
.rfq-cta .eyebrow {
  color: var(--color-white);
}

.rfq-cta__inner > div > p:last-child {
  color: var(--color-neutral-200);
}

.rfq-cta a {
  flex: 0 0 auto;
  padding: var(--space-3) var(--space-6);
  color: var(--color-white);
  font-weight: 750;
  text-decoration: none;
  background: var(--color-blue-600);
  border-radius: var(--radius-sm);
}

@media (max-width: 40rem) {
  .rfq-cta__inner {
    align-items: stretch;
    flex-direction: column;
  }

  .rfq-cta a {
    text-align: center;
  }
}
</style>
