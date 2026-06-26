<template>
  <section class="page-heading compact-heading">
    <p class="eyebrow">Tools</p>
    <h1>高效工具箱</h1>
    <p class="heading-text">集中放置团队内部常用效率工具。权限由后台控制台统一管理。</p>
  </section>

  <section class="tool-grid" aria-label="工具列表">
    <article v-for="tool in tools" :key="tool.key" class="tool-card">
      <div>
        <h2>{{ tool.title }}</h2>
        <p>{{ tool.description }}</p>
        <span class="tool-permission">{{ tool.can_use ? '可查看和使用' : '仅可查看' }}</span>
      </div>
      <a class="tool-action" :href="tool.path">
        <ExternalLink :size="16" />
        进入工具
      </a>
    </article>
  </section>

  <section v-if="!tools.length" class="placeholder-panel">
    <div>
      <span class="status-dot"></span>
      <strong>暂无可用工具</strong>
    </div>
    <p>当前账号还没有被授予工具箱内具体工具的访问权限。</p>
  </section>
</template>

<script setup>
import { onMounted, ref } from 'vue';
import { ExternalLink } from '@lucide/vue';
import { api } from '../api';

const emit = defineEmits(['auth-required']);
const tools = ref([]);

onMounted(async () => {
  try {
    const data = await api('/api/tools/');
    tools.value = data.tools;
  } catch (error) {
    if (error.status === 401 || error.status === 403) emit('auth-required');
  }
});
</script>
