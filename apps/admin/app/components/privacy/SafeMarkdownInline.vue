<!-- 组件职责：使用 Vue 文本插值渲染受限 Markdown 行内 token，拒绝原始 HTML。 -->
<script setup lang="ts">
import type { PrivacyInlineToken } from '../../utils/privacyMarkdown'

defineProps<{ tokens: PrivacyInlineToken[] }>()
</script>

<template>
  <template v-for="(token, index) in tokens" :key="`${index}-${token.kind}`">
    <strong v-if="token.kind === 'strong'">{{ token.text }}</strong>
    <em v-else-if="token.kind === 'emphasis'">{{ token.text }}</em>
    <code v-else-if="token.kind === 'code'">{{ token.text }}</code>
    <a
      v-else-if="token.kind === 'link' && token.href"
      :href="token.href"
      rel="nofollow noopener noreferrer"
      >{{ token.text }}</a
    >
    <template v-else>{{ token.text }}</template>
  </template>
</template>
