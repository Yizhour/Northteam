<template>
  <section class="page-heading compact-heading">
    <p class="eyebrow">Interns</p>
    <h1>实习生工作安排</h1>
    <p v-if="!isPublicLink" class="heading-text">查看实习生本周工作安排、请假占用和排班冲突。可点击或拖动时间格快速创建工作安排。</p>
  </section>

  <section class="intern-workspace" :class="{ 'public-schedule': isPublicLink }">
    <aside v-if="!isPublicLink" class="intern-sidebar">
      <div class="intern-sidebar-head">
        <h2>实习生列表</h2>
        <span>{{ interns.length }} 人</span>
      </div>
      <button v-if="listCapabilities.can_manage_interns" class="primary-button full-width" type="button" @click="openInternModal()">
        <Plus :size="16" />
        新增实习生
      </button>
      <button
        v-for="intern in interns"
        :key="intern.id"
        class="intern-list-item"
        :class="{ active: selectedIntern && selectedIntern.id === intern.id }"
        type="button"
        @click="selectIntern(intern)"
      >
        <strong>{{ intern.name }}</strong>
        <span>{{ intern.note || '暂无备注' }}</span>
      </button>
      <p v-if="!interns.length" class="intern-empty">暂无实习生档案。</p>
      <div v-if="selectedIntern && listCapabilities.can_manage_interns" class="intern-side-actions">
        <button class="plain-button" type="button" @click="openInternModal(selectedIntern)">编辑当前</button>
        <button class="plain-button" type="button" @click="copyShareUrl(selectedIntern)">复制专属链接</button>
        <button class="danger-button" type="button" @click="deleteIntern(selectedIntern)">停用</button>
      </div>
    </aside>

    <section class="schedule-panel">
      <div class="schedule-toolbar">
        <div>
          <h2>{{ selectedIntern ? selectedIntern.name : '请选择实习生' }}</h2>
          <span>{{ isPublicLink ? '专属链接' : '内部管理' }} · {{ schedule.week_start }} 至 {{ schedule.week_end }}</span>
        </div>
        <div v-if="!isPublicLink" class="schedule-actions">
          <button class="icon-button" type="button" title="上一周" @click="moveWeek(-7)">
            <ChevronLeft :size="18" />
          </button>
          <button class="plain-button" type="button" @click="goCurrentWeek">本周</button>
          <button class="icon-button" type="button" title="下一周" @click="moveWeek(7)">
            <ChevronRight :size="18" />
          </button>
          <button v-if="schedule.capabilities.can_request_leave" class="plain-button" type="button" @click="openCreate('leave')">
            <CalendarX :size="16" />
            请假
          </button>
          <button v-if="schedule.capabilities.can_create_work" class="primary-button" type="button" @click="openCreate('work')">
            <Plus :size="16" />
            安排工作
          </button>
        </div>
      </div>

      <div v-if="error" class="form-error">{{ error }}</div>

      <div class="schedule-table-wrap">
        <table class="schedule-table">
          <thead>
            <tr>
              <th class="time-column">时间</th>
              <th v-for="day in weekDays" :key="day.date">
                <strong>{{ day.label }}</strong>
                <span>{{ day.date }}</span>
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="hour in hours" :key="hour">
              <th class="time-column">{{ hourLabel(hour) }}</th>
              <td
                v-for="day in weekDays"
                :key="`${day.date}-${hour}`"
                class="schedule-cell"
                :class="{ selecting: isCellSelected(day.date, hour) }"
                @mousedown="startSelection(day.date, hour, $event)"
                @mouseenter="updateSelection(day.date, hour)"
              >
                <button
                  v-for="item in schedulesForCell(day.date, hour)"
                  :key="`${item.id}-${hour}`"
                  class="schedule-block"
                  :class="item.schedule_type"
                  type="button"
                  @click.stop="openDetail(item)"
                >
                  <span>{{ timeRange(item) }}</span>
                  <strong>{{ item.title }}</strong>
                  <small>{{ item.created_by_name }}</small>
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </section>

  <div v-if="modal.open" class="modal-backdrop" @click.self="closeModal">
    <form class="schedule-modal" @submit.prevent="submitSchedule">
      <div class="modal-head">
        <div>
          <p class="eyebrow">{{ form.schedule_type === 'leave' ? 'Leave' : 'Work' }}</p>
          <h2>{{ modalTitle }}</h2>
        </div>
        <button class="icon-button" type="button" title="关闭" @click="closeModal">
          <X :size="18" />
        </button>
      </div>

      <div v-if="modal.error" class="form-error">{{ modal.error }}</div>

      <div class="form-grid">
        <label>
          标题
          <input v-model="form.title" :disabled="modal.readonly" required>
        </label>
        <label>
          日期
          <input v-model="form.date" :disabled="modal.readonly" type="date" required>
        </label>
        <label>
          开始时间
          <input v-model="form.start" :disabled="modal.readonly" type="time" min="09:00" max="18:00" required>
        </label>
        <label>
          结束时间
          <input v-model="form.end" :disabled="modal.readonly" type="time" min="09:00" max="18:00" required>
        </label>
        <label class="wide">
          备注
          <textarea v-model="form.notes" :disabled="modal.readonly" rows="4"></textarea>
        </label>
      </div>

      <div v-if="modal.item" class="schedule-detail-meta">
        <span>安排人：{{ modal.item.created_by_name }}</span>
        <span>类型：{{ modal.item.schedule_type_label }}</span>
      </div>

      <div class="modal-actions">
        <button class="plain-button" type="button" @click="closeModal">关闭</button>
        <button v-if="modal.readonly && modal.item && modal.item.can_edit" class="primary-button" type="button" @click="enableEdit">编辑</button>
        <button v-if="!modal.readonly && modal.item && modal.item.can_delete" class="danger-button" type="button" @click="deleteSchedule">删除</button>
        <button v-if="!modal.readonly" class="primary-button" type="submit">{{ modal.item ? '保存' : '创建' }}</button>
      </div>
    </form>
  </div>

  <div v-if="internModal.open" class="modal-backdrop" @click.self="closeInternModal">
    <form class="schedule-modal" @submit.prevent="submitIntern">
      <div class="modal-head">
        <div>
          <p class="eyebrow">Intern</p>
          <h2>{{ internModal.item ? '编辑实习生' : '新增实习生' }}</h2>
        </div>
        <button class="icon-button" type="button" title="关闭" @click="closeInternModal">
          <X :size="18" />
        </button>
      </div>
      <div v-if="internModal.error" class="form-error">{{ internModal.error }}</div>
      <div class="form-grid">
        <label>
          姓名
          <input v-model="internForm.name" required>
        </label>
        <label class="wide">
          备注
          <textarea v-model="internForm.note" rows="3"></textarea>
        </label>
        <label v-if="internModal.item" class="wide">
          专属链接
          <input :value="internModal.item.share_url" readonly>
        </label>
      </div>
      <div class="modal-actions">
        <button class="plain-button" type="button" @click="closeInternModal">关闭</button>
        <button class="primary-button" type="submit">保存</button>
      </div>
    </form>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue';
