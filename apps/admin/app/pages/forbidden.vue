<!-- 页面用途：展示 API 权限不足后的安全禁止访问状态。 -->
<template>
  <main class="admin-shell">
    <section aria-labelledby="forbidden-title">
      <h1 id="forbidden-title">403 Forbidden</h1>
      <p>当前账号没有访问此模块的权限。</p>
      <NuxtLink to="/">返回工作台</NuxtLink>
    </section>
  </main>
</template>
