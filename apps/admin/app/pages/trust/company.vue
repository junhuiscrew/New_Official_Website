<!-- 页面用途：维护唯一 Company Profile 及其真实多语言公开资料。 -->
<script setup lang="ts">
useHead({ title: 'Company Profile', meta: [{ name: 'robots', content: 'noindex, nofollow' }] })
const api = useAuthorityApi()
const payloadJson = ref('{\n  "status": "enabled",\n  "translations": []\n}')
const message = ref('')
onMounted(async () => {
  const value = await api.detail<{
    profile: Record<string, unknown> | null
    translations: Array<Record<string, unknown>>
  }>('/trust/company-profile')
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
})
async function save() {
  await api.replace(
    '/trust/company-profile',
    JSON.parse(payloadJson.value) as Record<string, unknown>,
  )
  message.value = 'Saved'
}
</script>
<template>
  <main class="admin-shell">
    <h1>Company Profile</h1>
    <p>Only publish facts verified by Junhui.</p>
    <textarea v-model="payloadJson" rows="24" /><button type="button" @click="save">Save</button>
    <p role="status">{{ message }}</p>
  </main>
</template>
