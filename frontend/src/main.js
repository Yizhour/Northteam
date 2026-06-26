import { createApp } from 'vue';
import { createRouter, createWebHistory } from 'vue-router';

import App from './App.vue';
import HomeView from './views/HomeView.vue';
import LoginView from './views/LoginView.vue';
import PlaceholderView from './views/PlaceholderView.vue';
import ToolsView from './views/ToolsView.vue';
import './styles.css';

const routes = [
  { path: '/', component: HomeView, meta: { feature: 'overview' } },
  { path: '/login', component: LoginView },
  { path: '/projects', component: PlaceholderView, props: { featureKey: 'projects' } },
  { path: '/tools', component: ToolsView, meta: { feature: 'tools' } },
  { path: '/info', component: PlaceholderView, props: { featureKey: 'info' } },
  { path: '/files', component: PlaceholderView, props: { featureKey: 'files' } },
  { path: '/mistakes', component: PlaceholderView, props: { featureKey: 'mistakes' } },
  { path: '/interns', component: PlaceholderView, props: { featureKey: 'interns' } },
  { path: '/:pathMatch(.*)*', redirect: '/' },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

createApp(App).use(router).mount('#app');
