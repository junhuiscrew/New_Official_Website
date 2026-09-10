<!-- 页面用途：荣誉真实 CRUD；只录入可验证事实。 -->
<script setup lang="ts">
useHead({
  title: '荣誉',
  meta: [{ name: 'robots', content: 'noindex, nofollow' }],
})
useAuthorityApi()
</script>
<template><TrustCrud title="荣誉" resource="honors" /></template>
