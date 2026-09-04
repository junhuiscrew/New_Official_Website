<!-- 页面用途：简体中文最小 SSR placeholder，不代表最终首页 UI。 -->
<script setup lang="ts">
import { localePages } from '../../site-config'

const page = localePages['zh-cn']
</script>

<template>
  <LocalePlaceholder :page="page" />
</template>
