<!-- 组件职责：展示与 BreadcrumbList JSON-LD 完全一致的可见导航路径。 -->
<script setup lang="ts">
defineProps<{ items: Array<{ name: string; url: string }> }>()
</script>

<template>
  <nav aria-label="Breadcrumb" class="public-breadcrumb">
    <ol>
      <li v-for="(item, index) in items" :key="item.url">
        <a v-if="index < items.length - 1" :href="item.url">{{ item.name }}</a>
        <span v-else aria-current="page">{{ item.name }}</span>
      </li>
    </ol>
  </nav>
</template>
