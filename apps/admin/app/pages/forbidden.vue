<!-- 页面用途：展示 API 权限不足后的安全禁止访问状态。 -->
<template>
  <main class="admin-shell">
    <section aria-labelledby="forbidden-title">
      <h1 id="forbidden-title">403 Forbidden</h1>
      <p>Your account does not have permission to access this module.</p>
      <NuxtLink to="/">Return to overview</NuxtLink>
    </section>
  </main>
</template>
