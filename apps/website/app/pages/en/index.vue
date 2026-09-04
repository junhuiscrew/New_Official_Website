<!-- 页面用途：English 最小 SSR placeholder，不代表最终首页 UI。 -->
<script setup lang="ts">
import { localePages } from '../../site-config'

const page = localePages.en
</script>

<template>
  <LocalePlaceholder :page="page" />
</template>
