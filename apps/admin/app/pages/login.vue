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
    errorMessage.value = 'Email or password is incorrect, or the account is inactive.'
  } finally {
    pending.value = false
  }
}
</script>

<template>
  <main class="admin-shell">
    <form aria-labelledby="login-title" @submit.prevent="submitLogin">
      <p>Phase 3.2</p>
      <h1 id="login-title">Admin Login</h1>
      <label>Email <input v-model="email" type="email" autocomplete="username" required /></label>
      <label>
        Password
        <input v-model="password" type="password" autocomplete="current-password" required />
      </label>
      <p v-if="errorMessage" role="alert">{{ errorMessage }}</p>
      <button type="submit" :disabled="pending">{{ pending ? 'Signing in…' : 'Sign in' }}</button>
    </form>
  </main>
</template>
