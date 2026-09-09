<!-- 组件职责：编辑 GEO 声明，并只读展示后端根据真实正文构造的事实来源。 -->
<script setup lang="ts">
export interface GeoDraft {
  direct_answer: string
  target_questions_json: string[]
  key_facts_json: string[]
  evidence_json: string[]
  related_questions_json: string[]
  reviewer_id: string
  last_reviewed_at: string
}

interface ReviewerOption {
  id: string
  label: string
}

const props = defineProps<{
  modelValue: GeoDraft
  serverVisibleSourceText: string
  reviewers: ReviewerOption[]
}>()
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
      >内容复核人
      <select
        :value="modelValue.reviewer_id"
        @change="updateText('reviewer_id', ($event.target as HTMLSelectElement).value)"
      >
        <option value="">尚未指定</option>
        <option v-for="reviewer in reviewers" :key="reviewer.id" :value="reviewer.id">
          {{ reviewer.label }}
        </option>
      </select></label
    >
    <label
      >Last reviewed
      <input
        type="datetime-local"
        :value="modelValue.last_reviewed_at"
        @input="updateText('last_reviewed_at', ($event.target as HTMLInputElement).value)"
    /></label>
    <label
      >Server-visible source content
      <textarea :value="serverVisibleSourceText" readonly />
    </label>
    <p>该预览由后端真实 Product / Case / Knowledge / Expert 内容构造，不能在此编辑。</p>
    <button type="button" @click="$emit('save')">Validate and save GEO</button>
  </fieldset>
</template>
