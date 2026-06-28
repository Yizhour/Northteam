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

  <section v-if="data.bond_reminder.available" class="bond-reminder-panel">
    <div class="bond-reminder-header">
      <div>
        <p class="eyebrow">BondReminder</p>
        <h2>付息兑付提醒</h2>
      </div>
      <div class="bond-reminder-stats">
        <span>今日 {{ data.bond_reminder.today_count }} 项</span>
        <span>本周 {{ data.bond_reminder.weekly_count }} 项</span>
      </div>
    </div>

    <div v-if="!data.bond_reminder.configured" class="bond-empty-state">
      尚未完成债券数据或监控日期列配置。
    </div>
    <template v-else>
      <div class="bond-sections">
        <div class="bond-section">
          <div class="bond-section-title">
            <h3>今日事件</h3>
            <span>{{ data.bond_reminder.today }}</span>
          </div>
          <div v-if="data.bond_reminder.today_events.length" class="bond-event-list compact">
            <article v-for="(event, index) in data.bond_reminder.today_events" :key="`today-${event.event_type}-${event.date_str}-${index}`" class="bond-event-card">
              <span class="bond-tag" :style="{ backgroundColor: event.color }">{{ event.event_type }}</span>
              <strong>{{ primaryText(event) }}</strong>
              <p>{{ secondaryText(event) }}</p>
            </article>
          </div>
          <div v-else class="bond-empty-state small">今日暂无付息兑付事项。</div>
        </div>

        <div class="bond-section">
          <div class="bond-section-title">
            <h3>本周事件</h3>
            <span>{{ data.bond_reminder.week_range.label }}</span>
          </div>
          <div v-if="data.bond_reminder.weekly_events.length" class="bond-table-wrap">
            <table class="bond-table">
              <thead>
                <tr>
                  <th>事件类型</th>
                  <th>日期</th>
                  <th>星期</th>
                  <th v-for="column in data.bond_reminder.display_columns" :key="column">{{ column }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(event, index) in data.bond_reminder.weekly_events" :key="`week-${event.event_type}-${event.date_str}-${index}`">
                  <td><span class="bond-tag" :style="{ backgroundColor: event.color }">{{ event.event_type }}</span></td>
                  <td class="bond-date">{{ event.date_str }}</td>
                  <td>{{ event.weekday }}</td>
                  <td v-for="column in data.bond_reminder.display_columns" :key="column">{{ event.display_data[column] }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div v-else class="bond-empty-state small">本周暂无付息兑付事项。</div>
        </div>
      </div>
    </template>
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
  bond_reminder: {
    available: false,
    configured: false,
    week_range: { label: '' },
    today: '',
    display_columns: [],
    weekly_events: [],
    today_events: [],
    weekly_count: 0,
    today_count: 0,
  },
});

function primaryText(event) {
  const values = Object.values(event.display_data || {}).filter(Boolean);
  return values[1] || values[0] || event.event_type;
}

function secondaryText(event) {
  const primary = primaryText(event);
  const values = Object.values(event.display_data || {}).filter((value) => value && value !== primary);
  return values.slice(0, 3).join(' · ') || `${event.date_str} ${event.weekday}`;
}

onMounted(async () => {
  try {
    Object.assign(data, await api('/api/overview/'));
  } catch (error) {
    if (error.status === 401 || error.status === 403) emit('auth-required');
  }
});
</script>
