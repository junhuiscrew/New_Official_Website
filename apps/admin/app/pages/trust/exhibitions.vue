<!-- 页面用途：展会真实 CRUD 与统一发布入口。 -->
<script setup lang="ts">
useHead({ title: 'Exhibitions', meta: [{ name: 'robots', content: 'noindex, nofollow' }] })
useAuthorityApi()
</script>
<template><TrustCrud title="Exhibitions" resource="exhibitions" /></template>
