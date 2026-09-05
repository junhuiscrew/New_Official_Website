<!-- 组件职责：提供移动端全屏导航、动态 accordion、滚动锁与无障碍关闭行为。 -->
<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import LanguageSwitcher from './LanguageSwitcher.vue'
import SearchButton from './SearchButton.vue'
import { ui } from '~/i18n/ui'
import type { LocaleSlug, NavigationDto } from '~/types/public'

type AccordionKey = 'products' | 'solutions' | 'materials' | 'applications'

const props = withDefaults(
  defineProps<{
    open: boolean
    navigation: NavigationDto
    locale: LocaleSlug
    alternates?: Readonly<Record<string, string | null | undefined>> | null
  }>(),
  { alternates: null },
)

const emit = defineEmits<{ close: [] }>()
const labels = computed(() => ui[props.locale])
const expanded = ref<AccordionKey | null>(null)
const panel = ref<HTMLElement | null>(null)
const closeButton = ref<HTMLButtonElement | null>(null)
let savedBodyOverflow = ''
let bodyLocked = false
let desktopMedia: MediaQueryList | null = null

const staticRoutes = computed(() => [
  { key: 'capabilities', label: labels.value.navigation.capabilities },
  { key: 'case-studies', label: labels.value.navigation.caseStudies },
  { key: 'knowledge', label: labels.value.navigation.knowledge },
  { key: 'about', label: labels.value.navigation.about },
])

const productItems = computed(() => [
  ...props.navigation.products.categories,
  ...props.navigation.products.featured,
])
const solutionItems = computed(() => [
  ...props.navigation.solutions.featured,
  ...props.navigation.solutions.problems,
])

/** 仅在移动菜单打开期间锁定 body，并保留页面原有 overflow 值。 */
function syncBodyLock(shouldLock: boolean): void {
  if (typeof document === 'undefined') return
  if (shouldLock && !bodyLocked) {
    savedBodyOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    bodyLocked = true
  } else if (!shouldLock && bodyLocked) {
    document.body.style.overflow = savedBodyOverflow
    bodyLocked = false
  }
}

/** 切换一个 accordion，同时关闭其余动态分组。 */
function toggleAccordion(key: AccordionKey): void {
  expanded.value = expanded.value === key ? null : key
}

watch(
  () => props.open,
  (open) => {
    syncBodyLock(open)
    if (!open) expanded.value = null
    else nextTick(() => closeButton.value?.focus())
  },
  { immediate: true },
)

