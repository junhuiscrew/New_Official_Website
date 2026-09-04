<!-- 页面用途：Technology 结构化实体列表、创建、编辑、翻译与退役。 -->
<script setup lang="ts">
useHead({ title: 'Catalog Technologies', meta: [{ name: 'robots', content: 'noindex, nofollow' }] })
</script>
<template>
  <EntityCrud title="Technologies" resource="technologies" body-field="definition" />
</template>
