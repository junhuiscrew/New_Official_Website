<!-- 页面用途：制造能力真实 CRUD。 -->
<script setup lang="ts">
useHead({
  title: '制造能力',
  meta: [{ name: 'robots', content: 'noindex, nofollow' }],
})
useAuthorityApi()
</script>
<template><TrustCrud title="制造能力" resource="capabilities" /></template>