/** MobileNav 独立挂载时也支持 Escape，焦点回收由拥有触发按钮的父组件完成。 */
function onDocumentKeydown(event: KeyboardEvent): void {
  if (!props.open) return
  if (event.key === 'Escape') {
    emit('close')
    return
  }
  if (event.key !== 'Tab' || !panel.value) return

  // 全屏面板打开时循环可用焦点，避免键盘游标落到被遮挡的页面内容。
  const focusable = [
    ...panel.value.querySelectorAll<HTMLElement>('a[href], button:not([disabled])'),
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

/** 视口进入桌面断点时关闭隐藏的移动面板，确保 body 不残留滚动锁。 */
function onDesktopViewport(event: MediaQueryListEvent | MediaQueryList): void {
  if (event.matches && props.open) emit('close')
}

onMounted(() => {
  document.addEventListener('keydown', onDocumentKeydown)
  desktopMedia = window.matchMedia('(min-width: 74.001rem)')
  desktopMedia.addEventListener('change', onDesktopViewport)
  onDesktopViewport(desktopMedia)
})
onBeforeUnmount(() => {
  document.removeEventListener('keydown', onDocumentKeydown)
  desktopMedia?.removeEventListener('change', onDesktopViewport)
  syncBodyLock(false)
})
</script>

<template>
  <div
    v-if="open"
    class="mobile-nav"
    data-testid="mobile-nav"
    role="dialog"
    aria-modal="true"
    :aria-label="labels.navigation.mobileNavigation"
  >
    <button
      class="mobile-nav__backdrop"
      type="button"
      tabindex="-1"
      :aria-label="labels.navigation.closeMenu"
      @click="emit('close')"
    />
    <div ref="panel" class="mobile-nav__panel">
      <div class="mobile-nav__topbar">
        <img src="/brand/junhui-mark.png" alt="" width="40" height="40" />
        <button
          ref="closeButton"
          type="button"
          class="mobile-nav__close"
          data-testid="mobile-nav-close"
          @click="emit('close')"
        >
          {{ labels.navigation.closeMenu }}
        </button>
      </div>

      <nav :aria-label="labels.navigation.menu">
        <ul class="mobile-nav__list">
          <li>
            <button
              v-if="productItems.length"
              type="button"
              data-testid="mobile-products-toggle"
              :aria-expanded="expanded === 'products'"
              aria-controls="mobile-products-panel"
              @click="toggleAccordion('products')"
            >
              {{ labels.navigation.products }}
              <span aria-hidden="true">+</span>
            </button>
            <a v-else :href="`/${locale}/products/`" @click="emit('close')">
              {{ labels.navigation.products }}
            </a>
            <ul
              v-if="productItems.length"
              v-show="expanded === 'products'"
              id="mobile-products-panel"
            >
              <li v-for="item in productItems" :key="`${item.type}:${item.url}`">
                <a :href="item.url" @click="emit('close')">{{ item.name }}</a>
              </li>
              <li>
                <a :href="`/${locale}/products/`" @click="emit('close')">
                  {{ labels.navigation.viewAllProducts }}
                </a>
              </li>
            </ul>
          </li>

          <li>
            <button
              v-if="solutionItems.length"
              type="button"
              data-testid="mobile-solutions-toggle"
              :aria-expanded="expanded === 'solutions'"
              aria-controls="mobile-solutions-panel"
              @click="toggleAccordion('solutions')"
            >
              {{ labels.navigation.solutions }}
              <span aria-hidden="true">+</span>
            </button>
            <a v-else :href="`/${locale}/solutions/`" @click="emit('close')">
              {{ labels.navigation.solutions }}
            </a>
            <ul
              v-if="solutionItems.length"
              v-show="expanded === 'solutions'"
              id="mobile-solutions-panel"
            >
              <li v-for="item in solutionItems" :key="`${item.type}:${item.url}`">
                <a :href="item.url" @click="emit('close')">{{ item.name }}</a>
              </li>
              <li>
                <a :href="`/${locale}/solutions/`" @click="emit('close')">
                  {{ labels.navigation.viewAllSolutions }}
                </a>
              </li>
            </ul>
          </li>

          <li>
            <button
              v-if="navigation.materials.length"
              type="button"
              data-testid="mobile-materials-toggle"
              :aria-expanded="expanded === 'materials'"
              aria-controls="mobile-materials-panel"
              @click="toggleAccordion('materials')"
            >
              {{ labels.navigation.materials }}
              <span aria-hidden="true">+</span>
            </button>
            <a v-else :href="`/${locale}/materials/`" @click="emit('close')">
              {{ labels.navigation.materials }}
            </a>
            <ul
              v-if="navigation.materials.length"
              v-show="expanded === 'materials'"
              id="mobile-materials-panel"
            >
              <li v-for="item in navigation.materials" :key="`${item.type}:${item.url}`">
                <a :href="item.url" @click="emit('close')">{{ item.name }}</a>
              </li>
              <li>
                <a :href="`/${locale}/materials/`" @click="emit('close')">
                  {{ labels.navigation.viewAllMaterials }}
                </a>
              </li>
            </ul>
          </li>

          <li>
            <button
              v-if="navigation.applications.length"
              type="button"
              data-testid="mobile-applications-toggle"
              :aria-expanded="expanded === 'applications'"
              aria-controls="mobile-applications-panel"
              @click="toggleAccordion('applications')"
            >
              {{ labels.navigation.applications }}
              <span aria-hidden="true">+</span>
            </button>
            <a v-else :href="`/${locale}/applications/`" @click="emit('close')">
              {{ labels.navigation.applications }}
            </a>
            <ul
              v-if="navigation.applications.length"
              v-show="expanded === 'applications'"
              id="mobile-applications-panel"
            >
              <li v-for="item in navigation.applications" :key="`${item.type}:${item.url}`">
                <a :href="item.url" @click="emit('close')">{{ item.name }}</a>
              </li>
              <li>
                <a :href="`/${locale}/applications/`" @click="emit('close')">
                  {{ labels.navigation.viewAllApplications }}
                </a>
              </li>
            </ul>
          </li>

          <li v-for="routeItem in staticRoutes" :key="routeItem.key">
            <a :href="`/${locale}/${routeItem.key}/`" @click="emit('close')">
              {{ routeItem.label }}
            </a>
          </li>
        </ul>
      </nav>

      <div class="mobile-nav__actions">
        <SearchButton :locale="locale" />
        <LanguageSwitcher :locale="locale" :alternates="alternates" />
        <a
          class="mobile-nav__rfq"
          data-testid="mobile-rfq-cta"
          :href="`/${locale}/request-a-quote/`"
          @click="emit('close')"
        >
          {{ labels.cta.requestQuote }}
        </a>
      </div>
    </div>
  </div>
</template>

<style scoped>
.mobile-nav {
  position: fixed;
  inset: 0;
  z-index: 80;
  display: none;
}

.mobile-nav__backdrop {
  position: absolute;
  inset: 0;
  width: 100%;
  background: rgb(5 18 37 / 72%);
  border: 0;
}

.mobile-nav__panel {
  position: relative;
  width: min(90vw, 26rem);
  height: 100%;
  margin-inline-start: auto;
  padding: var(--space-4);
  overflow-y: auto;
  color: var(--color-neutral-950);
  background: var(--color-white);
}

.mobile-nav__topbar,
.mobile-nav__actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
}

.mobile-nav__close,
.mobile-nav__list button {
  color: inherit;
  background: transparent;
  border: 0;
  cursor: pointer;
}

.mobile-nav__list,
.mobile-nav__list ul {
  margin: 0;
  padding: 0;
  list-style: none;
}

.mobile-nav__list {
  margin-block: var(--space-6);
  border-block-start: 1px solid var(--color-neutral-200);
}

.mobile-nav__list > li {
  border-block-end: 1px solid var(--color-neutral-200);
}

.mobile-nav__list button,
.mobile-nav__list > li > a {
  width: 100%;
  min-height: 3rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-3) 0;
  color: inherit;
  font-weight: 700;
  text-align: start;
  text-decoration: none;
}

.mobile-nav__list ul {
  padding: 0 0 var(--space-3) var(--space-4);
}

.mobile-nav__list ul a {
  display: block;
  padding: var(--space-2) 0;
  color: var(--color-neutral-700);
  text-decoration: none;
}

.mobile-nav__actions {
  align-items: stretch;
  flex-direction: column;
}

.mobile-nav__rfq {
  padding: var(--space-3) var(--space-4);
  color: var(--color-white);
  font-weight: 700;
  text-align: center;
  text-decoration: none;
  background: var(--color-blue-700);
  border-radius: var(--radius-sm);
}

@media (max-width: 74rem) {
  .mobile-nav {
    display: block;
  }
}
</style>
