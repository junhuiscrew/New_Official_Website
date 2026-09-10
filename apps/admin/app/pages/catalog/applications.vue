<!-- 页面用途：Application 结构化实体列表、创建、编辑、翻译与退役。 -->
<script setup lang="ts">
import EntityCrud from '~/components/catalog/EntityCrud.vue'

useHead({
  title: '应用场景',
  meta: [{ name: 'robots', content: 'noindex, nofollow' }],
})
</script>
<template>
  <EntityCrud title="应用场景" resource="applications" body-field="description" />
</template>
