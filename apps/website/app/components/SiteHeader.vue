<!-- 组件职责：组合品牌、桌面 disclosure 导航、移动导航及全局转化入口。 -->
<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'

import LanguageSwitcher from './LanguageSwitcher.vue'
import MegaMenu from './MegaMenu.vue'
import MobileNav from './MobileNav.vue'
import SearchButton from './SearchButton.vue'
import type { MegaMenuSection } from './MegaMenu.vue'
import { useTelemetry } from '~/composables/useTelemetry'
import { ui } from '~/i18n/ui'
import type { LocaleSlug, NavigationDto, NavigationMenuItemDto } from '~/types/public'

type MenuKey = 'products' | 'solutions' | 'materials' | 'applications'

const props = withDefaults(
  defineProps<{
    navigation: NavigationDto
    locale: LocaleSlug
    alternates?: Readonly<Record<string, string | null | undefined>> | null
  }>(),
  { alternates: null },
)

const root = ref<HTMLElement | null>(null)
const mobileToggle = ref<HTMLButtonElement | null>(null)
const menuButtons = new Map<MenuKey, HTMLButtonElement>()
const openMenu = ref<MenuKey | null>(null)
const mobileOpen = ref(false)
const labels = computed(() => ui[props.locale])
const telemetry = useTelemetry()

const productSections = computed<MegaMenuSection[]>(() => [
  {
    key: 'categories',
    title: labels.value.sections.productCategories,
    items: props.navigation.products.categories,
  },
  {
    key: 'featured',
    title: labels.value.sections.featuredProducts,
    items: props.navigation.products.featured,
  },
])
const solutionSections = computed<MegaMenuSection[]>(() => [
  {
    key: 'featured',
    title: labels.value.navigation.solutions,
    items: props.navigation.solutions.featured,
  },
  {
    key: 'problems',
    title: labels.value.navigation.solveAProblem,
    items: props.navigation.solutions.problems,
  },
])
const materialSections = computed<MegaMenuSection[]>(() => [
  { key: 'materials', title: labels.value.navigation.materials, items: props.navigation.materials },
])
const applicationSections = computed<MegaMenuSection[]>(() => [
  {
    key: 'applications',
    title: labels.value.navigation.applications,
    items: props.navigation.applications,
  },
])

const hasProducts = computed(
  () =>
    props.navigation.products.categories.length > 0 ||
    props.navigation.products.featured.length > 0,
)
const hasSolutions = computed(
  () =>
    props.navigation.solutions.featured.length > 0 ||
    props.navigation.solutions.problems.length > 0,
)
const brandLogo = computed(
  () => props.navigation.brand?.media.header_logo?.url ?? '/brand/junhui-wordmark.png',
)

// 新设置未初始化时按旧合同生成等值菜单，避免部署迁移窗口造成导航归零。
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

/** 判断菜单项是否属于带动态内容的四个 Mega Menu。 */
function isMenuKey(key: string): key is MenuKey {
  return ['products', 'solutions', 'materials', 'applications'].includes(key)
}

/** 返回指定 Mega Menu 是否已有当前语言公开内容。 */
function hasMenuContent(key: string): boolean {
  if (!isMenuKey(key)) return false
  if (key === 'products') return hasProducts.value
  if (key === 'solutions') return hasSolutions.value
  if (key === 'materials') return props.navigation.materials.length > 0
  return props.navigation.applications.length > 0
}

/** 返回指定 Mega Menu 的发布内容分组。 */
function menuSections(key: string): MegaMenuSection[] {
  if (!isMenuKey(key)) return []
  if (key === 'products') return productSections.value
  if (key === 'solutions') return solutionSections.value
  if (key === 'materials') return materialSections.value
  return applicationSections.value
}

/** 保存各桌面 disclosure 按钮，关闭菜单时用于焦点回收。 */
function setMenuButton(key: MenuKey, element: unknown): void {
  if (element instanceof HTMLButtonElement) menuButtons.set(key, element)
}

/** 输入任意服务端目标键和元素；输出无，仅登记受支持 Mega Menu 按钮。 */
function setMenuButtonForKey(key: string, element: unknown): void {
  if (isMenuKey(key)) setMenuButton(key, element)
}

/** 打开指定菜单；再次点击同一按钮时关闭。 */
function toggleMenu(key: MenuKey): void {
  openMenu.value = openMenu.value === key ? null : key
}

/** 输入任意服务端目标键；输出无，仅切换受支持 Mega Menu。 */
function toggleMenuForKey(key: string): void {
  if (isMenuKey(key)) toggleMenu(key)
}

/** 关闭当前桌面菜单，并在 Escape/外部点击时恢复触发按钮焦点。 */
function closeMenu(restoreFocus = false): void {
  const previous = openMenu.value
  if (!previous) return
  openMenu.value = null
  if (restoreFocus) nextTick(() => menuButtons.get(previous)?.focus())
}

/** 关闭移动菜单并把焦点返回 hamburger。 */
function closeMobile(): void {
  if (!mobileOpen.value) return
  mobileOpen.value = false
  nextTick(() => mobileToggle.value?.focus())
}

/** 点击 Header 之外时仅关闭桌面浮层，不干扰正常导航。 */
function onDocumentClick(event: MouseEvent): void {
  if (openMenu.value && !root.value?.contains(event.target as Node)) closeMenu(false)
}

