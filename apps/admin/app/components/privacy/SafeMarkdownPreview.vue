<!-- 组件职责：把不可信 Privacy Markdown 按受限块结构渲染，不插入任何 HTML。 -->
<script setup lang="ts">
import { parsePrivacyMarkdown } from '../../utils/privacyMarkdown'

const props = defineProps<{ markdown: string }>()
const blocks = computed(() => parsePrivacyMarkdown(props.markdown))
</script>

<template>
  <article class="privacy-markdown-preview">
    <template v-for="(block, blockIndex) in blocks" :key="blockIndex">
      <h2 v-if="block.kind === 'heading' && block.level === 2">
        <SafeMarkdownInline :tokens="block.tokens" />
      </h2>
      <h3 v-else-if="block.kind === 'heading' && block.level === 3">
        <SafeMarkdownInline :tokens="block.tokens" />
      </h3>
      <p v-else-if="block.kind === 'paragraph'">
        <SafeMarkdownInline :tokens="block.tokens" />
      </p>
      <blockquote v-else-if="block.kind === 'blockquote'">
        <SafeMarkdownInline :tokens="block.tokens" />
      </blockquote>
      <ul v-else-if="block.kind === 'unordered-list'">
        <li v-for="(tokens, itemIndex) in block.items" :key="itemIndex">
          <SafeMarkdownInline :tokens="tokens" />
        </li>
      </ul>
      <ol v-else-if="block.kind === 'ordered-list'">
        <li v-for="(tokens, itemIndex) in block.items" :key="itemIndex">
          <SafeMarkdownInline :tokens="tokens" />
        </li>
      </ol>
      <pre v-else-if="block.kind === 'code'"><code>{{ block.text }}</code></pre>
    </template>
  </article>
</template>
