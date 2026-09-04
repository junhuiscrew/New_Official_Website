<!-- 页面用途：荣誉真实 CRUD；只录入可验证事实。 -->
<script setup lang="ts">
useHead({ title: 'Honors', meta: [{ name: 'robots', content: 'noindex, nofollow' }] })
useAuthorityApi()
</script>
<template><TrustCrud title="Honors" resource="honors" /></template>
