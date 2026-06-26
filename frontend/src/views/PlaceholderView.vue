<template>
  <section class="page-heading compact-heading">
    <p class="eyebrow">Module Placeholder</p>
    <h1>{{ page.title }}</h1>
    <p class="heading-text">{{ page.message }}</p>
  </section>

  <section class="placeholder-panel">
    <div>
      <span class="status-dot"></span>
      <strong>{{ page.title }} 功能预留</strong>
    </div>
    <p>后续可在此扩展列表、表单、权限和数据模型。</p>
  </section>
</template>

<script setup>
import { onMounted, reactive, watch } from 'vue';
import { api } from '../api';

const props = defineProps({
  featureKey: { type: String, required: true },
});
const emit = defineEmits(['auth-required']);
const page = reactive({ title: '', message: '' });

async function loadPage() {
  try {
    Object.assign(page, await api(`/api/pages/${props.featureKey}/`));
  } catch (error) {
    if (error.status === 401 || error.status === 403) emit('auth-required');
  }
}

onMounted(loadPage);
watch(() => props.featureKey, loadPage);
</script>
