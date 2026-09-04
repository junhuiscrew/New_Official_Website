<!-- 页面用途：Phase 3.2 Admin 功能验证总览，不代表最终 CMS Dashboard。 -->
<script setup lang="ts">
import { adminMeta } from '../admin-config'

// 管理后台不应被搜索引擎索引。
useHead({
  htmlAttrs: { lang: 'en' },
  title: adminMeta.title,
  meta: [
    { name: 'description', content: adminMeta.description },
    { name: 'robots', content: adminMeta.robots },
  ],
})
</script>

<template>
  <main class="admin-shell">
    <section aria-labelledby="admin-title">
      <p>Phase 3.2</p>
      <h1 id="admin-title">Junhui Global Website Admin</h1>
      <p>
        Authentication, RBAC, localization and publication foundations are available for
        verification.
      </p>
      <!-- Phase 3.3 Catalog 验证入口；各页面仅用于模型与工作流检查。 -->
      <NuxtLink to="/catalog">Open Structured Core Catalog</NuxtLink>
    </section>
  </main>
</template>
