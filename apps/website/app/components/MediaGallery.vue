<!-- 组件职责：展示公开产品媒体，并以可键盘关闭、恢复焦点的 dialog 提供放大查看。 -->
<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'

import { ui } from '~/i18n/ui'
import type { LocaleSlug, PublicMediaDto } from '~/types/public'

import PublicImage from './PublicImage.vue'
import PublicVideo from './PublicVideo.vue'

const props = defineProps<{ media: PublicMediaDto[]; locale: LocaleSlug }>()
const labels = computed(() => ui[props.locale])
const availableMedia = computed(() =>
  props.media.filter((item) => item.type === 'image' || item.type === 'video'),
)
const activeIndex = ref(0)
const isOpen = ref(false)
const opener = ref<HTMLElement | null>(null)
const closeButton = ref<HTMLButtonElement | null>(null)
const dialog = ref<HTMLDialogElement | null>(null)
const activeMedia = computed(() => availableMedia.value[activeIndex.value] ?? null)

/** 打开当前媒体的放大 dialog，并把键盘焦点移到关闭按钮。 */
async function openGallery(index: number, event: Event): Promise<void> {
  activeIndex.value = index
  opener.value = event.currentTarget as HTMLElement
  isOpen.value = true
  await nextTick()
  if (dialog.value && !dialog.value.open) {
    if (typeof dialog.value.showModal === 'function') dialog.value.showModal()
    else dialog.value.setAttribute('open', '')
  }
  closeButton.value?.focus()
}

/** 关闭 dialog，并把焦点还给触发按钮。 */
async function closeGallery(): Promise<void> {
  if (dialog.value?.open && typeof dialog.value.close === 'function') dialog.value.close()
  isOpen.value = false
  await nextTick()
  opener.value?.focus()
}

/** 处理 dialog 的 Escape 键关闭行为。 */
function onDialogKeydown(event: KeyboardEvent): void {
  if (event.key === 'Escape') {
    event.preventDefault()
    void closeGallery()
    return
  }
  if (event.key !== 'Tab' || !dialog.value) return

  const focusable = [
    ...dialog.value.querySelectorAll<HTMLElement>('button, a[href], video[controls]'),
  ]
  if (!focusable.length) return
  const first = focusable[0]!
  const last = focusable.at(-1)!
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault()
    last.focus()
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault()
    first.focus()
  }
}

/** 在公开媒体集合内循环切换上一项或下一项。 */
function move(step: -1 | 1): void {
  const count = availableMedia.value.length
  if (!count) return
  activeIndex.value = (activeIndex.value + step + count) % count
}
</script>

<template>
  <section v-if="availableMedia.length" class="media-gallery" :aria-label="labels.products.gallery">
    <template v-for="(item, index) in availableMedia.slice(0, 1)" :key="item.src">
      <button
        v-if="item.type === 'image'"
        type="button"
        class="media-gallery__primary"
        data-testid="gallery-open"
        :aria-label="labels.media.openGallery"
        @click="openGallery(index, $event)"
      >
        <PublicImage :media="item" :locale="locale" priority />
      </button>
      <PublicVideo v-else :media="item" />
    </template>

    <div v-if="availableMedia.length > 1" class="media-gallery__thumbnails" role="list">
      <button
        v-for="(item, index) in availableMedia"
        :key="`${item.src}:thumbnail`"
        type="button"
        role="listitem"
        :aria-label="`${labels.media.openGallery} ${index + 1}`"
        @click="openGallery(index, $event)"
      >
        <PublicImage
          v-if="item.type === 'image'"
          :media="{ ...item, loading: 'lazy' }"
          :locale="locale"
          sizes="8rem"
        />
        <span v-else>{{ item.alt }}</span>
      </button>
    </div>

    <dialog
      v-if="isOpen && activeMedia"
      ref="dialog"
      role="dialog"
      aria-modal="true"
      :aria-label="activeMedia.alt"
      @keydown="onDialogKeydown"
      @cancel.prevent="closeGallery"
    >
      <div class="media-gallery__dialog-actions">
        <button ref="closeButton" type="button" @click="closeGallery">
          {{ labels.media.closeGallery }}
        </button>
      </div>
      <PublicImage
        v-if="activeMedia.type === 'image'"
        :media="activeMedia"
        :locale="locale"
        sizes="100vw"
      />
      <PublicVideo v-else :media="activeMedia" />
      <div v-if="availableMedia.length > 1" class="media-gallery__dialog-navigation">
        <button type="button" @click="move(-1)">{{ labels.media.previousImage }}</button>
        <button type="button" @click="move(1)">{{ labels.media.nextImage }}</button>
      </div>
    </dialog>
  </section>
</template>

<style scoped>
.media-gallery,
.media-gallery__primary {
  width: 100%;
}

.media-gallery__primary,
.media-gallery__thumbnails button {
  padding: 0;
  overflow: hidden;
  color: inherit;
  text-align: inherit;
  background: transparent;
  border: var(--border-subtle);
  border-radius: 0;
}

.media-gallery__primary :deep(img) {
  aspect-ratio: 3 / 2;
}

.media-gallery__thumbnails {
  margin-block-start: var(--space-3);
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(5rem, 7rem));
  gap: var(--space-2);
}

.media-gallery__thumbnails :deep(img) {
  aspect-ratio: 1;
}

.media-gallery dialog {
  width: min(72rem, calc(100vw - var(--space-8)));
  max-height: calc(100vh - var(--space-8));
  padding: var(--space-4);
  overflow: auto;
  color: var(--color-neutral-950);
  background: var(--color-white);
  border: 0;
  box-shadow: var(--shadow-md);
}

.media-gallery dialog::backdrop {
  background: rgb(8 20 38 / 82%);
}

.media-gallery__dialog-actions,
.media-gallery__dialog-navigation {
  margin-block: var(--space-2);
  display: flex;
  justify-content: flex-end;
  gap: var(--space-3);
}

.media-gallery__dialog-navigation {
  justify-content: space-between;
}

.media-gallery dialog button {
  min-height: 2.75rem;
  padding: var(--space-2) var(--space-4);
}
</style>
