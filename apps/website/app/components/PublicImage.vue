<!-- 组件职责：只渲染具有公开 alt 与固有尺寸的图片，并统一 LCP/懒加载策略。 -->
<script setup lang="ts">
import { computed, ref } from 'vue'

import { ui } from '~/i18n/ui'
import type { LocaleSlug, PublicMediaDto } from '~/types/public'

const props = withDefaults(
  defineProps<{
    media: PublicMediaDto
    locale?: LocaleSlug
    priority?: boolean
    sizes?: string
    testId?: string
  }>(),
  {
    locale: 'en',
    priority: false,
    sizes: '(max-width: 48rem) 100vw, 50vw',
  },
)

const failed = ref(false)
const isRenderable = computed(
  () =>
    props.media.type === 'image' &&
    Boolean(props.media.src.trim()) &&
    Boolean(props.media.alt.trim()) &&
    Number.isInteger(props.media.width) &&
    Number.isInteger(props.media.height) &&
    Number(props.media.width) > 0 &&
    Number(props.media.height) > 0 &&
    !failed.value,
)
</script>

<template>
  <figure class="public-image">
    <img
      v-if="isRenderable"
      :src="media.src"
      :alt="media.alt"
      :width="media.width!"
      :height="media.height!"
      :loading="priority ? 'eager' : media.loading"
      :fetchpriority="priority ? 'high' : undefined"
      :sizes="sizes"
      :data-testid="testId"
      decoding="async"
      @error="failed = true"
    />
    <p v-else class="public-image__fallback" role="status">
      {{ ui[locale].media.imageUnavailable }}
    </p>
    <figcaption v-if="isRenderable && media.caption">{{ media.caption }}</figcaption>
  </figure>
</template>

<style scoped>
.public-image {
  margin: 0;
}

.public-image img {
  width: 100%;
  height: auto;
  display: block;
  object-fit: cover;
}

.public-image__fallback {
  min-height: 12rem;
  margin: 0;
  display: grid;
  place-items: center;
  color: var(--color-neutral-600);
  background: var(--color-neutral-100);
}

.public-image figcaption {
  padding-block-start: var(--space-2);
  color: var(--color-neutral-600);
  font-size: var(--font-size-small);
}
</style>
