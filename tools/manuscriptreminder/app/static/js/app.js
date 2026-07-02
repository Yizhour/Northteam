const state = {
  config: {},
  preview: { columns: [], rows: [] },
  overview: {},
  ready: false,
  isBinding: false,
  autoSaveTimer: null,
  lastLogsText: "",
  runningActions: new Set(),
};

const $ = (id) => document.getElementById(id);

async function api(path, options = {}) {
  const basePath = (window.MANUSCRIPT_REMINDER_BASE_PATH || "").replace(/\/$/, "");
  const response = await fetch(`${basePath}${path}`, {
    headers: options.body instanceof FormData ? undefined : { "Content-Type": "application/json" },
    ...options,
  });
  const payload = await response.json().catch(() => ({ ok: false, error: response.statusText }));
  if (!response.ok || !payload.ok) throw new Error(payload.error || response.statusText);
  return payload.data;
}

function toast(message) {
  const node = $("toast");
  node.textContent = message;
  node.classList.add("show");
  clearTimeout(node._timer);
  node._timer = setTimeout(() => node.classList.remove("show"), 2600);
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function input(value = "", attrs = "") {
  return `<input ${attrs} value="${escapeHtml(value)}">`;
}

async function loadAll() {
  state.isBinding = true;
  const [config, preview, overview, logs] = await Promise.all([
    api("/api/config"),
    api("/api/preview"),
    api("/api/overview"),
    api("/api/logs"),
  ]);
  Object.assign(state, { config, preview, overview });
  bindConfig();
  renderOverview();
  renderPreview();
  renderColumns();
  renderReceivers();
  renderLogs(logs);
  state.isBinding = false;
  state.ready = true;
}

function columnOptions(includeBlank = false) {
  const options = state.preview.columns || [];
  return (includeBlank ? [`<option value="">(未选择)</option>`] : [])
    .concat(options.map((col) => `<option>${escapeHtml(col)}</option>`))
    .join("");
}

function bindConfig() {
  const c = state.config;
  $("headerRow").value = c.ui_header_row_index ?? 0;
  $("senderEmail").value = c.sender_email || "";
  $("authCode").value = "";
  $("authCode").placeholder = c.auth_code_set ? "已保存，留空保持原授权码" : "请输入邮箱授权码";
  $("sendInterval").value = c.send_interval_seconds ?? 30;
  $("smtpTimeoutSeconds").value = c.smtp_timeout_seconds ?? 8;
  $("ownerColumn").innerHTML = columnOptions();
  $("archiveDeadlineColumn").innerHTML = columnOptions();
  $("associationDeadlineColumn").innerHTML = columnOptions();
  $("ownerColumn").value = c.owner_column || "";
  $("ownerName").value = c.owner_name || "";
  $("archiveDeadlineColumn").value = c.archive_deadline_column || "";
  $("associationDeadlineColumn").value = c.association_deadline_column || "";
  $("associationThreshold").value = c.association_workday_threshold ?? 10;
  $("weeklyEnabled").checked = !!c.weekly_enabled;
  $("weeklyTime").value = c.weekly_time || "09:00";
  $("scheduleDay").value = c.schedule_day || "Monday";
  $("emailSubject").value = c.email_subject || "";
  $("emailIntro").value = c.email_intro || "";
  $("dailyEnabled").checked = !!c.daily_enabled;
  $("dailyTime").value = c.daily_time || "09:00";
  $("dailyEmailReceiver").value = c.daily_email_receiver || "";
  $("dailyTemplate").value = c.daily_msg_template || "";
  $("dailyIntro").value = c.daily_msg_intro || "";
}

function renderOverview() {
  $("archiveCount").textContent = state.overview.archive_count ?? 0;
  $("overdueCount").textContent = state.overview.overdue_count ?? 0;
  $("associationCount").textContent = state.overview.association_warning_count ?? 0;
}

function renderPreview() {
  $("dataPath").textContent = state.preview.path ? `当前数据库数据：来源 ${state.preview.path}；共 ${state.preview.total_rows || 0} 行` : "尚未加载底稿报送数据。";
  const columns = state.preview.columns || [];
  const rows = state.preview.rows || [];
  $("previewTable").innerHTML =
    `<thead><tr>${columns.map((col) => `<th>${escapeHtml(col)}</th>`).join("")}</tr></thead>` +
    `<tbody>${rows.map((row) => `<tr>${columns.map((col) => `<td>${escapeHtml(row[col] ?? "")}</td>`).join("")}</tr>`).join("")}</tbody>`;
}

function renderColumns() {
  const columns = state.preview.columns || [];
  const dateColumns = new Set(state.config.date_columns || []);
  const displayColumns = new Set(state.config.display_columns || []);
  const colors = state.config.column_colors || {};
  const smsTexts = state.config.column_sms_texts || {};
  const palette = ["#e74c3c", "#3498db", "#2ecc71", "#9b59b6", "#f39c12", "#1abc9c", "#d35400", "#c0392b"];
  $("columnsTable").innerHTML = `
    <thead><tr><th>原数据列名</th><th>监控日期</th><th>事件颜色</th><th>短信显示文本</th><th>邮件/首页展示</th></tr></thead>
    <tbody>${columns.map((col, idx) => `<tr data-col="${escapeHtml(col)}">
      <td><strong>${escapeHtml(col)}</strong></td>
      <td><input class="col-date" type="checkbox" ${dateColumns.has(col) ? "checked" : ""}></td>
      <td><input class="col-color" type="color" value="${escapeHtml(colors[col] || palette[idx % palette.length])}"></td>
      <td>${input(smsTexts[col] || "", 'class="col-sms"')}</td>
      <td><input class="col-display" type="checkbox" ${displayColumns.has(col) ? "checked" : ""}></td>
    </tr>`).join("")}</tbody>`;
}

function renderReceivers() {
  const rows = state.config.receiver_list || [];
  $("receiversTable").innerHTML = `<thead><tr><th>邮箱地址</th><th>备注</th><th>操作</th></tr></thead><tbody>` +
    rows.map((item, idx) => `<tr><td>${input(item.email || "", 'data-field="email"')}</td><td>${input(item.remark || "", 'data-field="remark"')}</td><td><button class="danger linkish" data-remove-receiver="${idx}">删除</button></td></tr>`).join("") +
    `</tbody>`;
}

function collectConfig() {
  const config = structuredClone(state.config);
  Object.assign(config, {
    sender_email: $("senderEmail").value.trim(),
    send_interval_seconds: Math.max(30, Number($("sendInterval").value || 30)),
    smtp_timeout_seconds: Math.max(3, Number($("smtpTimeoutSeconds").value || 8)),
    ui_header_row_index: Number($("headerRow").value || 0),
    owner_column: $("ownerColumn").value,
    owner_name: $("ownerName").value.trim(),
    archive_deadline_column: $("archiveDeadlineColumn").value,
    association_deadline_column: $("associationDeadlineColumn").value,
    association_workday_threshold: Math.max(1, Number($("associationThreshold").value || 10)),
    weekly_enabled: $("weeklyEnabled").checked,
    weekly_time: $("weeklyTime").value || "09:00",
    schedule_day: $("scheduleDay").value,
    email_subject: $("emailSubject").value,
    email_intro: $("emailIntro").value,
    daily_enabled: $("dailyEnabled").checked,
    daily_time: $("dailyTime").value || "09:00",
    daily_email_receiver: $("dailyEmailReceiver").value.trim(),
    daily_msg_template: $("dailyTemplate").value,
    daily_msg_intro: $("dailyIntro").value,
  });
  if ($("authCode").value.trim()) config.auth_code = $("authCode").value.trim();
  const date_columns = [];
  const display_columns = [];
  const column_colors = {};
  const column_sms_texts = {};
  $("columnsTable").querySelectorAll("tbody tr").forEach((tr) => {
    const col = tr.dataset.col;
    if (tr.querySelector(".col-date")?.checked) {
      date_columns.push(col);
      column_colors[col] = tr.querySelector(".col-color").value;
      const sms = tr.querySelector(".col-sms").value.trim();
      if (sms) column_sms_texts[col] = sms;
    }
    if (tr.querySelector(".col-display")?.checked) display_columns.push(col);
  });
  Object.assign(config, { date_columns, display_columns, column_colors, column_sms_texts });
  const receivers = [];
  $("receiversTable").querySelectorAll("tbody tr").forEach((tr) => {
    const email = tr.querySelector('[data-field="email"]').value.trim();
    const remark = tr.querySelector('[data-field="remark"]').value.trim();
    if (email) receivers.push({ email, remark });
  });
  config.receiver_list = receivers;
  return config;
}

async function saveConfig(options = {}) {
  state.config = await api("/api/config", { method: "POST", body: JSON.stringify(collectConfig()) });
  state.overview = await api("/api/overview");
  if (!options.silent) {
    state.isBinding = true;
    bindConfig();
    renderColumns();
    renderReceivers();
    renderOverview();
    state.isBinding = false;
    toast("设置已保存");
  }
}

function scheduleConfigAutoSave() {
  if (!state.ready || state.isBinding) return;
  clearTimeout(state.autoSaveTimer);
  state.autoSaveTimer = setTimeout(async () => {
    try {
      await saveConfig({ silent: true });
      toast("已自动保存");
    } catch (err) {
      toast(`自动保存失败：${err.message}`);
    }
  }, 1000);
}

function renderLogs(logs) {
  const lines = logs || [];
  const text = lines.length ? [`共 ${lines.length} 条日志`, ...lines].join("\n") : "暂无日志";
  if (text === state.lastLogsText) return;
  state.lastLogsText = text;
  $("logBox").textContent = text;
}

async function refreshLogs() {
  renderLogs(await api("/api/logs?limit=2000"));
}

async function runExclusive(actionKey, buttonId, callback) {
  if (state.runningActions.has(actionKey)) return toast("任务正在执行，请勿重复点击");
  state.runningActions.add(actionKey);
  const button = $(buttonId);
  if (button) button.disabled = true;
  try {
    await callback();
  } finally {
    state.runningActions.delete(actionKey);
    if (button) button.disabled = false;
  }
}

function setupEvents() {
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach((node) => node.classList.remove("active"));
      document.querySelectorAll(".tab-panel").forEach((node) => node.classList.remove("active"));
      tab.classList.add("active");
      $(tab.dataset.tab).classList.add("active");
      if (tab.dataset.tab === "logsTab") refreshLogs();
    });
  });

  ["columnsTab", "scheduleTab", "receiversTable", "sharedSettingsDialog"].forEach((id) => {
    const root = $(id);
    root.addEventListener("input", (event) => {
      if (event.target.type === "file" || event.target.id === "authCode") return;
      scheduleConfigAutoSave();
    });
    root.addEventListener("change", (event) => {
      if (event.target.type === "file") return;
      scheduleConfigAutoSave();
    });
  });

  $("sharedSettingsBtn").addEventListener("click", () => $("sharedSettingsDialog").showModal());
  $("closeSharedSettingsBtn").addEventListener("click", () => $("sharedSettingsDialog").close());
  $("refreshBtn").addEventListener("click", () => loadAll().then(() => toast("已刷新")).catch((err) => toast(err.message)));

  $("dataFile").addEventListener("change", async () => {
    const file = $("dataFile").files[0];
    if (!file) return;
    const form = new FormData();
    form.append("file", file);
    form.append("header", $("headerRow").value || "0");
    state.preview = await api("/api/upload/data", { method: "POST", body: form });
    state.config = await api("/api/config");
    state.overview = await api("/api/overview");
    bindConfig();
    renderOverview();
    renderPreview();
    renderColumns();
    $("dataFile").value = "";
    toast("底稿报送数据已上传并写入数据库");
  });

  $("refreshPreviewBtn").addEventListener("click", async () => {
    state.preview = await api("/api/preview");
    state.overview = await api("/api/overview");
    renderOverview();
    renderPreview();
    renderColumns();
    toast("预览已刷新");
  });

  $("addReceiverBtn").addEventListener("click", () => {
    state.config.receiver_list = state.config.receiver_list || [];
    state.config.receiver_list.push({ email: "", remark: "" });
    renderReceivers();
    scheduleConfigAutoSave();
  });

  $("receiversTable").addEventListener("click", (event) => {
    const idx = event.target.dataset.removeReceiver;
    if (idx !== undefined) {
      state.config.receiver_list.splice(Number(idx), 1);
      renderReceivers();
      scheduleConfigAutoSave();
    }
  });

  $("runManualBtn").addEventListener("click", () => runExclusive("manual", "runManualBtn", async () => {
    await saveConfig();
    await api("/api/run/manual", { method: "POST" });
    await refreshLogs();
  }));
  $("runWeeklyBtn").addEventListener("click", () => runExclusive("weekly", "runWeeklyBtn", async () => {
    await saveConfig();
    await api("/api/run/weekly", { method: "POST" });
    await refreshLogs();
  }));
  $("runDailyBtn").addEventListener("click", () => runExclusive("daily", "runDailyBtn", async () => {
    await saveConfig();
    await api("/api/run/daily", { method: "POST" });
    await refreshLogs();
  }));
  $("clearLogsBtn").addEventListener("click", async () => {
    await api("/api/logs", { method: "DELETE" });
    await refreshLogs();
  });
}

setupEvents();
loadAll().catch((err) => toast(err.message));
setInterval(() => {
  if ($("logsTab").classList.contains("active")) refreshLogs().catch(() => {});
}, 5000);
