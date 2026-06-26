<template>
  <section class="login-panel">
    <div class="login-heading">
      <span class="brand-mark">NT</span>
      <div>
        <h1>NorthTeam 工作台</h1>
        <p>请使用内部账号登录。</p>
      </div>
    </div>

    <div v-if="errorMessage" class="form-error">{{ errorMessage }}</div>

    <form @submit.prevent="submit">
      <label>用户名 <input v-model="username" autocomplete="username" required /></label>
      <label>密码 <input v-model="password" type="password" autocomplete="current-password" required /></label>
      <button class="login-button" type="submit" :disabled="loading">
        <LogIn :size="16" />
        {{ loading ? '登录中...' : '登录' }}
      </button>
    </form>
  </section>
</template>

<script setup>
import { inject, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { LogIn } from '@lucide/vue';
import { login } from '../api';

const refreshSession = inject('refreshSession');
const router = useRouter();
const route = useRoute();
const username = ref('');
const password = ref('');
const errorMessage = ref('');
const loading = ref(false);

async function submit() {
  loading.value = true;
  errorMessage.value = '';
  try {
    await login(username.value, password.value);
    await refreshSession();
    router.push(route.query.next || '/');
  } catch (error) {
    errorMessage.value = error.message || '登录失败，请重试。';
  } finally {
    loading.value = false;
  }
}
</script>