import { CalendarX, ChevronLeft, ChevronRight, Plus, X } from '@lucide/vue';
import { api } from '../api';

const props = defineProps({
  token: { type: String, default: '' },
});
const emit = defineEmits(['auth-required']);
const isPublicLink = computed(() => Boolean(props.token));
const interns = ref([]);
const selectedIntern = ref(null);
const currentWeekStart = ref(mondayOf(new Date()));
const error = ref('');
const schedule = reactive({
  week_start: '',
  week_end: '',
  schedules: [],
  capabilities: {
    can_create_work: false,
    can_request_leave: false,
    can_manage_all: false,
    can_view_all: false,
  },
});
const modal = reactive({ open: false, readonly: true, item: null, error: '' });
const form = reactive({ schedule_type: 'work', title: '', date: '', start: '09:00', end: '10:00', notes: '' });
const internModal = reactive({ open: false, item: null, error: '' });
const internForm = reactive({ name: '', note: '' });
const listCapabilities = reactive({ can_manage_interns: false });
const selection = reactive({ active: false, date: '', startHour: 9, endHour: 9 });

const hours = computed(() => Array.from({ length: 9 }, (_, index) => index + 9));
const weekDays = computed(() => {
  const base = parseLocalDate(currentWeekStart.value);
  return ['周一', '周二', '周三', '周四', '周五'].map((label, index) => {
    const day = new Date(base);
    day.setDate(base.getDate() + index);
    return { label, date: formatDate(day) };
  });
});
const modalTitle = computed(() => {
  if (modal.item && modal.readonly) return '安排详情';
  if (modal.item) return '编辑安排';
  return form.schedule_type === 'leave' ? '提交请假' : '新增工作安排';
});