/** Escape 优先关闭当前移动或桌面导航并完成焦点回收。 */
function onDocumentKeydown(event: KeyboardEvent): void {
  if (event.key !== 'Escape') return
  if (mobileOpen.value) closeMobile()
  else closeMenu(true)
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
  <header ref="root" class="site-header">
    <div class="site-header__inner">
      <a class="site-header__brand" :href="`/${locale}/`" :aria-label="labels.navigation.home">
        <img :src="brandLogo" :alt="navigation.brand?.display_name ?? ''" width="220" height="60" />
      </a>

      <nav class="desktop-nav" data-testid="desktop-nav" :aria-label="labels.navigation.menu">
        <div
          v-for="item in headerItems"
          :key="item.target_key"
          class="desktop-nav__item"
          :data-menu-key="item.target_key"
        >
          <template v-if="isMenuKey(item.target_key)">
            <button
              v-if="hasMenuContent(item.target_key)"
              :ref="(element) => setMenuButtonForKey(item.target_key, element)"
              type="button"
              :data-testid="`desktop-${item.target_key}-toggle`"
              :aria-expanded="openMenu === item.target_key"
              :aria-controls="`${item.target_key}-mega-menu`"
              @click="toggleMenuForKey(item.target_key)"
            >
              {{ item.label }}
            </button>
            <a v-else :href="item.path">{{ item.label }}</a>
            <MegaMenu
              v-if="hasMenuContent(item.target_key)"
              :id="`${item.target_key}-mega-menu`"
              :test-id="`${item.target_key}-mega-menu`"
              :open="openMenu === item.target_key"
              :sections="menuSections(item.target_key)"
              :view-all="{
                label: item.label,
                href: item.path,
              }"
              @close="closeMenu(true)"
            />
          </template>
          <a v-else :href="item.path">{{ item.label }}</a>
        </div>
      </nav>

      <div class="site-header__actions" @click.capture="closeMenu(false)">
        <SearchButton :locale="locale" />
        <LanguageSwitcher :locale="locale" :alternates="alternates" />
        <a
          class="site-header__rfq"
          data-testid="rfq-cta"
          :href="`/${locale}/request-a-quote/`"
          @click="telemetry.track('rfq_cta_click', { locale })"
        >
          {{ labels.cta.requestQuote }}
        </a>
      </div>

      <button
        ref="mobileToggle"
        class="site-header__mobile-toggle"
        data-testid="mobile-nav-toggle"
        type="button"
        :aria-label="mobileOpen ? labels.navigation.closeMenu : labels.navigation.menu"
        :aria-expanded="mobileOpen"
        aria-controls="mobile-navigation"
        @click="mobileOpen = !mobileOpen"
      >
        <span aria-hidden="true" />
        <span aria-hidden="true" />
        <span aria-hidden="true" />
      </button>
    </div>

    <MobileNav
      v-if="mobileOpen"
      id="mobile-navigation"
      :open="mobileOpen"
      :navigation="navigation"
      :locale="locale"
      :alternates="alternates"
      @close="closeMobile"
    />
  </header>
</template>

<style scoped>
.site-header {
  position: relative;
  z-index: 40;
  color: var(--color-white);
  background: var(--color-navy-900);
  border-block-end: 3px solid var(--color-blue-600);
}

.site-header__inner {
  width: min(calc(100% - var(--space-8)), var(--container-max));
  min-height: 5rem;
  margin-inline: auto;
  display: flex;
  align-items: center;
  gap: var(--space-6);
}

.site-header__brand {
  flex: 0 0 auto;
}

.site-header__brand img {
  width: auto;
  height: 2.75rem;
  display: block;
}

.desktop-nav {
  min-width: 0;
  display: flex;
  align-items: stretch;
  gap: clamp(var(--space-2), 1.3vw, var(--space-5));
}

.desktop-nav__item {
  display: flex;
}

.desktop-nav a,
.desktop-nav button {
  display: inline-flex;
  align-items: center;
  padding: var(--space-2) 0;
  color: inherit;
  font: inherit;
  font-size: var(--font-size-small);
  white-space: nowrap;
  text-decoration: none;
  background: transparent;
  border: 0;
  cursor: pointer;
}

.desktop-nav button::after {
  content: '';
  width: 0.4rem;
  height: 0.4rem;
  margin-inline-start: var(--space-2);
  border-inline-end: 1px solid;
  border-block-end: 1px solid;
  transform: translateY(-0.15rem) rotate(45deg);
}

.desktop-nav a:hover,
.desktop-nav button:hover,
.desktop-nav button[aria-expanded='true'] {
  color: var(--color-blue-100);
}

.site-header__actions {
  margin-inline-start: auto;
  display: flex;
  align-items: center;
  gap: var(--space-4);
  font-size: var(--font-size-small);
  white-space: nowrap;
}

.site-header__rfq {
  padding: var(--space-3) var(--space-4);
  color: var(--color-white);
  font-weight: 700;
  text-decoration: none;
  background: var(--color-blue-600);
  border-radius: var(--radius-sm);
}

.site-header__mobile-toggle {
  width: 2.75rem;
  height: 2.75rem;
  margin-inline-start: auto;
  display: none;
  padding: 0.65rem;
  color: inherit;
  background: transparent;
  border: 1px solid var(--color-neutral-500);
  cursor: pointer;
}

.site-header__mobile-toggle span {
  height: 1px;
  display: block;
  background: currentColor;
}

.site-header__mobile-toggle span + span {
  margin-block-start: 0.32rem;
}

@media (max-width: 74rem) {
  .desktop-nav,
  .site-header__actions {
    display: none;
  }

  .site-header__mobile-toggle {
    display: block;
  }
}

@media (max-width: 23.4375rem) {
  .site-header__inner {
    width: min(calc(100% - var(--space-4)), var(--container-max));
  }

  .site-header__brand img {
    max-width: 11rem;
    height: auto;
  }
}
</style>
