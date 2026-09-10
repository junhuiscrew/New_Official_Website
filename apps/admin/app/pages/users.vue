<!-- 页面用途：后台用户基础查看页；中文界面不改变邮箱、角色代码和权限。 -->
<script setup lang="ts">
useHead({
  title: '后台用户',
  meta: [{ name: 'robots', content: 'noindex, nofollow' }],
})

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
      <h1 id="users-title">后台用户</h1>
      <p>中文员工可查看账号状态；角色和权限仍由服务端控制。</p>
      <p v-if="error">无法读取后台用户。</p>
      <table v-else>
        <thead>
          <tr>
            <th>邮箱</th>
            <th>姓名</th>
            <th>角色</th>
            <th>状态</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="user in data?.data || []" :key="user.id">
            <td>{{ user.email }}</td>
            <td>{{ user.display_name || '—' }}</td>
            <td>{{ user.roles.join(', ') || '—' }}</td>
            <td>{{ user.is_active ? '正常' : '已停用' }}</td>
          </tr>
        </tbody>
      </table>
    </section>
  </main>
</template>
