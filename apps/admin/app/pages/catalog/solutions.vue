<!-- 页面用途：Solution 结构化实体列表、创建、编辑、翻译与退役。 -->
<script setup lang="ts">
import EntityCrud from '~/components/catalog/EntityCrud.vue'

useHead({
  title: '解决方案',
  meta: [{ name: 'robots', content: 'noindex, nofollow' }],
})
</script>
<template>
  <EntityCrud title="解决方案" resource="solutions" body-field="definition" />
</template>
