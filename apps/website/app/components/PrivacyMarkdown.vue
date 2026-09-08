<!-- 组件职责：把受限 Markdown 块节点渲染为安全的 Vue 结构。 -->
<script setup lang="ts">
import { computed } from 'vue'

import PrivacyInline from '~/components/PrivacyInline.vue'
import { parsePrivacyMarkdown } from '~/utils/privacyMarkdown'

const props = defineProps<{ markdown: string }>()
const blocks = computed(() => parsePrivacyMarkdown(props.markdown))
</script>

<template>
  <div class="privacy-markdown">
    <template v-for="(block, index) in blocks" :key="index">
      <component
        :is="`h${block.level}`"
        v-if="block.type === 'heading'"
        class="privacy-markdown__heading"
        ><PrivacyInline :nodes="block.children"
      /></component>
      <p v-else-if="block.type === 'paragraph'"><PrivacyInline :nodes="block.children" /></p>
      <ol v-else-if="block.type === 'list' && block.ordered">
        <li v-for="(item, itemIndex) in block.items" :key="itemIndex">
          <PrivacyInline :nodes="item" />
        </li>
      </ol>
      <ul v-else-if="block.type === 'list'">
        <li v-for="(item, itemIndex) in block.items" :key="itemIndex">
          <PrivacyInline :nodes="item" />
        </li>
      </ul>
      <blockquote v-else-if="block.type === 'blockquote'">
        <p><PrivacyInline :nodes="block.children" /></p>
      </blockquote>
      <pre v-else><code>{{ block.value }}</code></pre>
    </template>
  </div>
</template>
