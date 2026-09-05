<!-- 组件职责：展示已发布技术文章的公开摘要、署名、日期和 canonical 链接。 -->
<script setup lang="ts">
import { computed } from 'vue'

import { ui } from '~/i18n/ui'
import type { LocaleSlug, PublicCardDto } from '~/types/public'

const props = defineProps<{ item: PublicCardDto; locale: LocaleSlug }>()
const labels = computed(() => ui[props.locale])
</script>

<template>
  <article class="article-card">
    <img
      v-if="item.media?.type === 'image'"
      data-testid="card-media"
      :src="item.media.src"
      :alt="item.media.alt"
      :width="item.media.width ?? undefined"
      :height="item.media.height ?? undefined"
      loading="lazy"
    />
    <div class="article-card__body">
      <a v-if="item.category" class="eyebrow" :href="item.category.url">
        {{ item.category.name }}
      </a>
      <h3>
        <a data-testid="card-primary-link" :href="item.url">{{ item.name }}</a>
      </h3>
      <p v-if="item.summary">{{ item.summary }}</p>
      <dl
        v-if="item.author || item.reviewer || item.published_at || item.updated_at"
        class="article-card__meta"
      >
        <div v-if="item.author">
          <dt>{{ labels.content.author }}</dt>
          <dd>{{ item.author }}</dd>
        </div>
        <div v-if="item.reviewer">
          <dt>{{ labels.content.reviewer }}</dt>
          <dd>{{ item.reviewer }}</dd>
        </div>
        <div v-if="item.published_at">
          <dt>{{ labels.content.published }}</dt>
          <dd>
            <time :datetime="item.published_at">{{ item.published_at }}</time>
          </dd>
        </div>
        <div v-if="item.updated_at">
          <dt>{{ labels.content.updated }}</dt>
          <dd>
            <time :datetime="item.updated_at">{{ item.updated_at }}</time>
          </dd>
        </div>
      </dl>
      <a class="article-card__action" :href="item.url">{{ labels.common.readMore }}</a>
    </div>
  </article>
</template>

<style scoped>
.article-card {
  height: 100%;
  display: grid;
  align-content: start;
  border-block-start: 3px solid var(--color-blue-600);
  background: var(--color-white);
  box-shadow: var(--shadow-sm);
}

.article-card > img {
  width: 100%;
  aspect-ratio: 16 / 9;
  object-fit: cover;
}

.article-card__body {
  padding: var(--space-5);
  display: grid;
  gap: var(--space-3);
}

.article-card h3 a {
  color: var(--color-navy-900);
  text-decoration: none;
}

.article-card__meta {
  margin: 0;
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3);
  color: var(--color-neutral-600);
  font-size: var(--font-size-small);
}

.article-card__meta > div {
  display: flex;
}

.article-card__meta dt,
.article-card__meta dd {
  margin: 0;
}

.article-card__action {
  font-weight: 700;
}
</style>
