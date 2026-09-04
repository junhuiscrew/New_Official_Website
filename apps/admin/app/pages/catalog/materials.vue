<!-- 页面用途：Material 结构化实体列表、创建、编辑、翻译与退役。 -->
<script setup lang="ts">
useHead({ title: 'Catalog Materials', meta: [{ name: 'robots', content: 'noindex, nofollow' }] })
</script>
<template><EntityCrud title="Materials" resource="materials" body-field="definition" /></template>
