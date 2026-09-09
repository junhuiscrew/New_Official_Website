<!-- 页面用途：全局公开站点 SSR 布局，一次取得导航与 Footer 数据并包裹页面正文。 -->
<script setup lang="ts">
import { computed } from 'vue'

import { ui } from '~/i18n/ui'
import type { NavigationDto } from '~/types/public'
import { resolveRouteLocale } from '~/composables/useLocalePath'

interface NavigationEnvelope {
  success: boolean
  data: NavigationDto | null
  error: unknown | null
}

type AlternateMap = Readonly<Record<string, string | null | undefined>>

const route = useRoute()
const api = useApi()
const currentLocale = computed(() => resolveRouteLocale(route.params.lang, route.path))
const currentYear = useState('public-current-year', () => new Date().getUTCFullYear())

/** 返回当前语言的空导航 DTO，API 可选组为空或暂不可用时保留静态入口。 */
function emptyNavigation(locale: NavigationDto['locale']): NavigationDto {
  return {
    locale,
    demo_mode: false,
    primary: [],
    products: { categories: [], featured: [] },
    solutions: { featured: [], problems: [] },
    materials: [],
    applications: [],
    company: null,
  }
}

// 使用语言组成稳定 key，让导航数据参与 Nuxt SSR payload 并避免 hydration 后重复请求。
const navigationKey = computed(() => {
  const locale = currentLocale.value
  return `navigation:${locale}`
})
const { data: navigationResponse } = await useAsyncData(
  navigationKey,
  () => {
    const locale = currentLocale.value
    return api<NavigationEnvelope>(`/public/navigation/${locale}`)
  },
  { default: () => null },
)
const navigation = computed(() => {
  const response = navigationResponse.value
  return response?.success && response.data ? response.data : emptyNavigation(currentLocale.value)
})

// 页面可通过 route meta 注入 SSR alternate；组件还会读取现有 hreflang head 作为 SPA 导航后备。
const alternates = computed(() => (route.meta.alternates as AlternateMap | undefined) ?? null)
</script>

<template>
  <div class="site-shell">
    <a class="skip-link" href="#main-content">{{ ui[currentLocale].common.skipToContent }}</a>
    <SiteHeader :navigation="navigation" :locale="currentLocale" :alternates="alternates" />
    <main id="main-content" tabindex="-1">
      <slot />
    </main>
    <SiteFooter :navigation="navigation" :locale="currentLocale" :year="currentYear" />
  </div>
</template>

<style scoped>
.site-shell {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

main {
  flex: 1;
}

.skip-link {
  position: fixed;
  inset-block-start: var(--space-2);
  inset-inline-start: var(--space-2);
  z-index: 100;
  padding: var(--space-2) var(--space-4);
  color: var(--color-white);
  background: var(--color-blue-700);
  transform: translateY(-200%);
}

.skip-link:focus {
  transform: translateY(0);
}
</style>
