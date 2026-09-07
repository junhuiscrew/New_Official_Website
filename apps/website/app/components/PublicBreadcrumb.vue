<!-- 组件职责：展示与 BreadcrumbList JSON-LD 完全一致的可见导航路径。 -->
<script setup lang="ts">
import { sameSiteRelativeTarget } from '~/composables/useLocalePath'

defineProps<{ items: Array<{ name: string; url: string }> }>()

/** 只把正式本站来源转换为当前预览可跟随的相对路径，异常来源回退首页。 */
function navigationTarget(url: string): string {
  return sameSiteRelativeTarget(url, '/')
}
</script>

<template>
  <nav aria-label="Breadcrumb" class="public-breadcrumb">
    <ol>
      <li v-for="(item, index) in items" :key="item.url">
        <a v-if="index < items.length - 1" :href="navigationTarget(item.url)">{{ item.name }}</a>
        <span v-else aria-current="page">{{ item.name }}</span>
      </li>
    </ol>
  </nav>
</template>
