<!-- 页面用途：专利真实 CRUD；禁止创建虚假专利。 -->
<script setup lang="ts">
useHead({
  title: '专利',
  meta: [{ name: 'robots', content: 'noindex, nofollow' }],
})
useAuthorityApi()
</script>
<template><TrustCrud title="专利" resource="patents" /></template>
