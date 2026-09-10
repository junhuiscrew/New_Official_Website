<!-- 页面用途：Technology 结构化实体列表、创建、编辑、翻译与退役。 -->
<script setup lang="ts">
import EntityCrud from '~/components/catalog/EntityCrud.vue'

useHead({
  title: '技术工艺',
  meta: [{ name: 'robots', content: 'noindex, nofollow' }],
})
</script>
<template>
  <EntityCrud title="技术工艺" resource="technologies" body-field="definition" />
</template>
