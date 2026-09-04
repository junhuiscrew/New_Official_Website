<!-- 页面用途：匿名 RFQ 多项目公开表单；不提交 Admin Cookie CSRF。 -->
<script setup lang="ts">
const api = useApi()
const route = useRoute()
const lang = String(route.params.lang)
const form = reactive({
  company_name: '',
  contact_name: '',
  email: '',
  message: '',
  items: [{ item_type: 'custom', requirements: '' }],
  consent_privacy: false,
  consent_marketing: false,
  honeypot: '',
  preferred_language: lang,
})
const result = ref('')
const errorMessage = ref('')
async function submit() {
  try {
    const response = await api<{ data: { reference: string; status: string } }>('/public/rfqs', {
      method: 'POST',
      body: form,
    })
    result.value = response.data.reference
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Unable to submit RFQ.'
  }
}
</script>
<template>
  <main class="public-content-page">
    <h1>Request a Quote</h1>
    <form @submit.prevent="submit">
      <label>Company <input v-model="form.company_name" required /></label
      ><label>Contact <input v-model="form.contact_name" required /></label
      ><label>Email <input v-model="form.email" type="email" required /></label
      ><label>Message <textarea v-model="form.message" /></label>
      <fieldset>
        <legend>Items</legend>
        <div v-for="(item, index) in form.items" :key="index">
          <label>Requirements <textarea v-model="item.requirements" /></label>
        </div>
        <button type="button" @click="form.items.push({ item_type: 'custom', requirements: '' })">
          Add item
        </button>
      </fieldset>
      <label
        ><input v-model="form.consent_privacy" type="checkbox" required /> I agree to the Privacy
        Policy</label
      ><label><input v-model="form.consent_marketing" type="checkbox" /> Marketing updates</label
      ><input v-model="form.honeypot" class="honeypot" tabindex="-1" autocomplete="off" /><button
        type="submit"
      >
        Submit inquiry
      </button>
      <p v-if="result" role="status">{{ result }} · received</p>
      <p v-if="errorMessage" role="alert">{{ errorMessage }}</p>
    </form>
  </main>
</template>
