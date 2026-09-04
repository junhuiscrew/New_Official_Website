<!-- 页面用途：设备真实 CRUD。 -->
<script setup lang="ts">
useHead({ title: 'Equipment', meta: [{ name: 'robots', content: 'noindex, nofollow' }] })
useAuthorityApi()
</script>
<template><TrustCrud title="Equipment" resource="equipment" /></template>
