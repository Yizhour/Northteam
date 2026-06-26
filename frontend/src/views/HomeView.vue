<template>
  <section class="page-heading">
    <p class="eyebrow">NorthTeam2</p>
    <h1>团队内部管理概况</h1>
    <p class="heading-text">面向团队日常协作、项目台账、资料归档和人员登记的内部工作台。</p>
  </section>

  <section class="summary-grid" aria-label="关键指标">
    <article v-for="card in data.summary_cards" :key="card.label" class="metric-card">
      <p>{{ card.label }}</p>
      <strong>{{ card.value }}</strong>
      <span>{{ card.hint }}</span>
    </article>
  </section>

  <section class="content-grid">
    <div class="panel">
      <div class="panel-heading">
        <h2>快捷入口</h2>
        <span>Quick Access</span>
      </div>
      <div class="quick-grid">
        <div v-for="link in data.quick_links" :key="link.label" class="quick-item">
          <strong>{{ link.label }}</strong>
          <span>{{ link.description }}</span>
        </div>
      </div>
    </div>

    <div class="panel">
      <div class="panel-heading">
        <h2>今日待办</h2>
        <span>To-do</span>
      </div>
      <ul class="clean-list">
        <li v-for="todo in data.todos" :key="todo">{{ todo }}</li>
      </ul>
    </div>

    <div class="panel wide-panel">
      <div class="panel-heading">
        <h2>系统公告</h2>
        <span>Notice</span>
      </div>
      <ul class="notice-list">
        <li v-for="announcement in data.announcements" :key="announcement">{{ announcement }}</li>
      </ul>
    </div>
  </section>
</template>

<script setup>
import { onMounted, reactive } from 'vue';
import { api } from '../api';

const emit = defineEmits(['auth-required']);
const data = reactive({
  summary_cards: [],
  quick_links: [],
  todos: [],
  announcements: [],
});

onMounted(async () => {
  try {
    Object.assign(data, await api('/api/overview/'));
  } catch (error) {
    if (error.status === 401 || error.status === 403) emit('auth-required');
  }
});
</script>
