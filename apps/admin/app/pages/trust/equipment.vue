<!-- 页面用途：设备真实 CRUD。 -->
<script setup lang="ts">
useHead({
  title: '生产设备',
  meta: [{ name: 'robots', content: 'noindex, nofollow' }],
})
useAuthorityApi()
</script>
<template><TrustCrud title="生产设备" resource="equipment" /></template>
