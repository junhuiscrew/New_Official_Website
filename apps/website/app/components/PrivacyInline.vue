<!-- 组件职责：递归渲染受限 Markdown 行内节点。 -->
<script setup lang="ts">
import type { PrivacyInlineNode } from '~/utils/privacyMarkdown'

defineProps<{ nodes: PrivacyInlineNode[] }>()
</script>

<template>
  <template v-for="(node, index) in nodes" :key="index">
    <template v-if="node.type === 'text'">{{ node.value }}</template>
    <code v-else-if="node.type === 'code'">{{ node.value }}</code>
    <strong v-else-if="node.type === 'strong'"><PrivacyInline :nodes="node.children" /></strong>
    <em v-else-if="node.type === 'emphasis'"><PrivacyInline :nodes="node.children" /></em>
    <a v-else :href="node.href"><PrivacyInline :nodes="node.children" /></a>
  </template>
</template>
