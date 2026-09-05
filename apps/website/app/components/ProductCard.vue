<!-- 组件职责：展示公开产品卡片、最多四项公开规格及带来源上下文的询价入口。 -->
<script setup lang="ts">
import { computed } from 'vue'

import { rfqUrl } from '~/composables/useLocalePath'
import { useTelemetry } from '~/composables/useTelemetry'
import { ui } from '~/i18n/ui'
import type { LocaleSlug, PublicCardDto } from '~/types/public'

const props = defineProps<{ item: PublicCardDto; locale: LocaleSlug }>()
const labels = computed(() => ui[props.locale])
const specifications = computed(() => (props.item.specifications ?? []).slice(0, 4))
const telemetry = useTelemetry()
</script>

<template>
  <article class="product-card">
    <img
      v-if="item.media?.type === 'image'"
      data-testid="card-media"
      :src="item.media.src"
      :alt="item.media.alt"
      :width="item.media.width ?? undefined"
      :height="item.media.height ?? undefined"
      loading="lazy"
    />
    <div class="product-card__body">
      <a v-if="item.category" class="eyebrow" :href="item.category.url">
        {{ item.category.name }}
      </a>
      <h3>
        <a data-testid="card-primary-link" :href="item.url">{{ item.name }}</a>
      </h3>
      <p v-if="item.summary">{{ item.summary }}</p>
      <dl v-if="specifications.length" class="product-card__specs">
        <div
          v-for="specification in specifications"
          :key="`${specification.group}:${specification.name}`"
        >
          <dt>{{ specification.name }}</dt>
          <dd>
            {{ specification.value
            }}<template v-if="specification.unit"> {{ specification.unit }}</template>
          </dd>
        </div>
      </dl>
      <div class="product-card__actions">
        <a data-testid="card-primary-link-action" :href="item.url">{{ labels.cta.viewDetails }}</a>
        <a
          :href="rfqUrl({ locale, type: item.type, slug: item.slug })"
          @click="
            telemetry.track('rfq_cta_click', {
              locale,
              sourceType: item.type,
              sourceSlug: item.slug,
            })
          "
        >
          {{ labels.cta.requestQuote }}
        </a>
      </div>
    </div>
  </article>
</template>

<style scoped>
.product-card {
  height: 100%;
  display: grid;
  align-content: start;
  background: var(--color-white);
  border: var(--border-subtle);
}

.product-card > img {
  width: 100%;
  aspect-ratio: 3 / 2;
  object-fit: cover;
}

.product-card__body {
  padding: var(--space-5);
  display: grid;
  gap: var(--space-3);
}

.product-card h3 a {
  color: var(--color-navy-900);
  text-decoration: none;
}

.product-card p {
  color: var(--color-neutral-600);
}

.product-card__specs {
  margin: var(--space-2) 0 0;
  display: grid;
  gap: var(--space-2);
}

.product-card__specs > div {
  display: flex;
  justify-content: space-between;
  gap: var(--space-3);
  padding-block-end: var(--space-2);
  border-block-end: var(--border-subtle);
}

.product-card__specs dt,
.product-card__specs dd {
  margin: 0;
  font-size: var(--font-size-small);
}

.product-card__specs dd {
  color: var(--color-neutral-950);
  font-family: var(--font-technical);
}

.product-card__actions {
  margin-block-start: var(--space-2);
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-4);
  font-weight: 700;
}
</style>
