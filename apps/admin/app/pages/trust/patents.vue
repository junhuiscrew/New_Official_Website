<!-- 页面用途：专利真实 CRUD；禁止创建虚假专利。 -->
<script setup lang="ts">
useHead({ title: 'Patents', meta: [{ name: 'robots', content: 'noindex, nofollow' }] })
useAuthorityApi()
</script>
<template><TrustCrud title="Patents" resource="patents" /></template>
