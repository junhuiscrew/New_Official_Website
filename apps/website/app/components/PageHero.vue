<!-- 组件职责：呈现唯一首页 H1、两项核心转化入口和 Public DTO 提供的 LCP 媒体。 -->
<script setup lang="ts">
import type { PublicMediaDto } from '~/types/public'

defineProps<{
  eyebrow?: string | null
  title: string
  summary: string
  primaryLabel: string
  primaryHref: string
  secondaryLabel: string
  secondaryHref: string
  media?: PublicMediaDto | null
}>()
</script>

<template>
  <section
    class="page-hero"
    :class="{ 'page-hero--without-media': media?.type !== 'image' }"
    data-home-section="hero"
  >
    <div class="page-hero__inner public-container">
      <div class="page-hero__content">
        <p v-if="eyebrow" class="page-hero__eyebrow">{{ eyebrow }}</p>
        <h1>{{ title }}</h1>
        <p>{{ summary }}</p>
        <div class="page-hero__actions">
          <a class="page-hero__primary" data-testid="hero-cta" :href="primaryHref">
            {{ primaryLabel }}
          </a>
          <a class="page-hero__secondary" data-testid="hero-cta" :href="secondaryHref">
            {{ secondaryLabel }}
          </a>
        </div>
      </div>

      <figure v-if="media?.type === 'image'" class="page-hero__media">
        <img
          data-testid="hero-media"
          :src="media.src"
          :alt="media.alt"
          :width="media.width ?? undefined"
          :height="media.height ?? undefined"
          loading="eager"
          fetchpriority="high"
        />
        <figcaption v-if="media.caption">{{ media.caption }}</figcaption>
      </figure>
    </div>
  </section>
</template>

<style scoped>
.page-hero {
  color: var(--color-white);
  background: var(--color-navy-950);
  border-block-end: 3px solid var(--color-blue-600);
}

.page-hero__inner {
  min-height: min(44rem, calc(100vh - 5rem));
  padding-block: clamp(var(--space-16), 9vw, var(--space-24));
  display: grid;
  align-items: center;
  grid-template-columns: minmax(0, 1.05fr) minmax(20rem, 0.95fr);
  gap: clamp(var(--space-8), 6vw, var(--space-20));
}

.page-hero__content {
  display: grid;
  gap: var(--space-6);
}

.page-hero h1 {
  color: var(--color-white);
}

.page-hero__eyebrow {
  color: var(--color-blue-100);
  font-size: var(--font-size-label);
  font-weight: 750;
  letter-spacing: var(--letter-spacing-label);
  text-transform: uppercase;
}

.page-hero__content > p {
  max-width: 42rem;
  color: var(--color-neutral-200);
  font-size: clamp(1.0625rem, 2vw, 1.25rem);
}

.page-hero__actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3);
}

.page-hero__actions a {
  min-height: 3rem;
  padding: var(--space-3) var(--space-6);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-weight: 750;
  text-decoration: none;
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
}

.page-hero__primary {
  color: var(--color-white);
  background: var(--color-blue-600);
}

.page-hero__secondary {
  color: var(--color-white);
  border-color: var(--color-neutral-400) !important;
}

.page-hero__media {
  margin: 0;
}

.page-hero__media img {
  width: 100%;
  aspect-ratio: 16 / 9;
  object-fit: cover;
  border: 1px solid var(--color-navy-700);
  box-shadow: var(--shadow-md);
}

.page-hero__media figcaption {
  margin-block-start: var(--space-2);
  color: var(--color-neutral-400);
  font-size: var(--font-size-small);
}

.page-hero--without-media .page-hero__inner {
  grid-template-columns: minmax(0, 48rem);
}

@media (max-width: 48rem) {
  .page-hero__inner {
    min-height: auto;
    grid-template-columns: minmax(0, 1fr);
  }

  .page-hero__actions a {
    flex: 1 1 12rem;
  }
}
</style>
