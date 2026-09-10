<!-- 组件职责：使用中文操作界面创建真实、可核验且绑定 Knowledge/GEO 的来源引用。 -->
<script setup lang="ts">
export interface SourceDraft {
  title: string
  url: string
  publisher: string
  source_type: string
  article_id?: string
  geo_document_id?: string
}

const props = defineProps<{ modelValue: SourceDraft }>()
const emit = defineEmits<{
  'update:modelValue': [value: SourceDraft]
  save: []
}>()

function update(field: keyof SourceDraft, value: string) {
  emit('update:modelValue', { ...props.modelValue, [field]: value })
}
</script>

<template>
  <fieldset class="sub-editor">
    <legend>来源引用</legend>
    <label
      >来源标题
      <input
        :value="modelValue.title"
        required
        @input="update('title', ($event.target as HTMLInputElement).value)"
    /></label>
    <label
      >URL
      <input
        :value="modelValue.url"
        type="url"
        required
        @input="update('url', ($event.target as HTMLInputElement).value)"
    /></label>
    <label
      >发布机构
      <input
        :value="modelValue.publisher"
        @input="update('publisher', ($event.target as HTMLInputElement).value)"
    /></label>
    <label
      >来源类型
      <select
        :value="modelValue.source_type"
        @change="update('source_type', ($event.target as HTMLSelectElement).value)"
      >
        <option value="official">官方网站</option>
        <option value="standard">标准</option>
        <option value="technical-paper">技术论文</option>
        <option value="manufacturer">制造商资料</option>
        <option value="internal-first-party">内部一手资料</option>
        <option value="case-evidence">案例依据</option>
        <option value="other">其他</option>
      </select>
    </label>
    <button type="button" @click="$emit('save')">添加已核验来源</button>
  </fieldset>
</template>
