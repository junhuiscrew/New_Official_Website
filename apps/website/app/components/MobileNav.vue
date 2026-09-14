<!-- 组件职责：提供移动端全屏导航、动态 accordion、滚动锁与无障碍关闭行为。 -->
<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import LanguageSwitcher from './LanguageSwitcher.vue'
import SearchButton from './SearchButton.vue'
import { ui } from '~/i18n/ui'
import type {
  LocaleSlug,
  NavigationDto,
  NavigationMenuItemDto,
  PublicLinkDto,
} from '~/types/public'

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

const productItems = computed(() => [
  ...props.navigation.products.categories,
  ...props.navigation.products.featured,
])
const solutionItems = computed(() => [
  ...props.navigation.solutions.featured,
  ...props.navigation.solutions.problems,
])
const brandLogo = computed(
  () => props.navigation.brand?.media.mobile_logo?.url ?? '/brand/junhui-mark.png',
)

// 设置未初始化时按旧公开合同生成等值顺序，保证迁移窗口的移动菜单可用。
const headerItems = computed<NavigationMenuItemDto[]>(() => {
  if (props.navigation.header_items?.length) return props.navigation.header_items
  const routes: Record<string, { label: string; path: string }> = {
    products: { label: labels.value.navigation.products, path: `/${props.locale}/products/` },
    solutions: { label: labels.value.navigation.solutions, path: `/${props.locale}/solutions/` },
    materials: { label: labels.value.navigation.materials, path: `/${props.locale}/materials/` },
    applications: {
      label: labels.value.navigation.applications,
      path: `/${props.locale}/applications/`,
    },
    capabilities: {
      label: labels.value.navigation.capabilities,
      path: `/${props.locale}/capabilities/`,
    },
    case_studies: {
      label: labels.value.navigation.caseStudies,
      path: `/${props.locale}/case-studies/`,
    },
    knowledge: { label: labels.value.navigation.knowledge, path: `/${props.locale}/knowledge/` },
    about: { label: labels.value.navigation.about, path: `/${props.locale}/about/` },
  }
  return props.navigation.primary.map((key) => ({ target_key: key, ...routes[key]! }))
})

/** 判断当前项目是否支持动态子菜单。 */
function isAccordionKey(key: string): key is AccordionKey {
  return ['products', 'solutions', 'materials', 'applications'].includes(key)
}

/** 返回当前语言已通过发布门禁的子菜单内容。 */
function submenuItems(key: string): PublicLinkDto[] {
  if (!isAccordionKey(key)) return []
  if (key === 'products') return productItems.value
  if (key === 'solutions') return solutionItems.value
  if (key === 'materials') return props.navigation.materials
  return props.navigation.applications
}

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

/** 输入任意服务端目标键；输出无，仅切换受支持动态分组。 */
function toggleAccordionForKey(key: string): void {
  if (isAccordionKey(key)) toggleAccordion(key)
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
        <img :src="brandLogo" :alt="navigation.brand?.short_name ?? ''" width="40" height="40" />
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
          <li v-for="item in headerItems" :key="item.target_key">
            <button
              v-if="isAccordionKey(item.target_key) && submenuItems(item.target_key).length"
              type="button"
              :data-testid="`mobile-${item.target_key}-toggle`"
              :aria-expanded="expanded === item.target_key"
              :aria-controls="`mobile-${item.target_key}-panel`"
              @click="toggleAccordionForKey(item.target_key)"
            >
              {{ item.label }}
              <span aria-hidden="true">+</span>
            </button>
            <a v-else :href="item.path" @click="emit('close')">
              {{ item.label }}
            </a>
            <ul
              v-if="isAccordionKey(item.target_key) && submenuItems(item.target_key).length"
              v-show="expanded === item.target_key"
              :id="`mobile-${item.target_key}-panel`"
            >
              <li
                v-for="child in submenuItems(item.target_key)"
                :key="`${child.type}:${child.url}`"
              >
                <a :href="child.url" @click="emit('close')">{{ child.name }}</a>
              </li>
              <li>
                <a :href="item.path" @click="emit('close')">
                  {{ item.label }}
                </a>
              </li>
            </ul>
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
