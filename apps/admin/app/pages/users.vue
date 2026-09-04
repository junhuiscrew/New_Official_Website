<!-- 页面用途：Users 基础查看页；创建、编辑能力以 API 服务端权限为准。 -->
<script setup lang="ts">
interface UserItem {
  id: string
  email: string
  display_name: string | null
  is_active: boolean
  roles: string[]
}

const { apiBase } = useAuth()
const { data, error } = await useFetch<{ data: UserItem[] }>('/users', {
  baseURL: apiBase,
  credentials: 'include',
  // Admin 受保护数据只在客户端 Guard 完成认证/refresh 后加载。
  server: false,
})
</script>

<template>
  <main class="admin-shell">
    <section aria-labelledby="users-title">
      <h1 id="users-title">Users</h1>
      <p v-if="error">Unable to load users.</p>
      <table v-else>
        <thead>
          <tr>
            <th>Email</th>
            <th>Name</th>
            <th>Roles</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="user in data?.data || []" :key="user.id">
            <td>{{ user.email }}</td>
            <td>{{ user.display_name || '—' }}</td>
            <td>{{ user.roles.join(', ') || '—' }}</td>
            <td>{{ user.is_active ? 'Active' : 'Disabled' }}</td>
          </tr>
        </tbody>
      </table>
    </section>
  </main>
</template>
