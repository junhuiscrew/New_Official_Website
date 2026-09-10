<!-- 页面用途：Material 结构化实体列表、创建、编辑、翻译与退役。 -->
<script setup lang="ts">
import EntityCrud from '~/components/catalog/EntityCrud.vue'

useHead({
  title: '材料',
  meta: [{ name: 'robots', content: 'noindex, nofollow' }],
})
</script>
<template>
  <EntityCrud title="材料" resource="materials" body-field="definition" />
</template>
