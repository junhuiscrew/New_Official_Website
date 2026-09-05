<!-- 组件职责：优先导航至已发布 alternate，缺失时安全回退目标语言首页。 -->
<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, useId } from 'vue'

import { alternateTarget } from '~/composables/useLocalePath'
import { useTelemetry } from '~/composables/useTelemetry'
import { ui } from '~/i18n/ui'
import type { LocaleSlug } from '~/types/public'

const props = withDefaults(
  defineProps<{
    locale: LocaleSlug
    alternates?: Readonly<Record<string, string | null | undefined>> | null
  }>(),
  { alternates: null },
)

const root = ref<HTMLElement | null>(null)
const toggleButton = ref<HTMLButtonElement | null>(null)
const open = ref(false)
const optionsId = `language-options-${useId()}`
const discoveredAlternates = ref<Record<string, string>>({})
const targetLocale = computed<LocaleSlug>(() => (props.locale === 'en' ? 'zh-cn' : 'en'))
const targetHref = computed(() =>
  alternateTarget(targetLocale.value, props.alternates ?? discoveredAlternates.value),
)
const labels = computed(() => ui[props.locale])
const telemetry = useTelemetry()

/** 关闭语言选择浮层，并按键盘/外部关闭场景回收焦点。 */
function close(restoreFocus = false): void {
  if (!open.value) return
  open.value = false
  if (restoreFocus) nextTick(() => toggleButton.value?.focus())
}

/** 从页面 Head 读取后端已序列化的 hreflang，支持 Layout 常驻后的 SPA 路由切换。 */
function readHeadAlternates(): void {
  if (typeof document === 'undefined' || props.alternates !== null) return
  discoveredAlternates.value = Object.fromEntries(
    [...document.head.querySelectorAll<HTMLLinkElement>('link[rel="alternate"][hreflang]')]
      .map((link) => [link.hreflang, link.getAttribute('href')?.trim() ?? ''] as const)
      .filter(([, href]) => Boolean(href)),
  )
}

/** 打开前刷新当前页面 alternate，缺失时仍由共享 helper 回退语言首页。 */
function toggle(): void {
  if (!open.value) readHeadAlternates()
  open.value = !open.value
}

/** 处理组件外点击，避免浮层在页面继续操作时残留。 */
function onDocumentClick(event: MouseEvent): void {
  if (open.value && !root.value?.contains(event.target as Node)) close(false)
}

/** Escape 关闭语言选择，并把焦点返回触发按钮。 */
function onDocumentKeydown(event: KeyboardEvent): void {
  if (event.key === 'Escape') close(true)
}

onMounted(() => {
  document.addEventListener('click', onDocumentClick)
  document.addEventListener('keydown', onDocumentKeydown)
})
onBeforeUnmount(() => {
  document.removeEventListener('click', onDocumentClick)
  document.removeEventListener('keydown', onDocumentKeydown)
})
</script>

<template>
  <div ref="root" class="language-switcher">
    <button
      ref="toggleButton"
      type="button"
      :aria-expanded="open"
      :aria-controls="optionsId"
      :aria-label="`${labels.navigation.language}: ${locale === 'zh-cn' ? labels.language.zhCn : labels.language.en}`"
      @click="toggle"
    >
      <span aria-hidden="true">◎</span>
      <span>{{ labels.navigation.language }}</span>
    </button>
    <div
      v-if="open"
      :id="optionsId"
      class="language-switcher__options"
      data-testid="language-options"
    >
      <a
        :href="targetHref"
        :lang="targetLocale === 'zh-cn' ? 'zh-CN' : 'en'"
        @click="telemetry.track('language_switch', { locale, targetLocale })"
      >
        {{ targetLocale === 'zh-cn' ? labels.language.zhCn : labels.language.en }}
      </a>
    </div>
  </div>
</template>

<style scoped>
.language-switcher {
  position: relative;
}

button {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: 0;
  color: inherit;
  background: transparent;
  border: 0;
  cursor: pointer;
}

.language-switcher__options {
  position: absolute;
  inset-block-start: calc(100% + var(--space-3));
  inset-inline-end: 0;
  z-index: 50;
  min-width: 10rem;
  padding: var(--space-2);
  color: var(--color-neutral-950);
  background: var(--color-white);
  border: 1px solid var(--color-neutral-200);
  box-shadow: var(--shadow-md);
}

.language-switcher__options a {
  display: block;
  padding: var(--space-2) var(--space-3);
  color: inherit;
  text-decoration: none;
}
</style>
