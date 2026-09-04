<!-- 页面用途：Application 结构化实体列表、创建、编辑、翻译与退役。 -->
<script setup lang="ts">
useHead({ title: 'Catalog Applications', meta: [{ name: 'robots', content: 'noindex, nofollow' }] })
</script>
<template>
  <EntityCrud title="Applications" resource="applications" body-field="description" />
</template>
