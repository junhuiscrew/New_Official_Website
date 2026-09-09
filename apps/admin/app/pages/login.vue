<!-- 页面用途：Admin 安全登录页，凭据通过同源 API 交换为 HttpOnly Cookie。 -->
<script setup lang="ts">
const email = ref('')
const password = ref('')
const errorMessage = ref('')
const pending = ref(false)
const { login } = useAuth()

async function submitLogin() {
  pending.value = true
  errorMessage.value = ''
  try {
    await login(email.value, password.value)
    await navigateTo('/')
  } catch {
    errorMessage.value = '邮箱或密码不正确，或账号已停用。'
  } finally {
    pending.value = false
  }
}
</script>

<template>
  <main class="admin-shell">
    <form aria-labelledby="login-title" @submit.prevent="submitLogin">
      <p>JUNHUI · CONTENT OPERATIONS</p>
      <h1 id="login-title">登录管理后台</h1>
      <span>使用后台应用账号访问独立 Demo R2 内容与媒体。</span>
      <label>邮箱 <input v-model="email" type="email" autocomplete="username" required /></label>
      <label>
        密码
        <input v-model="password" type="password" autocomplete="current-password" required />
      </label>
      <p v-if="errorMessage" role="alert">{{ errorMessage }}</p>
      <button type="submit" :disabled="pending">{{ pending ? '正在登录…' : '安全登录' }}</button>
    </form>
  </main>
</template>
