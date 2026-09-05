<!-- 页面用途：维护唯一 Company Profile 及其真实多语言公开资料。 -->
<script setup lang="ts">
useHead({ title: 'Company Profile', meta: [{ name: 'robots', content: 'noindex, nofollow' }] })
const api = useAuthorityApi()
const payloadJson = ref('{\n  "status": "enabled",\n  "translations": []\n}')
const message = ref('')
const profileId = ref<string | null>(null)
const translationStatuses = ref<Array<{ locale_id: string; status: string }>>([])
const publications = ref<Array<{ locale_id: string; status: string }>>([])

async function load() {
  const value = await api.detail<{
    profile: Record<string, unknown> | null
    translations: Array<Record<string, unknown>>
    translation_statuses: Array<{ locale_id: string; status: string }>
    publications: Array<{ locale_id: string; status: string }>
  }>('/trust/company-profile')
  profileId.value = value.profile?.id ? String(value.profile.id) : null
  translationStatuses.value = value.translation_statuses || []
  publications.value = value.publications || []
  const profile = Object.fromEntries(
    Object.entries(value.profile || {}).filter(
      ([key]) => !['id', 'created_at', 'updated_at'].includes(key),
    ),
  )
  const translations = value.translations.map((translation) => ({
    locale_id: translation.locale_id,
    fields: Object.fromEntries(
      Object.entries(translation).filter(
        ([key]) =>
          !['id', 'company_profile_id', 'locale_id', 'created_at', 'updated_at'].includes(key),
      ),
    ),
  }))
  payloadJson.value = JSON.stringify({ ...profile, translations }, null, 2)
}

async function save() {
  await api.replace(
    '/trust/company-profile',
    JSON.parse(payloadJson.value) as Record<string, unknown>,
  )
  message.value = 'Saved'
  await load()
}

function publicationStatus(localeId: string) {
  return (
    publications.value.find((publication) => publication.locale_id === localeId)?.status || 'draft'
  )
}

// Company Profile 复用后端统一 TranslationStatus / Publication 事务，不在前端伪造状态。
async function review(localeId: string) {
  if (!profileId.value) return
  await api.archive(`/trust/company-profile/${profileId.value}/translations/${localeId}/review`)
  await load()
}

async function transition(localeId: string, status: 'published' | 'archived') {
  if (!profileId.value) return
  await api.archive(`/trust/company-profile/${profileId.value}/publications/${localeId}/${status}`)
  await load()
}

onMounted(load)
</script>
<template>
  <main class="admin-shell">
    <h1>Company Profile</h1>
    <p>Only publish facts verified by Junhui.</p>
    <textarea v-model="payloadJson" rows="24" /><button type="button" @click="save">Save</button>
    <p role="status">{{ message }}</p>
    <section v-if="translationStatuses.length">
      <h2>Publication lifecycle</h2>
      <div v-for="translationStatus in translationStatuses" :key="translationStatus.locale_id">
        <span>
          {{ translationStatus.locale_id }} · translation {{ translationStatus.status }} ·
          publication
          {{ publicationStatus(translationStatus.locale_id) }}
        </span>
        <button
          v-if="publicationStatus(translationStatus.locale_id) !== 'published'"
          type="button"
          @click="review(translationStatus.locale_id)"
        >
          Review
        </button>
        <button
          v-if="publicationStatus(translationStatus.locale_id) === 'review'"
          type="button"
          @click="transition(translationStatus.locale_id, 'published')"
        >
          Publish
        </button>
        <button
          v-if="publicationStatus(translationStatus.locale_id) === 'published'"
          type="button"
          @click="transition(translationStatus.locale_id, 'archived')"
        >
          Archive publication
        </button>
      </div>
    </section>
  </main>
</template>
