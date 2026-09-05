<!-- 组件职责：仅使用 Case Public Card DTO 展示匿名或已获授权的公开案例内容。 -->
<script setup lang="ts">
import { computed } from 'vue'

import { ui } from '~/i18n/ui'
import type { LocaleSlug, PublicCardDto } from '~/types/public'

const props = defineProps<{ item: PublicCardDto; locale: LocaleSlug }>()
const labels = computed(() => ui[props.locale])
</script>

<template>
  <article class="case-card" :class="{ 'case-card--without-media': item.media?.type !== 'image' }">
    <img
      v-if="item.media?.type === 'image'"
      data-testid="card-media"
      :src="item.media.src"
      :alt="item.media.alt"
      :width="item.media.width ?? undefined"
      :height="item.media.height ?? undefined"
      loading="lazy"
    />
    <div class="case-card__body">
      <h3>
        <a data-testid="card-primary-link" :href="item.url">{{ item.name }}</a>
      </h3>
      <p v-if="item.summary">{{ item.summary }}</p>
      <a class="case-card__action" :href="item.url">{{ labels.cta.viewDetails }}</a>
    </div>
  </article>
</template>

<style scoped>
.case-card {
  height: 100%;
  display: grid;
  grid-template-columns: minmax(8rem, 0.7fr) minmax(0, 1.3fr);
  background: var(--color-white);
  border: var(--border-subtle);
}

.case-card > img {
  width: 100%;
  height: 100%;
  min-height: 13rem;
  object-fit: cover;
}

.case-card--without-media {
  grid-template-columns: minmax(0, 1fr);
}

.case-card__body {
  padding: var(--space-6);
  display: grid;
  align-content: center;
  gap: var(--space-3);
}

.case-card h3 a {
  color: var(--color-navy-900);
  text-decoration: none;
}

.case-card__action {
  font-weight: 700;
}

@media (max-width: 36rem) {
  .case-card {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
