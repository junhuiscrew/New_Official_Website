<!-- 页面用途：Solution 结构化实体列表、创建、编辑、翻译与退役。 -->
<script setup lang="ts">
useHead({ title: 'Catalog Solutions', meta: [{ name: 'robots', content: 'noindex, nofollow' }] })
</script>
<template><EntityCrud title="Solutions" resource="solutions" body-field="definition" /></template>
