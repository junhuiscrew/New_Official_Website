<!-- 页面用途：Locale 基础查看与默认语言切换页。 -->
<script setup lang="ts">
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
const { data, error, refresh } = await useFetch<{ data: LocaleItem[] }>('/locales', {
  baseURL: apiBase,
  credentials: 'include',
  // 等客户端 Guard 完成 session refresh 后再读取 Locale 数据。
  server: false,
})

async function setDefault(localeId: string) {
  if (!currentUser.value?.permissions.includes('locale.manage')) return
  const csrfToken = useCookie<string | null>('junhui_csrf')
  await $fetch(`/locales/${localeId}/set-default`, {
    method: 'POST',
    baseURL: apiBase,
    credentials: 'include',
    headers: { 'X-CSRF-Token': csrfToken.value || '' },
  })
  await refresh()
}
</script>

<template>
  <main class="admin-shell">
    <section aria-labelledby="locales-title">
      <h1 id="locales-title">Locales</h1>
      <p v-if="error">Unable to load locales.</p>
      <ul v-else>
        <li v-for="locale in data?.data || []" :key="locale.id">
          <strong>{{ locale.native_name }}</strong> — /{{ locale.slug }}/ —
          {{ locale.is_enabled ? 'Enabled' : 'Disabled' }}
          <span v-if="locale.is_default">(Default)</span>
          <button v-else type="button" @click="setDefault(locale.id)">Set default</button>
        </li>
      </ul>
    </section>
  </main>
</template>
