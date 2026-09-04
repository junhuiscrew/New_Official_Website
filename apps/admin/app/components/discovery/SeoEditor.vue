<!-- 组件职责：编辑跨内容类型复用的 SEO meta、robots 与 canonical override。 -->
<script setup lang="ts">
export interface SeoDraft {
  seo_title: string
  meta_description: string
  canonical_override: string
  robots_index: boolean
  robots_follow: boolean
  og_title: string
  og_description: string
}

const props = defineProps<{ modelValue: SeoDraft }>()
const emit = defineEmits<{ 'update:modelValue': [value: SeoDraft]; save: [] }>()

function update(field: keyof SeoDraft, value: string | boolean) {
  emit('update:modelValue', { ...props.modelValue, [field]: value })
}
</script>

<template>
  <fieldset class="sub-editor">
    <legend>SEO</legend>
    <label
      >SEO title
      <input
        :value="modelValue.seo_title"
        @input="update('seo_title', ($event.target as HTMLInputElement).value)"
    /></label>
    <label
      >Meta description
      <textarea
        :value="modelValue.meta_description"
        @input="update('meta_description', ($event.target as HTMLTextAreaElement).value)"
      />
    </label>
    <label
      >Canonical override
      <input
        :value="modelValue.canonical_override"
        placeholder="默认使用 ContentRoute"
        @input="update('canonical_override', ($event.target as HTMLInputElement).value)"
    /></label>
    <label
      ><input
        type="checkbox"
        :checked="modelValue.robots_index"
        @change="update('robots_index', ($event.target as HTMLInputElement).checked)"
      />
      Index</label
    >
    <label
      ><input
        type="checkbox"
        :checked="modelValue.robots_follow"
        @change="update('robots_follow', ($event.target as HTMLInputElement).checked)"
      />
      Follow</label
    >
    <label
      >OG title
      <input
        :value="modelValue.og_title"
        @input="update('og_title', ($event.target as HTMLInputElement).value)"
    /></label>
    <label
      >OG description
      <textarea
        :value="modelValue.og_description"
        @input="update('og_description', ($event.target as HTMLTextAreaElement).value)"
      />
    </label>
    <button type="button" @click="$emit('save')">Save SEO</button>
  </fieldset>
</template>
