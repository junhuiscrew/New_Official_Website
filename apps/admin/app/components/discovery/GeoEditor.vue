<!-- 组件职责：使用中文操作界面编辑 GEO 声明，并只读展示后端构造的事实来源。 -->
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
const emit = defineEmits<{
  'update:modelValue': [value: GeoDraft]
  save: []
}>()

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
      >直接回答
      <textarea
        :value="modelValue.direct_answer"
        @input="updateText('direct_answer', ($event.target as HTMLTextAreaElement).value)"
      />
    </label>
    <label
      >目标问题（每行一项）
      <textarea
        :value="modelValue.target_questions_json.join('\n')"
        @input="updateLines('target_questions_json', ($event.target as HTMLTextAreaElement).value)"
      />
    </label>
    <label
      >关键事实（每行一项）
      <textarea
        :value="modelValue.key_facts_json.join('\n')"
        @input="updateLines('key_facts_json', ($event.target as HTMLTextAreaElement).value)"
      />
    </label>
    <label
      >依据（每行一项）
      <textarea
        :value="modelValue.evidence_json.join('\n')"
        @input="updateLines('evidence_json', ($event.target as HTMLTextAreaElement).value)"
      />
    </label>
    <label
      >相关问题（每行一项）
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
      >最近复核时间
      <input
        type="datetime-local"
        :value="modelValue.last_reviewed_at"
        @input="updateText('last_reviewed_at', ($event.target as HTMLInputElement).value)"
    /></label>
    <label
      >服务端可见事实来源
      <textarea :value="serverVisibleSourceText" readonly />
    </label>
    <p>该预览由后端真实 Product / Case / Knowledge / Expert 内容构造，不能在此编辑。</p>
    <button type="button" @click="$emit('save')">校验并保存 GEO</button>
  </fieldset>
</template>
