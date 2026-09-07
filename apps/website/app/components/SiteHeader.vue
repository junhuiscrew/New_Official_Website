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
import type { LocaleSlug, NavigationDto } from '~/types/public'

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
const primary = computed(() => new Set(props.navigation.primary))

/** 保存各桌面 disclosure 按钮，关闭菜单时用于焦点回收。 */
function setMenuButton(key: MenuKey, element: unknown): void {
  if (element instanceof HTMLButtonElement) menuButtons.set(key, element)
}

/** 打开指定菜单；再次点击同一按钮时关闭。 */
function toggleMenu(key: MenuKey): void {
  openMenu.value = openMenu.value === key ? null : key
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
        <img src="/brand/junhui-wordmark.png" alt="" width="220" height="60" />
      </a>

      <nav class="desktop-nav" data-testid="desktop-nav" :aria-label="labels.navigation.menu">
        <div v-if="primary.has('products')" class="desktop-nav__item">
          <button
            v-if="hasProducts"
            :ref="(element) => setMenuButton('products', element)"
            type="button"
            data-testid="desktop-products-toggle"
            :aria-expanded="openMenu === 'products'"
            aria-controls="products-mega-menu"
            @click="toggleMenu('products')"
          >
            {{ labels.navigation.products }}
          </button>
          <a v-else :href="`/${locale}/products/`">{{ labels.navigation.products }}</a>
          <MegaMenu
            v-if="hasProducts"
            id="products-mega-menu"
            test-id="products-mega-menu"
            :open="openMenu === 'products'"
            :sections="productSections"
            :view-all="{
              label: labels.navigation.viewAllProducts,
              href: `/${locale}/products/`,
            }"
            @close="closeMenu(true)"
          />
        </div>
        <div v-if="primary.has('solutions')" class="desktop-nav__item">
          <button
            v-if="hasSolutions"
            :ref="(element) => setMenuButton('solutions', element)"
            type="button"
            data-testid="desktop-solutions-toggle"
            :aria-expanded="openMenu === 'solutions'"
            aria-controls="solutions-mega-menu"
            @click="toggleMenu('solutions')"
          >
            {{ labels.navigation.solutions }}
          </button>
          <a v-else :href="`/${locale}/solutions/`">{{ labels.navigation.solutions }}</a>
          <MegaMenu
            v-if="hasSolutions"
            id="solutions-mega-menu"
            test-id="solutions-mega-menu"
            :open="openMenu === 'solutions'"
            :sections="solutionSections"
            :view-all="{
              label: labels.navigation.viewAllSolutions,
              href: `/${locale}/solutions/`,
            }"
            @close="closeMenu(true)"
          />
        </div>
        <div v-if="primary.has('materials')" class="desktop-nav__item">
          <button
            v-if="navigation.materials.length"
            :ref="(element) => setMenuButton('materials', element)"
            type="button"
            :aria-expanded="openMenu === 'materials'"
            aria-controls="materials-mega-menu"
            @click="toggleMenu('materials')"
          >
            {{ labels.navigation.materials }}
          </button>
          <a v-else :href="`/${locale}/materials/`">{{ labels.navigation.materials }}</a>
          <MegaMenu
            v-if="navigation.materials.length"
            id="materials-mega-menu"
            test-id="materials-mega-menu"
            :open="openMenu === 'materials'"
            :sections="materialSections"
            :view-all="{
              label: labels.navigation.viewAllMaterials,
              href: `/${locale}/materials/`,
            }"
            @close="closeMenu(true)"
          />
        </div>
        <div v-if="primary.has('applications')" class="desktop-nav__item">
          <button
            v-if="navigation.applications.length"
            :ref="(element) => setMenuButton('applications', element)"
            type="button"
            :aria-expanded="openMenu === 'applications'"
            aria-controls="applications-mega-menu"
            @click="toggleMenu('applications')"
          >
            {{ labels.navigation.applications }}
          </button>
          <a v-else :href="`/${locale}/applications/`">{{ labels.navigation.applications }}</a>
          <MegaMenu
            v-if="navigation.applications.length"
            id="applications-mega-menu"
            test-id="applications-mega-menu"
            :open="openMenu === 'applications'"
            :sections="applicationSections"
            :view-all="{
              label: labels.navigation.viewAllApplications,
              href: `/${locale}/applications/`,
            }"
            @close="closeMenu(true)"
          />
        </div>
        <a v-if="primary.has('capabilities')" :href="`/${locale}/capabilities/`">{{
          labels.navigation.capabilities
        }}</a>
        <a v-if="primary.has('case_studies')" :href="`/${locale}/case-studies/`">{{
          labels.navigation.caseStudies
        }}</a>
        <a v-if="primary.has('knowledge')" :href="`/${locale}/knowledge/`">{{
          labels.navigation.knowledge
        }}</a>
        <a v-if="primary.has('about')" :href="`/${locale}/about/`">{{ labels.navigation.about }}</a>
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
