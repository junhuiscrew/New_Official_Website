<!-- 页面用途：Admin CMS 最小占位页，不包含最终登录或内容管理界面。 -->
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
      <p>Phase 3.1</p>
      <h1 id="admin-title">Junhui Global Website Admin</h1>
      <p>
        Administration foundation is running. Authentication and CMS features begin in Phase 3.2.
      </p>
    </section>
  </main>
</template>
