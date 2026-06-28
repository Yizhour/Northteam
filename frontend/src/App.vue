<template>
  <div>
    <header class="topbar">
      <RouterLink class="brand" to="/">
        <span class="brand-mark">NT</span>
        <span class="brand-text">NorthTeam2 工作台</span>
      </RouterLink>

      <nav class="main-nav" aria-label="主导航">
        <RouterLink
          v-for="item in session.features"
          :key="item.key"
          class="nav-link"
          :to="item.path"
        >
          {{ item.name }}
        </RouterLink>
      </nav>

      <div class="user-actions">
        <template v-if="session.authenticated">
          <span class="user-name">{{ session.username }}</span>
          <a v-if="session.can_manage_permissions" class="admin-link" href="/admin/access-control/">权限控制台</a>
          <a v-if="session.is_staff" class="admin-link" href="/admin/">Admin</a>
          <button class="logout-button" type="button" @click="handleLogout">
            <LogOut :size="15" />
            退出
          </button>
        </template>
        <RouterLink v-else class="admin-link" to="/login">
          <LogIn :size="15" />
          登录
        </RouterLink>
      </div>
    </header>

    <main class="page-shell">
      <RouterView
        :session="session"
        :refresh-session="loadSession"
        @auth-required="goLogin"
      />
    </main>
  </div>
</template>

<script setup>
import { onMounted, provide, reactive } from 'vue';
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router';
import { LogIn, LogOut } from '@lucide/vue';

import { api, logout } from './api';

const router = useRouter();
const route = useRoute();
const session = reactive({
  authenticated: false,
  username: '',
  role: 'anonymous',
  role_label: '只读用户（未登录）',
  is_staff: false,
  can_manage_permissions: false,
  features: [],
});

async function loadSession() {
  const data = await api('/api/session/');
  Object.assign(session, data);
}

async function handleLogout() {
  await logout();
  await loadSession();
  router.push('/');
}

function goLogin() {
  router.push({ path: '/login', query: { next: route.fullPath } });
}

provide('session', session);
provide('refreshSession', loadSession);

onMounted(loadSession);
</script>