function mondayOf(date) {
  const copy = new Date(date);
  const day = copy.getDay() || 7;
  copy.setDate(copy.getDate() - day + 1);
  return formatDate(copy);
}

function parseLocalDate(value) {
  const [year, month, day] = value.split('-').map(Number);
  return new Date(year, month - 1, day);
}

function formatDate(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function hourLabel(hour) {
  return `${String(hour).padStart(2, '0')}:00-${String(hour + 1).padStart(2, '0')}:00`;
}

function toMinutes(value) {
  const date = new Date(value);
  return date.getHours() * 60 + date.getMinutes();
}

function datePart(value) {
  return value.slice(0, 10);
}

function timePart(value) {
  return value.slice(11, 16);
}

function timeRange(item) {
  return `${timePart(item.start_time)}-${timePart(item.end_time)}`;
}

function schedulesForCell(date, hour) {
  const cellStart = hour * 60;
  const cellEnd = (hour + 1) * 60;
  return schedule.schedules.filter((item) => {
    if (datePart(item.start_time) !== date) return false;
    return toMinutes(item.start_time) < cellEnd && toMinutes(item.end_time) > cellStart;
  });
}

function isCellSelected(date, hour) {
  if (!selection.active || selection.date !== date) return false;
  const minHour = Math.min(selection.startHour, selection.endHour);
  const maxHour = Math.max(selection.startHour, selection.endHour);
  return hour >= minHour && hour <= maxHour;
}

function startSelection(date, hour, event) {
  if (isPublicLink.value || !schedule.capabilities.can_create_work || event.target.closest('.schedule-block')) return;
  selection.active = true;
  selection.date = date;
  selection.startHour = hour;
  selection.endHour = hour;
  window.addEventListener('mouseup', finishSelection, { once: true });
}

function updateSelection(date, hour) {
  if (!selection.active || selection.date !== date) return;
  selection.endHour = hour;
}

function finishSelection() {
  if (!selection.active) return;
  const date = selection.date;
  const startHour = Math.min(selection.startHour, selection.endHour);
  const endHour = Math.max(selection.startHour, selection.endHour) + 1;
  selection.active = false;
  openCreate('work', {
    date,
    start: `${String(startHour).padStart(2, '0')}:00`,
    end: `${String(endHour).padStart(2, '0')}:00`,
  });
}

function handleApiError(apiError) {
  if (isPublicLink.value) {
    error.value = apiError.message;
    return true;
  }
  if (apiError.status === 401 || apiError.status === 403) {
    emit('auth-required');
    return true;
  }
  return false;
}

async function loadInterns() {
  if (isPublicLink.value) return;
  try {
    const data = await api('/api/interns/');
    interns.value = data.interns;
    Object.assign(listCapabilities, data.capabilities || {});
    if (!selectedIntern.value && interns.value.length) {
      selectedIntern.value = interns.value[0];
    }
  } catch (apiError) {
    if (!handleApiError(apiError)) error.value = apiError.message;
  }
}

async function loadSchedule() {
  try {
    error.value = '';
    if (!isPublicLink.value && !selectedIntern.value) return;
    const path = isPublicLink.value
      ? `/api/intern-share/${props.token}/?week_start=${currentWeekStart.value}`
      : `/api/intern-schedules/?intern_id=${selectedIntern.value.id}&week_start=${currentWeekStart.value}`;
    const data = await api(path);
    if (isPublicLink.value) {
      selectedIntern.value = data.intern;
    }
    Object.assign(schedule, data);
  } catch (apiError) {
    if (!handleApiError(apiError)) error.value = apiError.message;
  }
}

async function selectIntern(intern) {
  selectedIntern.value = intern;
  await loadSchedule();
}

async function moveWeek(days) {
  const date = parseLocalDate(currentWeekStart.value);
  date.setDate(date.getDate() + days);
  currentWeekStart.value = formatDate(date);
  await loadSchedule();
}

async function goCurrentWeek() {
  currentWeekStart.value = mondayOf(new Date());
  await loadSchedule();
}

function fillForm(item) {
  form.schedule_type = item.schedule_type;
  form.title = item.title;
  form.date = datePart(item.start_time);
  form.start = timePart(item.start_time);
  form.end = timePart(item.end_time);
  form.notes = item.notes || '';
}

function openCreate(type, defaults = {}) {
  modal.open = true;
  modal.readonly = false;
  modal.item = null;
  modal.error = '';
  form.schedule_type = type;
  form.title = type === 'leave' ? '请假' : '';
  form.date = defaults.date || weekDays.value[0]?.date || currentWeekStart.value;
  form.start = defaults.start || '09:00';
  form.end = defaults.end || '10:00';
  form.notes = '';
}

function openDetail(item) {
  if (isPublicLink.value) return;
  modal.open = true;
  modal.readonly = true;
  modal.item = item;
  modal.error = '';
  fillForm(item);
}

function enableEdit() {
  modal.readonly = false;
}

function closeModal() {
  modal.open = false;
}

function schedulePayload() {
  return {
    intern_id: selectedIntern.value?.id,
    schedule_type: form.schedule_type,
    title: form.title,
    notes: form.notes,
    start_time: `${form.date}T${form.start}:00`,
    end_time: `${form.date}T${form.end}:00`,
  };
}

async function submitSchedule() {
  if (isPublicLink.value) {
    modal.error = '专属链接只能查看日程，不能提交或修改。';
    return;
  }
  try {
    modal.error = '';
    if (modal.item) {
      await api(`/api/intern-schedules/${modal.item.id}/`, {
        method: 'PATCH',
        body: JSON.stringify(schedulePayload()),
      });
    } else {
      await api('/api/intern-schedules/', {
        method: 'POST',
        body: JSON.stringify(schedulePayload()),
      });
    }
    closeModal();
    await loadSchedule();
  } catch (apiError) {
    if (!handleApiError(apiError)) modal.error = apiError.message;
  }
}

async function deleteSchedule() {
  if (!modal.item) return;
  if (isPublicLink.value) {
    modal.error = '专属链接只能查看日程，不能删除。';
    return;
  }
  try {
    modal.error = '';
    await api(`/api/intern-schedules/${modal.item.id}/`, { method: 'DELETE' });
    closeModal();
    await loadSchedule();
  } catch (apiError) {
    if (!handleApiError(apiError)) modal.error = apiError.message;
  }
}

function openInternModal(intern = null) {
  internModal.open = true;
  internModal.item = intern;
  internModal.error = '';
  internForm.name = intern?.name || '';
  internForm.note = intern?.note || '';
}

function closeInternModal() {
  internModal.open = false;
}

async function submitIntern() {
  try {
    internModal.error = '';
    if (internModal.item) {
      await api(`/api/interns/${internModal.item.id}/`, {
        method: 'PATCH',
        body: JSON.stringify(internForm),
      });
    } else {
      await api('/api/interns/', {
        method: 'POST',
        body: JSON.stringify(internForm),
      });
    }
    closeInternModal();
    selectedIntern.value = null;
    await loadInterns();
    await loadSchedule();
  } catch (apiError) {
    internModal.error = apiError.message;
  }
}

async function deleteIntern(intern) {
  try {
    await api(`/api/interns/${intern.id}/`, { method: 'DELETE' });
    selectedIntern.value = null;
    await loadInterns();
    await loadSchedule();
  } catch (apiError) {
    error.value = apiError.message;
  }
}

async function copyShareUrl(intern) {
  if (navigator.clipboard && intern.share_url) {
    await navigator.clipboard.writeText(intern.share_url);
  }
}

onMounted(async () => {
  await loadInterns();
  await loadSchedule();
});
</script>
