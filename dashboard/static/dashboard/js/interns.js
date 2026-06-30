(() => {
    const shareToken = window.NT_INTERN_SHARE_TOKEN || '';
    const state = {
        interns: [],
        selectedIntern: null,
        weekStart: mondayOf(new Date()),
        schedules: [],
        capabilities: {},
        modalItem: null,
        modalReadonly: false,
        modalType: 'work',
        internModalItem: null,
        listCapabilities: {},
        selection: null,
    };
    const weekdays = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'];
    const dayStartMinutes = 9 * 60;
    const dayEndMinutes = 18 * 60;
    const lunchStartMinutes = 12 * 60;
    const lunchEndMinutes = 13 * 60 + 30;
    const slotMinutes = 30;
    const totalSlots = (dayEndMinutes - dayStartMinutes) / slotMinutes;
    const lunchStartSlot = (lunchStartMinutes - dayStartMinutes) / slotMinutes;
    const lunchEndSlot = (lunchEndMinutes - dayStartMinutes) / slotMinutes;
    const lunchRemovedSlots = lunchEndSlot - lunchStartSlot;
    const weekendCells = [
        { label: '上午（尽量不要周末布置工作）', startSlot: 0, endSlot: lunchStartSlot },
        { label: '下午（尽量不要周末布置工作）', startSlot: lunchEndSlot, endSlot: totalSlots },
    ];
    const $ = (id) => document.getElementById(id);

    function getCookie(name) {
        const value = `; ${document.cookie}`;
        const parts = value.split(`; ${name}=`);
        return parts.length === 2 ? parts.pop().split(';').shift() : '';
    }

    async function request(path, options = {}) {
        const response = await fetch(path, {
            credentials: 'include',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken'),
                ...(options.headers || {}),
            },
            ...options,
        });
        const payload = await response.json().catch(() => ({ ok: false, error: response.statusText }));
        if (!response.ok || !payload.ok) throw new Error(payload.error || response.statusText);
        return payload.data;
    }

    function formatDate(date) {
        const y = date.getFullYear();
        const m = String(date.getMonth() + 1).padStart(2, '0');
        const d = String(date.getDate()).padStart(2, '0');
        return `${y}-${m}-${d}`;
    }

    function parseDate(value) {
        const [y, m, d] = value.split('-').map(Number);
        return new Date(y, m - 1, d);
    }

    function mondayOf(date) {
        const copy = new Date(date);
        const day = copy.getDay() || 7;
        copy.setDate(copy.getDate() - day + 1);
        return formatDate(copy);
    }

    function datePart(value) { return value.slice(0, 10); }
    function timePart(value) { return value.slice(11, 16); }
    function formatMinutes(minutes) {
        const hour = Math.floor(minutes / 60);
        const minute = minutes % 60;
        return `${String(hour).padStart(2, '0')}:${String(minute).padStart(2, '0')}`;
    }
    function toMinutes(value) {
        const date = new Date(value);
        return date.getHours() * 60 + date.getMinutes();
    }
    function minutesToSlot(minutes, roundUp = false) {
        const raw = (minutes - dayStartMinutes) / slotMinutes;
        return roundUp ? Math.ceil(raw) : Math.floor(raw);
    }

    function shareUrlFor(intern) {
        if (!intern) return '';
        const token = intern.share_token || (intern.share_url || '').split('/interns/share/').pop();
        if (!token) return intern.share_url || '';
        try {
            return new URL(`/interns/share/${token}`, window.location.origin).href;
        } catch (exc) {
            return intern.share_url || '';
        }
    }

    async function copyText(text) {
        if (!text) return false;
        if (navigator.clipboard && window.isSecureContext) {
            try {
                await navigator.clipboard.writeText(text);
                return true;
            } catch (exc) {
                // Fall through to the textarea fallback for older or restricted browsers.
            }
        }
        const textarea = document.createElement('textarea');
        textarea.value = text;
        textarea.setAttribute('readonly', '');
        textarea.style.position = 'fixed';
        textarea.style.left = '-9999px';
        document.body.appendChild(textarea);
        textarea.select();
        const copied = document.execCommand('copy');
        document.body.removeChild(textarea);
        return copied;
    }

    function showCopyNotice(message, isError = false) {
        const node = $('copyToast');
        node.textContent = message;
        node.classList.toggle('error', isError);
        node.hidden = false;
        clearTimeout(node._timer);
        node._timer = setTimeout(() => { node.hidden = true; }, 2200);
    }

    function weekDays() {
        const base = parseDate(state.weekStart);
        return weekdays.map((label, index) => {
            const day = new Date(base);
            day.setDate(base.getDate() + index);
            return { label, date: formatDate(day), isWeekend: index >= 5 };
        });
    }

    function timeSlots() {
        return Array.from({ length: totalSlots }, (_, index) => {
            const start = dayStartMinutes + index * slotMinutes;
            const end = start + slotMinutes;
            return { index, label: `${formatMinutes(start)}-${formatMinutes(end)}` };
        });
    }

    function visibleRows() {
        const rows = [];
        timeSlots().forEach((slot) => {
            if (slot.index === lunchStartSlot) {
                rows.push({
                    type: 'lunch',
                    index: lunchStartSlot,
                    startSlot: lunchStartSlot,
                    endSlot: lunchEndSlot,
                    label: '午休',
                    timeLabel: `${formatMinutes(lunchStartMinutes)}-${formatMinutes(lunchEndMinutes)}`,
                });
            }
            if (slot.index >= lunchStartSlot && slot.index < lunchEndSlot) return;
            rows.push({
                type: 'work',
                index: slot.index,
                startSlot: slot.index,
                endSlot: slot.index + 1,
                label: slot.label,
                timeLabel: slot.label,
            });
        });
        return rows;
    }

    function slotToDisplayLine(slot) {
        if (slot <= lunchStartSlot) return slot;
        if (slot >= lunchEndSlot) return slot - lunchRemovedSlots + 1;
        return lunchStartSlot;
    }

    function cellsForDay(day) {
        if (day.isWeekend) return weekendCells;
        return visibleRows()
            .filter((row) => row.type === 'work')
            .map((row) => ({
                label: row.label,
                startSlot: row.startSlot,
                endSlot: row.endSlot,
            }));
    }

    function scheduleBlocks(days) {
        return state.schedules.map((item) => {
            const dayIndex = days.findIndex((day) => day.date === datePart(item.start_time));
            if (dayIndex < 0) return '';
            const startSlot = Math.max(0, Math.min(totalSlots, minutesToSlot(toMinutes(item.start_time))));
            const endSlot = Math.max(startSlot + 1, Math.min(totalSlots, minutesToSlot(toMinutes(item.end_time), true)));
            const typeStyle = item.schedule_type === 'leave'
                ? 'color:#475569;background:#e5e7eb;border-color:#cbd5e1;'
                : 'color:#173b34;background:#e8f5f0;border-color:#b9ddcf;';
            const startLine = slotToDisplayLine(startSlot);
            const endLine = Math.max(startLine + 1, slotToDisplayLine(endSlot));
            return `
                <button class="schedule-block ${item.schedule_type}" type="button" data-schedule-id="${item.id}" style="grid-column:${dayIndex + 2};grid-row:${startLine + 2} / ${endLine + 2};display:grid;gap:4px;width:auto;min-height:0;margin:3px 6px;padding:8px;border:1px solid;border-radius:6px;cursor:pointer;font:inherit;text-align:left;z-index:2;overflow:hidden;${typeStyle}">
                    <span>${timePart(item.start_time)}-${timePart(item.end_time)}</span>
                    <strong>${item.title}</strong>
                    <small>${item.created_by_name}</small>
                </button>`;
        }).join('');
    }

    function setError(message) {
        $('scheduleError').hidden = !message;
        $('scheduleError').textContent = message || '';
    }

    function renderInterns() {
        $('internCount').textContent = `${state.interns.length} 人`;
        $('newInternBtn').hidden = !state.listCapabilities.can_manage_interns;
        $('internSideActions').hidden = !(state.selectedIntern && state.listCapabilities.can_manage_interns);
        $('internList').innerHTML = state.interns.map((intern) => `
            <button class="intern-list-item ${state.selectedIntern && state.selectedIntern.id === intern.id ? 'active' : ''}" type="button" data-intern-id="${intern.id}">
                <strong>${intern.name}</strong>
                <span>${intern.note || '暂无备注'}</span>
            </button>
        `).join('') || '<p class="intern-empty">暂无实习生档案。</p>';
    }

    function renderSchedule() {
        $('selectedInternName').textContent = state.selectedIntern ? state.selectedIntern.name : '请选择实习生';
        $('weekLabel').textContent = state.selectedIntern ? `${shareToken ? '专属链接' : '内部管理'} · ${state.weekStart} 至 ${state.weekEnd || ''}` : '';
        if (!shareToken) {
            $('leaveBtn').hidden = !state.capabilities.can_request_leave;
            $('workBtn').hidden = !state.capabilities.can_create_work;
        }
        const days = weekDays();
        const rows = visibleRows();
        const gridStyle = `position:relative;display:grid;width:100%;min-width:0;background:#fff;grid-template-columns:72px repeat(5, minmax(0, 1fr)) repeat(2, minmax(0, .7fr));grid-template-rows:auto repeat(${rows.length}, minmax(30px, auto));`;
        const headStyle = 'box-sizing:border-box;padding:8px 4px;color:#334155;background:#eef3f8;font-size:12px;font-weight:700;border-right:1px solid #d8e1ec;border-bottom:1px solid #d8e1ec;overflow:hidden;';
        const timeStyle = 'box-sizing:border-box;padding:6px 4px;color:#334155;background:#eef3f8;font-size:11px;line-height:1.2;border-right:1px solid #d8e1ec;border-bottom:1px solid #d8e1ec;white-space:normal;';
        const lunchTimeStyle = 'box-sizing:border-box;padding:6px 4px;color:#ffffff;background:#263241;font-size:11px;line-height:1.2;border-right:1px solid #1f2937;border-bottom:1px solid #1f2937;white-space:normal;font-weight:700;';
        const cellStyle = 'box-sizing:border-box;min-height:30px;padding:0;background:#fbfcfe;border:0;border-right:1px solid #d8e1ec;border-bottom:1px solid #d8e1ec;cursor:crosshair;font:inherit;text-align:center;';
        const timeColumn = rows.map((row, rowIndex) => `<div class="time-column schedule-time-slot${row.type === 'lunch' ? ' lunch' : ''}" style="grid-column:1;grid-row:${rowIndex + 2};${row.type === 'lunch' ? lunchTimeStyle : timeStyle}">${row.timeLabel}</div>`).join('');
        const dayCells = days.map((day, dayIndex) => cellsForDay(day).map((cell) => `
            <button class="schedule-cell ${isCellSelected(day.date, cell) ? 'selecting' : ''}" type="button" data-date="${day.date}" data-start-slot="${cell.startSlot}" data-end-slot="${cell.endSlot}" style="grid-column:${dayIndex + 2};grid-row:${slotToDisplayLine(cell.startSlot) + 2} / ${slotToDisplayLine(cell.endSlot) + 2};${cellStyle}">
                ${day.isWeekend ? `<span class="weekend-cell-label">${cell.label}</span>` : ''}
            </button>`).join('')).join('');
        const lunchRow = `<div class="schedule-lunch-row" style="grid-column:2 / 9;grid-row:${slotToDisplayLine(lunchStartSlot) + 2} / ${slotToDisplayLine(lunchEndSlot) + 2};display:flex;align-items:center;justify-content:center;color:#ffffff;background:#263241;border-bottom:1px solid #1f2937;font-size:13px;font-weight:700;letter-spacing:0;z-index:1;">午休 12:00-13:30</div>`;
        $('scheduleTable').style.cssText = gridStyle;
        $('scheduleTable').innerHTML = `
            <div class="schedule-head time-column" style="grid-column:1;grid-row:1;${headStyle}">时间</div>
            ${days.map((day, dayIndex) => `<div class="schedule-head day-column" style="grid-column:${dayIndex + 2};grid-row:1;text-align:center;${headStyle}"><strong>${day.label}</strong><span>${day.date}</span></div>`).join('')}
            ${timeColumn}
            ${dayCells}
            ${lunchRow}
            ${scheduleBlocks(days)}
        `;
    }

    function isCellSelected(date, cell) {
        if (!state.selection || state.selection.date !== date) return false;
        const minSlot = Math.min(state.selection.anchorStart, state.selection.currentStart);
        const maxSlot = Math.max(state.selection.anchorEnd, state.selection.currentEnd);
        return cell.startSlot < maxSlot && cell.endSlot > minSlot;
    }

    async function loadInterns() {
        if (shareToken) return;
        const data = await request('/api/interns/');
        state.interns = data.interns;
        state.listCapabilities = data.capabilities || {};
        state.selectedIntern = state.selectedIntern || state.interns[0] || null;
        renderInterns();
    }

    async function loadSchedule() {
        if (!shareToken && !state.selectedIntern) {
            renderSchedule();
            return;
        }
        const path = shareToken
            ? `/api/intern-share/${shareToken}/?week_start=${state.weekStart}`
            : `/api/intern-schedules/?intern_id=${state.selectedIntern.id}&week_start=${state.weekStart}`;
        const data = await request(path);
        if (shareToken) state.selectedIntern = data.intern;
        state.schedules = data.schedules;
        state.capabilities = data.capabilities;
        state.weekEnd = data.week_end;
        renderSchedule();
    }

    function setReadonly(readonly) {
        state.modalReadonly = readonly;
        ['scheduleTitle', 'scheduleDate', 'scheduleStart', 'scheduleEnd', 'scheduleNotes'].forEach((id) => { $(id).disabled = readonly; });
        $('saveScheduleBtn').hidden = readonly;
        $('editScheduleBtn').hidden = !(readonly && state.modalItem && state.modalItem.can_edit);
        $('deleteScheduleBtn').hidden = readonly || !(state.modalItem && state.modalItem.can_delete);
    }

    function openModal(type, item = null) {
        if (shareToken) return;
        state.modalType = type;
        state.modalItem = item;
        $('modalError').hidden = true;
        $('modalEyebrow').textContent = type === 'leave' ? 'Leave' : 'Work';
        $('modalTitle').textContent = item ? '安排详情' : (type === 'leave' ? '提交请假' : '新增工作安排');
        $('scheduleTitle').value = item ? item.title : (type === 'leave' ? '请假' : '');
        $('scheduleDate').value = item ? datePart(item.start_time) : weekDays()[0].date;
        $('scheduleStart').value = item ? timePart(item.start_time) : '09:00';
        $('scheduleEnd').value = item ? timePart(item.end_time) : '10:00';
        $('scheduleNotes').value = item ? item.notes || '' : '';
        $('scheduleMeta').innerHTML = item ? `<span>安排人：${item.created_by_name}</span><span>类型：${item.schedule_type_label}</span>` : '';
        setReadonly(!!item);
        $('scheduleModal').hidden = false;
    }

    function openModalForRange(date, startSlot, endSlot) {
        if (shareToken || !state.capabilities.can_create_work) return;
        const from = Math.min(startSlot, endSlot);
        const to = Math.max(startSlot, endSlot);
        openModal('work');
        $('scheduleDate').value = date;
        $('scheduleStart').value = formatMinutes(dayStartMinutes + from * slotMinutes);
        $('scheduleEnd').value = formatMinutes(dayStartMinutes + to * slotMinutes);
    }

    function closeModal() {
        $('scheduleModal').hidden = true;
    }

    async function submitSchedule(event) {
        event.preventDefault();
        if (shareToken) {
            $('modalError').hidden = false;
            $('modalError').textContent = '专属链接只能查看日程，不能提交或修改。';
            return;
        }
        const payload = {
            intern_id: state.selectedIntern && state.selectedIntern.id,
            schedule_type: state.modalType,
            title: $('scheduleTitle').value,
            notes: $('scheduleNotes').value,
            start_time: `${$('scheduleDate').value}T${$('scheduleStart').value}:00`,
            end_time: `${$('scheduleDate').value}T${$('scheduleEnd').value}:00`,
        };
        try {
            if (state.modalItem) {
                await request(`/api/intern-schedules/${state.modalItem.id}/`, { method: 'PATCH', body: JSON.stringify(payload) });
            } else {
                await request('/api/intern-schedules/', { method: 'POST', body: JSON.stringify(payload) });
            }
            closeModal();
            await loadSchedule();
        } catch (exc) {
            $('modalError').hidden = false;
            $('modalError').textContent = exc.message;
        }
    }

    async function init() {
        try {
            await loadInterns();
            await loadSchedule();
        } catch (exc) {
            setError(exc.message);
        }
    }

    function openInternModal(intern = null) {
        state.internModalItem = intern;
        $('internModalTitle').textContent = intern ? '编辑实习生' : '新增实习生';
        $('internName').value = intern ? intern.name : '';
        $('internNote').value = intern ? intern.note || '' : '';
        $('internShareWrap').hidden = !intern;
        $('internShareUrl').value = intern ? shareUrlFor(intern) : '';
        $('deleteInternInModalBtn').hidden = !intern;
        $('internModalError').hidden = true;
        $('internModal').hidden = false;
    }

    function closeInternModal() {
        $('internModal').hidden = true;
    }

    if (!shareToken) $('internList').addEventListener('click', async (event) => {
        const button = event.target.closest('[data-intern-id]');
        if (!button) return;
        state.selectedIntern = state.interns.find((intern) => String(intern.id) === button.dataset.internId);
        renderInterns();
        await loadSchedule();
    });
    $('scheduleTable').addEventListener('click', (event) => {
        const button = event.target.closest('[data-schedule-id]');
        if (!button) return;
        const item = state.schedules.find((schedule) => String(schedule.id) === button.dataset.scheduleId);
        if (item && !shareToken) openModal(item.schedule_type, item);
    });
    $('scheduleTable').addEventListener('mousedown', (event) => {
        if (shareToken || event.target.closest('[data-schedule-id]')) return;
        const cell = event.target.closest('.schedule-cell');
        if (!cell || !state.capabilities.can_create_work) return;
        event.preventDefault();
        state.selection = {
            date: cell.dataset.date,
            anchorStart: Number(cell.dataset.startSlot),
            anchorEnd: Number(cell.dataset.endSlot),
            currentStart: Number(cell.dataset.startSlot),
            currentEnd: Number(cell.dataset.endSlot),
        };
        renderSchedule();
    });
    $('scheduleTable').addEventListener('mouseover', (event) => {
        if (!state.selection) return;
        const cell = event.target.closest('.schedule-cell');
        if (!cell || cell.dataset.date !== state.selection.date) return;
        state.selection.currentStart = Number(cell.dataset.startSlot);
        state.selection.currentEnd = Number(cell.dataset.endSlot);
        renderSchedule();
    });
    document.addEventListener('mouseup', () => {
        if (!state.selection) return;
        const selection = state.selection;
        state.selection = null;
        renderSchedule();
        openModalForRange(
            selection.date,
            Math.min(selection.anchorStart, selection.currentStart),
            Math.max(selection.anchorEnd, selection.currentEnd),
        );
    });
    $('prevWeekBtn').addEventListener('click', async () => {
        const date = parseDate(state.weekStart);
        date.setDate(date.getDate() - 7);
        state.weekStart = formatDate(date);
        await loadSchedule();
    });
    $('nextWeekBtn').addEventListener('click', async () => {
        const date = parseDate(state.weekStart);
        date.setDate(date.getDate() + 7);
        state.weekStart = formatDate(date);
        await loadSchedule();
    });
    $('currentWeekBtn').addEventListener('click', async () => {
        state.weekStart = mondayOf(new Date());
        await loadSchedule();
    });
    if (!shareToken) $('workBtn').addEventListener('click', () => openModal('work'));
    if (!shareToken) $('leaveBtn').addEventListener('click', () => openModal('leave'));
    if (!shareToken) $('closeModalBtn').addEventListener('click', closeModal);
    if (!shareToken) $('cancelModalBtn').addEventListener('click', closeModal);
    if (!shareToken) $('editScheduleBtn').addEventListener('click', () => {
        $('modalTitle').textContent = '编辑安排';
        setReadonly(false);
    });
    if (!shareToken) $('deleteScheduleBtn').addEventListener('click', async () => {
        if (!state.modalItem) return;
        if (shareToken) return;
        await request(`/api/intern-schedules/${state.modalItem.id}/`, { method: 'DELETE' });
        closeModal();
        await loadSchedule();
    });
    if (!shareToken) $('newInternBtn').addEventListener('click', () => openInternModal());
    if (!shareToken) $('editInternBtn').addEventListener('click', () => { if (state.selectedIntern) openInternModal(state.selectedIntern); });
    if (!shareToken) $('copyInternLinkBtn').addEventListener('click', async () => {
        const copied = await copyText(shareUrlFor(state.selectedIntern));
        showCopyNotice(copied ? '专属链接已复制' : '复制失败，请手动复制', !copied);
    });
    if (!shareToken) $('deleteInternInModalBtn').addEventListener('click', async () => {
        if (!state.internModalItem) return;
        await request(`/api/interns/${state.internModalItem.id}/`, { method: 'DELETE' });
        closeInternModal();
        state.selectedIntern = null;
        await loadInterns();
        await loadSchedule();
    });
    if (!shareToken) $('closeInternModalBtn').addEventListener('click', closeInternModal);
    if (!shareToken) $('cancelInternModalBtn').addEventListener('click', closeInternModal);
    if (!shareToken) $('internForm').addEventListener('submit', async (event) => {
        event.preventDefault();
        const payload = { name: $('internName').value, note: $('internNote').value };
        try {
            if (state.internModalItem) {
                await request(`/api/interns/${state.internModalItem.id}/`, { method: 'PATCH', body: JSON.stringify(payload) });
            } else {
                await request('/api/interns/', { method: 'POST', body: JSON.stringify(payload) });
            }
            closeInternModal();
            state.selectedIntern = null;
            await loadInterns();
            await loadSchedule();
        } catch (exc) {
            $('internModalError').hidden = false;
            $('internModalError').textContent = exc.message;
        }
    });
    if (!shareToken) $('scheduleForm').addEventListener('submit', submitSchedule);
    init();
})();

