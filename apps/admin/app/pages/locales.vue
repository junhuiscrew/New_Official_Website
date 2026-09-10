<!-- 页面用途：网站语言基础查看与默认语言切换页；Locale 代码保持原值。 -->
<script setup lang="ts">
useHead({
  title: '网站语言',
  meta: [{ name: 'robots', content: 'noindex, nofollow' }],
})

interface LocaleItem {
  id: string
  code: string
  slug: string
  native_name: string
  is_default: boolean
  is_enabled: boolean
  sort_order: number
}
const { apiBase, currentUser } = useAuth()
const authorityApi = useAuthorityApi()
const { data, error, refresh } = await useFetch<{ data: LocaleItem[] }>('/locales', {
  baseURL: apiBase,
  credentials: 'include',
  // 等客户端 Guard 完成 session refresh 后再读取 Locale 数据。
  server: false,
})

async function setDefault(localeId: string) {
  if (!currentUser.value?.permissions.includes('locale.manage')) return
  // 复用统一认证请求，使长时间打开页面后的写操作可以安全恢复过期会话。
  await authorityApi.request(`/locales/${localeId}/set-default`, {
    method: 'POST',
  })
  await refresh()
}
</script>

<template>
  <main class="admin-shell">
    <section aria-labelledby="locales-title">
      <h1 id="locales-title">网站语言</h1>
      <p>中文操作界面不改变 Locale、路径或业务正文。</p>
      <p v-if="error">无法读取网站语言。</p>
      <ul v-else>
        <li v-for="locale in data?.data || []" :key="locale.id">
          <strong>{{ locale.native_name }}</strong> — /{{ locale.slug }}/ —
          {{ locale.is_enabled ? '已启用' : '已停用' }}
          <span v-if="locale.is_default">（默认语言）</span>
          <button v-else type="button" @click="setDefault(locale.id)">设为默认语言</button>
        </li>
      </ul>
    </section>
  </main>
</template>
