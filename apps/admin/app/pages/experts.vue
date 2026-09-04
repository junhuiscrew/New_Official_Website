<!-- 页面用途：真实 Author/Expert 资料、核验与公开资料页控制的最小真实 CRUD。 -->
<script setup lang="ts">
useHead({ title: 'Experts', meta: [{ name: 'robots', content: 'noindex, nofollow' }] })
</script>
<template><AuthorityCrud title="Authors & Experts" resource="experts" /></template>
