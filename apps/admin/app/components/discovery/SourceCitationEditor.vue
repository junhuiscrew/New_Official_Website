<!-- 组件职责：创建真实、可核验且绑定 Knowledge/GEO 的来源引用。 -->
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
const emit = defineEmits<{ 'update:modelValue': [value: SourceDraft]; save: [] }>()

function update(field: keyof SourceDraft, value: string) {
  emit('update:modelValue', { ...props.modelValue, [field]: value })
}
</script>

<template>
  <fieldset class="sub-editor">
    <legend>Source citation</legend>
    <label
      >Title
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
      >Publisher
      <input
        :value="modelValue.publisher"
        @input="update('publisher', ($event.target as HTMLInputElement).value)"
    /></label>
    <label
      >Source type
      <select
        :value="modelValue.source_type"
        @change="update('source_type', ($event.target as HTMLSelectElement).value)"
      >
        <option>official</option>
        <option>standard</option>
        <option>technical-paper</option>
        <option>manufacturer</option>
        <option>internal-first-party</option>
        <option>case-evidence</option>
        <option>other</option>
      </select>
    </label>
    <button type="button" @click="$emit('save')">Add verified source</button>
  </fieldset>
</template>
