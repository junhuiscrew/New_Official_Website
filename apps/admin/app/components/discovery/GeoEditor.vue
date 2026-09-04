<!-- 组件职责：编辑 GEO 直接答案、关键事实、证据及其可见正文校验输入。 -->
<script setup lang="ts">
export interface GeoDraft {
  direct_answer: string
  target_questions_json: string[]
  key_facts_json: string[]
  evidence_json: string[]
  related_questions_json: string[]
  reviewer_id: string
  last_reviewed_at: string
  visible_source_text: string
}

const props = defineProps<{ modelValue: GeoDraft }>()
const emit = defineEmits<{ 'update:modelValue': [value: GeoDraft]; save: [] }>()

function updateText(field: keyof GeoDraft, value: string) {
  emit('update:modelValue', { ...props.modelValue, [field]: value })
}

function updateLines(
  field: 'target_questions_json' | 'key_facts_json' | 'evidence_json' | 'related_questions_json',
  value: string,
) {
  emit('update:modelValue', {
    ...props.modelValue,
    [field]: value
      .split('\n')
      .map((item) => item.trim())
      .filter(Boolean),
  })
}
</script>

<template>
  <fieldset class="sub-editor">
    <legend>GEO</legend>
    <label
      >Direct answer
      <textarea
        :value="modelValue.direct_answer"
        @input="updateText('direct_answer', ($event.target as HTMLTextAreaElement).value)"
      />
    </label>
    <label
      >Target questions (one per line)
      <textarea
        :value="modelValue.target_questions_json.join('\n')"
        @input="updateLines('target_questions_json', ($event.target as HTMLTextAreaElement).value)"
      />
    </label>
    <label
      >Key facts (one per line)
      <textarea
        :value="modelValue.key_facts_json.join('\n')"
        @input="updateLines('key_facts_json', ($event.target as HTMLTextAreaElement).value)"
      />
    </label>
    <label
      >Evidence (one per line)
      <textarea
        :value="modelValue.evidence_json.join('\n')"
        @input="updateLines('evidence_json', ($event.target as HTMLTextAreaElement).value)"
      />
    </label>
    <label
      >Related questions (one per line)
      <textarea
        :value="modelValue.related_questions_json.join('\n')"
        @input="updateLines('related_questions_json', ($event.target as HTMLTextAreaElement).value)"
      />
    </label>
    <label
      >Reviewer ID
      <input
        :value="modelValue.reviewer_id"
        @input="updateText('reviewer_id', ($event.target as HTMLInputElement).value)"
    /></label>
    <label
      >Last reviewed
      <input
        type="datetime-local"
        :value="modelValue.last_reviewed_at"
        @input="updateText('last_reviewed_at', ($event.target as HTMLInputElement).value)"
    /></label>
    <label
      >Visible source content
      <textarea
        :value="modelValue.visible_source_text"
        required
        @input="updateText('visible_source_text', ($event.target as HTMLTextAreaElement).value)"
      />
    </label>
    <p>Direct answer、key facts 与 evidence 必须逐项出现在上方可见正文中。</p>
    <button type="button" @click="$emit('save')">Validate and save GEO</button>
  </fieldset>
</template>
