<!-- 页面用途：真实 Author/Expert 资料、核验与公开资料页控制的最小真实 CRUD。 -->
<script setup lang="ts">
useHead({
  title: '作者与专家',
  meta: [{ name: 'robots', content: 'noindex, nofollow' }],
})
</script>
<template><AuthorityCrud title="作者与专家" resource="experts" /></template>
