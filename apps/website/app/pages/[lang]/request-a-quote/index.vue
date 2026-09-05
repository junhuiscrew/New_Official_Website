<!-- 页面用途：匿名 RFQ 多项目公开表单；不提交 Admin Cookie CSRF。 -->
<script setup lang="ts">
const api = useApi()
const route = useRoute()
const lang = String(route.params.lang)
const form = reactive({
  company_name: '',
  contact_name: '',
  email: '',
  phone: '',
  whatsapp: '',
  country_code: '',
  website: '',
  message: '',
  items: [
    {
      item_type: 'custom',
      product_name_text: '',
      quantity: '',
      material_text: '',
      screw_diameter: '',
      length: '',
      machine_brand: '',
      machine_model: '',
      requirements: '',
    },
  ],
  consent_privacy: false,
  consent_marketing: false,
  honeypot: '',
  preferred_language: lang,
})
const result = ref('')
const files = ref<File[]>([])
const errorMessage = ref('')
function addItem() {
  form.items.push({
    item_type: 'custom',
    product_name_text: '',
    quantity: '',
    material_text: '',
    screw_diameter: '',
    length: '',
    machine_brand: '',
    machine_model: '',
    requirements: '',
  })
}
function removeItem(index: number) {
  if (form.items.length > 1) form.items.splice(index, 1)
}
async function submit() {
  try {
    const response = await api<{
      data: { reference: string; status: string; submission_token: string }
    }>('/public/rfqs', {
      method: 'POST',
      body: form,
    })
    result.value = response.data.reference
    // 短期提交令牌只允许为刚创建的 RFQ 写入 private-rfq。
    for (const attachment of files.value) {
      const body = new FormData()
      body.append('file', attachment)
      body.append('file_category', 'other')
      await api(`/public/rfqs/${response.data.reference}/files`, {
        method: 'POST',
        body,
        headers: { 'X-RFQ-Submission-Token': response.data.submission_token },
      })
    }
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
      ><label>Phone <input v-model="form.phone" type="tel" autocomplete="tel" /></label
      ><label>WhatsApp <input v-model="form.whatsapp" type="tel" /></label
      ><label>Country <input v-model="form.country_code" maxlength="2" placeholder="CN" /></label
      ><label>Website <input v-model="form.website" type="url" placeholder="https://" /></label
      ><label>Message <textarea v-model="form.message" /></label>
      <fieldset>
        <legend>Items</legend>
        <div v-for="(item, index) in form.items" :key="index">
          <label
            >Item type
            <select v-model="item.item_type">
              <option value="product">Product</option>
              <option value="screw">Screw</option>
              <option value="barrel">Barrel</option>
              <option value="component">Component</option>
              <option value="custom">Custom</option>
              <option value="other">Other</option>
            </select></label
          >
          <label>Product <input v-model="item.product_name_text" /></label>
          <label>Quantity <input v-model="item.quantity" /></label>
          <label>Material <input v-model="item.material_text" /></label>
          <label>Screw diameter <input v-model="item.screw_diameter" /></label>
          <label>Length <input v-model="item.length" /></label>
          <label>Machine brand <input v-model="item.machine_brand" /></label>
          <label>Machine model <input v-model="item.machine_model" /></label>
          <label>Requirements <textarea v-model="item.requirements" /></label>
          <button type="button" @click="removeItem(index)">Remove item</button>
        </div>
        <button type="button" @click="addItem">Add item</button>
      </fieldset>
      <label
        >Drawings and specifications
        <input
          type="file"
          multiple
          accept=".jpg,.jpeg,.png,.webp,.pdf,.dwg,.dxf,.step,.stp,.iges,.igs"
          @change="files = Array.from(($event.target as HTMLInputElement).files || [])"
      /></label>
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
