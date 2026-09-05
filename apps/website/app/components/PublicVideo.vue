<!-- 组件职责：按 DTO 加载策略延迟非首屏视频，并用原生 controls 展示公开视频。 -->
<script setup lang="ts">
import { computed } from 'vue'

import type { PublicMediaDto } from '~/types/public'

const props = defineProps<{
  media: PublicMediaDto
  poster?: PublicMediaDto | null
}>()

const posterSrc = computed(() => {
  const poster = props.poster
  if (
    poster?.type !== 'image' ||
    !poster.src.trim() ||
    !poster.alt.trim() ||
    !poster.width ||
    !poster.height
  ) {
    return undefined
  }
  return poster.src
})

// 非首屏视频不预取字节；显式 eager 视频仅加载元数据，不自动播放。
const preload = computed(() => (props.media.loading === 'lazy' ? 'none' : 'metadata'))
</script>

<template>
  <figure v-if="media.type === 'video' && media.src && media.alt" class="public-video">
    <video
      controls
      playsinline
      :preload="preload"
      :poster="posterSrc"
      :width="media.width ?? undefined"
      :height="media.height ?? undefined"
      :aria-label="media.alt"
      :data-loading="media.loading"
    >
      <source :src="media.src" :type="media.mime_type" />
    </video>
    <figcaption v-if="media.caption">{{ media.caption }}</figcaption>
  </figure>
</template>

<style scoped>
.public-video {
  margin: 0;
}

.public-video video {
  width: 100%;
  height: auto;
  display: block;
  background: var(--color-navy-950);
}

.public-video figcaption {
  padding-block-start: var(--space-2);
  color: var(--color-neutral-600);
  font-size: var(--font-size-small);
}
</style>
