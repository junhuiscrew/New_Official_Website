<!-- 页面用途：Structured Core Catalog 最小验证入口，不代表最终 CMS UI。 -->
<script setup lang="ts">
import { adminMeta } from '../../admin-config'

// Admin 页面统一禁止搜索引擎收录；真正权限仍由 FastAPI RBAC 校验。
useHead({
  title: `Catalog · ${adminMeta.title}`,
  meta: [{ name: 'robots', content: 'noindex, nofollow' }],
})
</script>

<template>
  <main class="admin-shell">
    <h1>Structured Core Catalog</h1>
    <p>Phase 3.3 最小模型与发布工作流验证入口。</p>
    <nav aria-label="Catalog entities">
      <NuxtLink
        v-for="item in [
          'categories',
          'products',
          'materials',
          'technologies',
          'applications',
          'solutions',
          'specifications',
        ]"
        :key="item"
        :to="`/catalog/${item}`"
      >
        {{ item }}
      </NuxtLink>
    </nav>
  </main>
</template>
