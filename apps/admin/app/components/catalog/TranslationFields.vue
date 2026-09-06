<!-- 组件职责：提供 zh-CN / en 翻译标签页及名称、正文输入，并保持父表单双向同步。 -->
<script setup lang="ts">
import type { CatalogTranslationDraft } from '~/composables/useCatalogApi'

interface LocaleOption {
  id: string
  code: string
  native_name: string
}
interface ExtraFieldOption {
  key: string
  label: string
  rows?: number
}

const props = withDefaults(
  defineProps<{
    locales: LocaleOption[]
    modelValue: CatalogTranslationDraft[]
    bodyField?: string
    extraFields?: ExtraFieldOption[]
  }>(),
  { bodyField: 'description', extraFields: () => [] },
)
const emit = defineEmits<{
  'update:modelValue': [value: CatalogTranslationDraft[]]
}>()
const activeCode = ref('zh-CN')

const supportedLocales = computed(() =>
  props.locales.filter((locale) => ['zh-CN', 'en'].includes(locale.code)),
)

function translationFor(locale: LocaleOption): CatalogTranslationDraft {
  return (
    props.modelValue.find((item) => item.locale_id === locale.id) || {
      locale_id: locale.id,
      code: locale.code,
      name: '',
      fields: {},
    }
  )
}

function updateTranslation(locale: LocaleOption, field: 'name' | 'description', value: string) {
  const next = props.modelValue.filter((item) => item.locale_id !== locale.id)
  const current = translationFor(locale)
  const updated =
    field === 'name'
      ? { ...current, name: value }
      : { ...current, fields: { ...current.fields, [props.bodyField]: value } }
  emit('update:modelValue', [...next, updated])
}

// 更新产品等实体附加的结构化翻译字段，同时保留当前语言的其他字段。
function updateExtraField(locale: LocaleOption, field: string, value: string) {
  const next = props.modelValue.filter((item) => item.locale_id !== locale.id)
  const current = translationFor(locale)
  emit('update:modelValue', [
    ...next,
    { ...current, fields: { ...current.fields, [field]: value } },
  ])
}
</script>

<template>
  <fieldset class="translation-fields">
    <legend>Translations</legend>
    <div class="tab-list" role="tablist" aria-label="Translation locale">
      <button
        v-for="locale in supportedLocales"
        :key="locale.id"
        type="button"
        :class="{ active: activeCode === locale.code }"
        @click="activeCode = locale.code"
      >
        {{ locale.code }} · {{ locale.native_name }}
      </button>
    </div>
    <div v-for="locale in supportedLocales" v-show="activeCode === locale.code" :key="locale.id">
      <label>
        Name
        <input
          :value="translationFor(locale).name"
          @input="updateTranslation(locale, 'name', ($event.target as HTMLInputElement).value)"
        />
      </label>
      <label>
        Description
        <textarea
          :value="translationFor(locale).fields[props.bodyField] || ''"
          @input="
            updateTranslation(locale, 'description', ($event.target as HTMLTextAreaElement).value)
          "
        />
      </label>
      <label v-for="field in extraFields" :key="field.key">
        {{ field.label }}
        <textarea
          :rows="field.rows || 3"
          :value="translationFor(locale).fields[field.key] || ''"
          @input="updateExtraField(locale, field.key, ($event.target as HTMLTextAreaElement).value)"
        />
      </label>
    </div>
  </fieldset>
</template>
