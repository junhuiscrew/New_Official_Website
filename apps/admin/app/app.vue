<!-- 页面用途：Admin CMS 全局工作台壳，提供分组侧栏、当前页面上下文、Demo标识与安全退出。 -->
<script setup lang="ts">
import { computed, ref } from 'vue'

interface AdminNavItem {
  label: string
  to: string
  permission?: string
  anyPermissions?: string[]
  mark: string
}

interface AdminNavGroup {
  label: string
  items: AdminNavItem[]
}

const { currentUser, logout } = useAuth()
const route = useRoute()
const runtimeConfig = useRuntimeConfig()
const sidebarOpen = ref(false)

const navGroups: AdminNavGroup[] = [
  {
    label: '演示资源',
    items: [
      { label: '工作台', to: '/', mark: 'OV' },
      { label: '演示媒体', to: '/demo-media', permission: 'media.read', mark: 'AV' },
    ],
  },
  {
    label: '内容与产品',
    items: [
      {
        label: '产品与目录',
        to: '/catalog',
        anyPermissions: [
          'catalog.read',
          'material.read',
          'technology.read',
          'application.read',
          'solution.read',
        ],
        mark: 'PD',
      },
      { label: '案例研究', to: '/cases', permission: 'case.read', mark: 'CS' },
      { label: '知识文章', to: '/knowledge', permission: 'knowledge.read', mark: 'KN' },
      { label: '常见问题', to: '/faqs', permission: 'faq.read', mark: 'FQ' },
      { label: '作者与专家', to: '/experts', permission: 'expert.read', mark: 'AU' },
      { label: '信任与能力', to: '/trust', permission: 'content.read', mark: 'TR' },
      { label: '下载资料', to: '/downloads', permission: 'download.read', mark: 'DL' },
    ],
  },
  {
    label: '增长与运营',
    items: [
      { label: '媒体资源库', to: '/media', permission: 'media.read', mark: 'ME' },
      { label: '询盘中心', to: '/rfqs', permission: 'rfq.read', mark: 'RF' },
    ],
  },
  {
    label: '系统',
    items: [
      { label: '语言管理', to: '/locales', permission: 'locale.read', mark: 'LA' },
      { label: '用户', to: '/users', permission: 'user.read', mark: 'US' },
      { label: '角色权限', to: '/roles', permission: 'role.read', mark: 'RB' },
    ],
  },
]

/** 输入导航项；输出当前用户是否拥有展示该入口所需的读取权限。 */
function canSee(item: AdminNavItem): boolean {
  if (!currentUser.value) return false
  if (item.permission) return currentUser.value.permissions.includes(item.permission)
  if (item.anyPermissions) {
    return item.anyPermissions.some((permission) =>
      currentUser.value?.permissions.includes(permission),
    )
  }
  return true
}

const visibleGroups = computed(() =>
  navGroups
    .map((group) => ({ ...group, items: group.items.filter(canSee) }))
    .filter((group) => group.items.length),
)

const pageTitle = computed(() => {
  const fixedTitles: Record<string, string> = {
    '/homepage': '首页编排',
    '/site-overview': '全站模块',
    '/site-pages/products': 'Products SEO',
    '/privacy': '隐私版本',
  }
  const matching = navGroups.flatMap((group) => group.items).find((item) => item.to === route.path)
  return fixedTitles[route.path] || matching?.label || '内容管理'
})

async function handleLogout(): Promise<void> {
  await logout()
  await navigateTo('/login')
}
</script>

<template>
  <div :class="['admin-app', { 'admin-app--authenticated': currentUser }]">
    <!-- 认证侧栏：只展示当前账号实际拥有读取权限的业务入口。 -->
    <ClientOnly>
      <aside v-if="currentUser" :class="['admin-sidebar', { 'admin-sidebar--open': sidebarOpen }]">
        <div class="admin-brand">
          <span class="admin-brand__mark">JH</span>
          <span>
            <strong>JUNHUI</strong>
            <small>Content Operations</small>
          </span>
        </div>
        <div v-if="runtimeConfig.public.demoMode" class="admin-demo-status">
          <span /> 独立演示环境 · DEMO R2
        </div>
        <nav aria-label="管理后台模块">
          <section v-if="currentUser.permissions.includes('content.read')" class="admin-nav-group">
            <h2>总览</h2>
            <NuxtLink to="/site-overview" @click="sidebarOpen = false">
              <span aria-hidden="true">MO</span>
              全站模块
            </NuxtLink>
            <NuxtLink to="/homepage" @click="sidebarOpen = false">
              <span aria-hidden="true">HP</span>
              首页编排
            </NuxtLink>
          </section>
          <section v-for="group in visibleGroups" :key="group.label" class="admin-nav-group">
            <h2>{{ group.label }}</h2>
            <NuxtLink
              v-for="item in group.items"
              :key="item.to"
              :to="item.to"
              @click="sidebarOpen = false"
            >
              <span aria-hidden="true">{{ item.mark }}</span>
              {{ item.label }}
            </NuxtLink>
          </section>
          <section
            v-if="
              currentUser.permissions.includes('seo.read') ||
              currentUser.permissions.includes('privacy.read')
            "
            class="admin-nav-group"
          >
            <h2>内容治理</h2>
            <NuxtLink
              v-if="currentUser.permissions.includes('seo.read')"
              to="/site-pages/products"
              @click="sidebarOpen = false"
            >
              <span aria-hidden="true">SE</span>
              Products SEO
            </NuxtLink>
            <NuxtLink
              v-if="currentUser.permissions.includes('privacy.read')"
              to="/privacy"
              @click="sidebarOpen = false"
            >
              <span aria-hidden="true">PR</span>
              隐私版本
            </NuxtLink>
          </section>
        </nav>
        <div class="admin-sidebar__footer">
          <span class="admin-avatar">{{ (currentUser.display_name || currentUser.email)[0] }}</span>
          <span>
            <strong>{{ currentUser.display_name || 'Demo Administrator' }}</strong>
            <small>{{ currentUser.email }}</small>
          </span>
          <button type="button" title="退出登录" @click="handleLogout">↗</button>
        </div>
      </aside>
    </ClientOnly>

    <div class="admin-main-frame">
      <ClientOnly>
        <header v-if="currentUser" class="admin-topbar">
          <button
            class="admin-topbar__menu"
            type="button"
            aria-label="打开导航"
            :aria-expanded="sidebarOpen"
            @click="sidebarOpen = !sidebarOpen"
          >
            ☰
          </button>
          <div>
            <p>JUNHUI / DEMO CONTENT SYSTEM</p>
            <h1>{{ pageTitle }}</h1>
          </div>
          <a
            class="admin-preview-link"
            :href="String(runtimeConfig.public.websiteUrl || 'https://junhuiscrewbarrel.com')"
            target="_blank"
            rel="noopener"
          >
            查看演示站 <span aria-hidden="true">↗</span>
          </a>
        </header>
      </ClientOnly>
      <div class="admin-page-frame">
        <NuxtPage />
      </div>
    </div>
  </div>
</template>
