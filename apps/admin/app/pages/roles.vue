<!-- 页面用途：只读展示 8 个 Role 及 Permission Matrix。 -->
<script setup lang="ts">
interface RoleItem {
  id: string
  name: string
  display_name: string
  permissions: string[]
}
const { apiBase } = useAuth()
const { data, error } = await useFetch<{ data: RoleItem[] }>('/rbac/roles', {
  baseURL: apiBase,
  credentials: 'include',
  // SSR 仅渲染安全壳，避免把受保护矩阵写进服务端 HTML。
  server: false,
})
</script>

<template>
  <main class="admin-shell">
    <section aria-labelledby="roles-title">
      <h1 id="roles-title">Roles & Permissions</h1>
      <p v-if="error">Unable to load roles.</p>
      <article v-for="role in data?.data || []" v-else :key="role.id">
        <h2>
          {{ role.display_name }} <small>{{ role.name }}</small>
        </h2>
        <p>{{ role.permissions.join(', ') || 'No permissions' }}</p>
      </article>
    </section>
  </main>
</template>
