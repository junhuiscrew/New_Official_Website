<!-- 页面用途：Admin CMS 应用根壳，提供 Phase 3.2 功能验证导航与全局退出。 -->
<script setup lang="ts">
const { currentUser, logout } = useAuth()

async function handleLogout() {
  await logout()
  await navigateTo('/login')
}
</script>

<template>
  <header v-if="currentUser" class="admin-nav">
    <strong>Junhui Admin</strong>
    <nav aria-label="Admin modules">
      <NuxtLink to="/">Overview</NuxtLink>
      <NuxtLink v-if="currentUser.permissions.includes('user.read')" to="/users">Users</NuxtLink>
      <NuxtLink v-if="currentUser.permissions.includes('role.read')" to="/roles">Roles</NuxtLink>
      <NuxtLink v-if="currentUser.permissions.includes('locale.read')" to="/locales"
        >Locales</NuxtLink
      >
    </nav>
    <span>{{ currentUser.display_name || currentUser.email }}</span>
    <button type="button" @click="handleLogout">Logout</button>
  </header>
  <NuxtPage />
</template>
