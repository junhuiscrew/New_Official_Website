<!-- 页面用途：制造能力真实 CRUD。 -->
<script setup lang="ts">
useHead({ title: 'Capabilities', meta: [{ name: 'robots', content: 'noindex, nofollow' }] })
useAuthorityApi()
</script>
<template><TrustCrud title="Manufacturing Capabilities" resource="capabilities" /></template>
