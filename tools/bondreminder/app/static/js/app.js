const state = {
  config: {},
  preview: { columns: [], rows: [] },
  contacts: [],
  tasks: [],
  customerData: { columns: [], rows: [] },
  customerSettings: {},
  ready: false,
  isBinding: false,
  autoSaveTimer: null,
  customerSettingsTimer: null,
  customerDataTimer: null,
};

const $ = (id) => document.getElementById(id);

async function api(path, options = {}) {
  const basePath = (window.BOND_REMINDER_BASE_PATH || "").replace(/\/$/, "");
  const requestPath = path.startsWith("/") ? `${basePath}${path}` : path;
  const response = await fetch(requestPath, {
    headers: options.body instanceof FormData ? undefined : { "Content-Type": "application/json" },
    ...options,
  });
  const payload = await response.json().catch(() => ({ ok: false, error: response.statusText }));
  if (!response.ok || !payload.ok) {
    throw new Error(payload.error || response.statusText);
  }
  return payload.data;
}

function toast(message) {
  const node = $("toast");
  node.textContent = message;
  node.classList.add("show");
  clearTimeout(node._timer);
  node._timer = setTimeout(() => node.classList.remove("show"), 2600);
}

function input(value = "", attrs = "") {
  return `<input ${attrs} value="${escapeHtml(value ?? "")}">`;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function today() {
  return new Date().toISOString().slice(0, 10);
}

async function loadAll() {
  state.isBinding = true;
  const [config, preview, contacts, tasks, customerData, customerSettings, logs] = await Promise.all([
    api("/api/config"),
    api("/api/bond-preview"),
    api("/api/contacts"),
    api("/api/tasks"),
    api("/api/customer-data"),
    api("/api/customer-settings"),
    api("/api/logs"),
  ]);
  Object.assign(state, { config, preview, contacts, tasks, customerData, customerSettings });
  bindConfig();
  renderPreview();
  renderColumns();
  renderReceivers();
  renderContacts();
  renderTasks();
  bindCustomerSettings();
  renderCustomerTable();
  renderLogs(logs);
  state.isBinding = false;
  state.ready = true;
}

function bindConfig() {
  const c = state.config;
  $("headerRow").value = c.ui_header_row_index ?? 0;
  $("senderEmail").value = c.sender_email || "";
  $("authCode").placeholder = c.auth_code_set ? "已保存，留空保持原授权码" : "请输入 163 邮箱授权码";
  $("authCode").value = "";
  $("authExpiryEnabled").checked = !!c.auth_expiry_enabled;
  $("authStartDate").value = c.auth_start_date || today();
  $("authValidityDays").value = c.auth_validity_days || 180;
  $("dailyEmailReceiver").value = c.daily_email_receiver || "";
  $("sendInterval").value = c.send_interval_seconds ?? c.birthday_send_interval_seconds ?? 30;
  $("smtpPreferredMode").value = c.smtp_preferred_mode || "auto";
  $("smtpTimeoutSeconds").value = c.smtp_timeout_seconds ?? 8;
  $("weeklyEnabled").checked = !!c.weekly_enabled;
  $("weeklyTime").value = c.weekly_time || c.common_time || "09:00";
  $("scheduleDay").value = c.schedule_day || "Monday";
  $("emailSubject").value = c.email_subject || "";
  $("emailIntro").value = c.email_intro || "";
  $("dailyEnabled").checked = !!c.daily_enabled;
  $("dailyTime").value = c.daily_time || c.common_time || "09:00";
  $("dailyTemplate").value = c.daily_msg_template || "";
  $("dailyIntro").value = c.daily_msg_intro || "";
  bindColumnSelects();
}

function bindColumnSelects() {
  const columns = state.preview.columns || [];
  const options = [`<option value="">(不提取)</option>`].concat(columns.map((col) => `<option>${escapeHtml(col)}</option>`)).join("");
  $("contactNameCol").innerHTML = options;
  $("contactPhoneCol").innerHTML = options;
  $("contactNameCol").value = state.config.col_contact_name || "";
  $("contactPhoneCol").value = state.config.col_contact_phone || "";
}

function renderPreview() {
  $("bondPath").textContent = state.preview.path ? `当前缓存：${state.preview.path}；共 ${state.preview.total_rows || 0} 行` : "尚未加载债券数据。";
  const table = $("previewTable");
  const columns = state.preview.columns || [];
  const rows = state.preview.rows || [];
  table.innerHTML = `<thead><tr>${columns.map((col) => `<th>${escapeHtml(col)}</th>`).join("")}</tr></thead>` +
    `<tbody>${rows.map((row) => `<tr>${columns.map((col) => `<td>${escapeHtml(row[col] ?? "")}</td>`).join("")}</tr>`).join("")}</tbody>`;
}

function renderColumns() {
  const columns = state.preview.columns || [];
  const dateColumns = new Set(state.config.date_columns || []);
  const displayColumns = new Set(state.config.display_columns || []);
  const colors = state.config.column_colors || {};
  const smsTexts = state.config.column_sms_texts || {};
  const defaults = state.config.default_column_mappings || {};
  const defaultDates = new Set(defaults.date_columns || []);
  const defaultDisplays = new Set(defaults.display_columns || []);
  const defaultSms = defaults.column_sms_texts || {};
  const palette = ["#e74c3c", "#3498db", "#2ecc71", "#9b59b6", "#f39c12", "#1abc9c", "#d35400", "#c0392b", "#16a085"];
  $("columnsTable").innerHTML = `
    <thead><tr><th>原数据列名</th><th>监控日期</th><th>事件颜色</th><th>短信显示文本</th><th>邮件展示</th></tr></thead>
    <tbody>${columns.map((col, idx) => {
      const checkedDate = dateColumns.has(col) || defaultDates.has(col);
      const checkedDisplay = displayColumns.has(col) || defaultDisplays.has(col);
      const color = colors[col] || palette[idx % palette.length];
      const text = smsTexts[col] || defaultSms[col] || "";
      return `<tr data-col="${escapeHtml(col)}">
        <td><strong>${escapeHtml(col)}</strong></td>
        <td><input class="col-date" type="checkbox" ${checkedDate ? "checked" : ""}></td>
        <td><input class="col-color" type="color" value="${escapeHtml(color)}"></td>
        <td>${input(text, 'class="col-sms"')}</td>
        <td><input class="col-display" type="checkbox" ${checkedDisplay ? "checked" : ""}></td>
      </tr>`;
    }).join("")}</tbody>`;
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
    weekly_time: $("weeklyTime").value || "09:00",
    daily_time: $("dailyTime").value || "09:00",
    common_time: $("weeklyTime").value || "09:00",
    sender_email: $("senderEmail").value.trim(),
    auth_expiry_enabled: $("authExpiryEnabled").checked,
    auth_start_date: $("authStartDate").value || today(),
    auth_validity_days: Number($("authValidityDays").value || 180),
    daily_email_receiver: $("dailyEmailReceiver").value.trim(),
    send_interval_seconds: Math.max(30, Number($("sendInterval").value || 30)),
    birthday_send_interval_seconds: Math.max(30, Number($("sendInterval").value || 30)),
    smtp_preferred_mode: $("smtpPreferredMode").value || "auto",
    smtp_timeout_seconds: Math.max(3, Number($("smtpTimeoutSeconds").value || 8)),
    weekly_enabled: $("weeklyEnabled").checked,
    schedule_day: $("scheduleDay").value,
    email_subject: $("emailSubject").value,
    email_intro: $("emailIntro").value,
    daily_enabled: $("dailyEnabled").checked,
    col_contact_name: $("contactNameCol").value,
    col_contact_phone: $("contactPhoneCol").value,
    daily_msg_template: $("dailyTemplate").value,
    daily_msg_intro: $("dailyIntro").value,
    ui_header_row_index: Number($("headerRow").value || 0),
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

  const receiverRows = [];
  $("receiversTable").querySelectorAll("tbody tr").forEach((tr) => {
    const email = tr.querySelector('[data-field="email"]').value.trim();
    const remark = tr.querySelector('[data-field="remark"]').value.trim();
    if (email) receiverRows.push({ email, remark });
  });
  config.receiver_list = receiverRows;
  return config;
}

async function saveConfig(options = {}) {
  const config = collectConfig();
  state.config = await api("/api/config", { method: "POST", body: JSON.stringify(config) });
  if (!options.silent) {
    state.isBinding = true;
    bindConfig();
    renderColumns();
    renderReceivers();
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

function setupConfigAutoSave() {
  const roots = ["dataTab", "columnsTable", "scheduleTab", "receiversTable", "sharedSettingsDialog"];
  for (const id of roots) {
    const root = $(id);
    if (!root) continue;
    root.addEventListener("input", (event) => {
      if (event.target.type === "file" || event.target.id === "authCode") return;
      scheduleConfigAutoSave();
    });
    root.addEventListener("change", (event) => {
      if (event.target.type === "file") return;
      scheduleConfigAutoSave();
    });
  }
}

function renderContacts() {
  $("contactsTable").innerHTML = `<thead><tr><th>姓名</th><th>电话</th><th>邮箱</th><th>操作</th></tr></thead><tbody>` +
    state.contacts.map((c, idx) => `<tr>
      <td>${input(c.name || "", 'data-field="name"')}</td>
      <td>${input(c.phone || "", 'data-field="phone"')}</td>
      <td>${input(c.email || "", 'data-field="email"')}</td>
      <td><button class="danger linkish" data-remove-contact="${idx}">删除</button></td>
    </tr>`).join("") + `</tbody>`;
}

function collectContacts() {
  return [...$("contactsTable").querySelectorAll("tbody tr")].map((tr) => ({
    name: tr.querySelector('[data-field="name"]').value.trim(),
    phone: tr.querySelector('[data-field="phone"]').value.trim(),
    email: tr.querySelector('[data-field="email"]').value.trim(),
  })).filter((item) => item.name || item.phone || item.email);
}

async function saveContacts() {
  state.contacts = await api("/api/contacts", { method: "POST", body: JSON.stringify(collectContacts()) });
  renderContacts();
  toast("通讯录已保存");
}

function currentContacts() {
  const table = $("contactsTable");
  if (table && table.querySelector("tbody tr")) {
    const edited = collectContacts();
    if (edited.length) return edited;
  }
  return state.contacts || [];
}

function pickContacts(valueType = "email", single = false) {
  const valueKey = valueType === "phone" ? "phone" : "email";
  const contacts = currentContacts().filter((contact) => (contact[valueKey] || "").trim());
  if (!contacts.length) {
    toast(valueType === "phone" ? "通讯录中没有可导入的手机号" : "通讯录中没有可导入的邮箱");
    return Promise.resolve([]);
  }

  $("contactPickerTitle").textContent = valueType === "phone" ? "从通讯录导入手机号" : "从通讯录导入邮箱";
  $("contactPickerBody").innerHTML = contacts.map((contact, idx) => `
    <label class="picker-row">
      <input type="${single ? "radio" : "checkbox"}" name="contactPick" value="${idx}">
      <span><strong>${escapeHtml(contact.name || "未命名")}</strong><br>${escapeHtml(contact[valueKey] || "")}</span>
    </label>
  `).join("");

  return new Promise((resolve) => {
    const dialog = $("contactPickerDialog");
    const cleanup = () => {
      $("confirmContactPickerBtn").onclick = null;
      $("cancelContactPickerBtn").onclick = null;
      dialog.oncancel = null;
    };
    $("confirmContactPickerBtn").onclick = () => {
      const picked = [...$("contactPickerBody").querySelectorAll("input:checked")]
        .map((inputNode) => contacts[Number(inputNode.value)])
        .filter(Boolean)
        .map((contact) => ({
          name: contact.name || "",
          value: (contact[valueKey] || "").trim(),
        }));
      cleanup();
      dialog.close();
      resolve(single ? picked.slice(0, 1) : picked);
    };
    $("cancelContactPickerBtn").onclick = () => {
      cleanup();
      dialog.close();
      resolve([]);
    };
    dialog.oncancel = () => {
      cleanup();
      resolve([]);
    };
    dialog.showModal();
  });
}

function renderTasks() {
  $("tasksTable").innerHTML = `<thead><tr><th>任务名称</th><th>发送方式</th><th>收件人</th><th>发送时间</th><th>状态</th><th>操作</th></tr></thead><tbody>` +
    state.tasks.map((task, idx) => {
      const t = task.time_config || {};
      const timeText = t.type === "once" ? `一次性 ${t.date || ""} ${t.time || ""}` : (t.type === "weekly" ? `每周 ${(t.weekdays || []).join(", ")} ${t.time || ""}` : `每天 ${t.time || ""}`);
      const status = task.executed ? "已执行" : (task.enabled === false ? "已禁用" : "启用中");
      return `<tr>
        <td>${escapeHtml(task.name || "")}</td>
        <td>${task.send_type === "sms" ? "短信发送" : "邮件发送"}</td>
        <td>${escapeHtml((task.receivers || []).join(", "))}</td>
        <td>${escapeHtml(timeText)}</td>
        <td>${status}</td>
        <td class="row-actions">
          <button class="linkish" data-edit-task="${idx}">修改</button>
          <button class="linkish" data-toggle-task="${idx}">${task.enabled === false || task.executed ? "启用" : "禁用"}</button>
          <button class="linkish" data-run-task="${idx}">运行</button>
          <button class="danger linkish" data-delete-task="${idx}">删除</button>
        </td>
      </tr>`;
    }).join("") + `</tbody>`;
}

function openTaskDialog(index = null) {
  const task = index === null ? {} : state.tasks[index];
  $("taskDialogTitle").textContent = index === null ? "添加任务" : "修改任务";
  $("taskIndex").value = index === null ? "" : String(index);
  $("taskName").value = task.name || "";
  $("taskSendType").value = task.send_type || "email";
  $("taskSubject").value = task.subject || (task.name ? `自定义任务：${task.name}` : "");
  $("taskReceivers").value = (task.receivers || []).join("\n");
  const t = task.time_config || {};
  $("taskTimeType").value = t.type || "once";
  $("taskDate").value = t.date || today();
  $("taskTime").value = t.time || "09:00";
  $("taskContent").value = task.content || "";
  document.querySelectorAll("#taskWeekWrap input").forEach((box) => box.checked = (t.weekdays || []).includes(box.value));
  updateTaskVisibility();
  $("taskDialog").showModal();
}

function updateTaskVisibility() {
  const type = $("taskTimeType").value;
  $("taskDateWrap").style.display = type === "once" ? "grid" : "none";
  $("taskWeekWrap").style.display = type === "weekly" ? "grid" : "none";
  $("taskSubject").closest("label").style.display = $("taskSendType").value === "email" ? "grid" : "none";
}

async function saveTaskFromDialog(event) {
  event.preventDefault();
  const form = $("taskForm");
  if (!form.reportValidity()) return;
  try {
    const index = $("taskIndex").value;
    const timeType = $("taskTimeType").value;
    const time_config = { type: timeType, time: $("taskTime").value || "09:00" };
    if (timeType === "once") time_config.date = $("taskDate").value || today();
    if (timeType === "weekly") {
      time_config.weekdays = [...document.querySelectorAll("#taskWeekWrap input:checked")].map((box) => box.value);
      if (!time_config.weekdays.length) {
        toast("请至少选择一个星期");
        return;
      }
    }
    const task = {
      name: $("taskName").value.trim(),
      send_type: $("taskSendType").value,
      subject: $("taskSubject").value.trim(),
      receivers: $("taskReceivers").value.split(/\n|,|;/).map((item) => item.trim()).filter(Boolean),
      time_config,
      content: $("taskContent").value,
      enabled: true,
    };
    const method = index === "" ? "POST" : "PUT";
    const path = index === "" ? "/api/tasks" : `/api/tasks/${index}`;
    state.tasks = await api(path, { method, body: JSON.stringify(task) });
    $("taskDialog").close();
    renderTasks();
    toast("任务已保存");
  } catch (err) {
    toast(err.message);
  }
}

function bindCustomerSettings() {
  const s = state.customerSettings;
  $("customerApiKey").value = "";
  $("customerApiKey").placeholder = s.api_key_set ? "已保存，留空保持原 API Key" : "Volcengine Ark API Key";
  $("customerModel").value = s.model || "";
  $("customerApiUrl").value = s.api_url || "";
  $("birthdayEnabled").checked = !!s.birthday_enabled;
  $("birthdaySendTime").value = s.send_time || "09:00";
  $("birthdayTemplate").value = s.birthday_template || "";
  $("merchantPhone").value = s.merchant_phone || "";
  $("merchantTemplate").value = s.merchant_template || "";
  bindCustomerColumnSelects();
}

function bindCustomerColumnSelects() {
  const columns = state.customerData.columns || [];
  const options = columns.map((col) => `<option>${escapeHtml(col)}</option>`).join("");
  $("birthdayPhoneCol").innerHTML = options;
  $("birthdayDateCol").innerHTML = options;
  $("birthdayPhoneCol").value = state.customerSettings.phone_column || "";
  $("birthdayDateCol").value = state.customerSettings.birthday_column || "";
}

function renderCustomerTable() {
  const columns = state.customerData.columns || [];
  const rows = state.customerData.rows || [];
  $("customerTable").innerHTML = `<thead><tr>${columns.map((col, idx) => `<th>${input(col, `data-col-index="${idx}" class="customer-col-name"`)}<button class="danger linkish" data-delete-customer-col="${idx}">删列</button></th>`).join("")}<th>操作</th></tr></thead>` +
    `<tbody>${rows.map((row, rowIdx) => `<tr>${columns.map((col) => `<td>${input(row[col] || "", 'class="customer-cell"')}</td>`).join("")}<td><button class="danger linkish" data-delete-customer-row="${rowIdx}">删除</button></td></tr>`).join("")}</tbody>`;
  bindCustomerColumnSelects();
}

function collectCustomerData() {
  const columns = [...$("customerTable").querySelectorAll(".customer-col-name")].map((node) => node.value.trim()).filter(Boolean);
  const rows = [...$("customerTable").querySelectorAll("tbody tr")].map((tr) => {
    const row = {};
    [...tr.querySelectorAll(".customer-cell")].forEach((cell, idx) => {
      if (columns[idx]) row[columns[idx]] = cell.value.trim();
    });
    return row;
  });
  return { columns, rows };
}

async function saveCustomerData() {
  state.customerData = await api("/api/customer-data", { method: "POST", body: JSON.stringify(collectCustomerData()) });
  renderCustomerTable();
  toast("客户表已保存");
}

async function saveCustomerDataSilent() {
  state.customerData = await api("/api/customer-data", { method: "POST", body: JSON.stringify(collectCustomerData()) });
}

function scheduleCustomerDataAutoSave() {
  if (!state.ready || state.isBinding) return;
  clearTimeout(state.customerDataTimer);
  state.customerDataTimer = setTimeout(async () => {
    try {
      await saveCustomerDataSilent();
      toast("客户表已自动保存");
    } catch (err) {
      toast(`客户表自动保存失败：${err.message}`);
    }
  }, 1000);
}

async function saveCustomerSettings() {
  const settings = {
    model: $("customerModel").value.trim(),
    api_url: $("customerApiUrl").value.trim(),
    birthday_enabled: $("birthdayEnabled").checked,
    phone_column: $("birthdayPhoneCol").value,
    birthday_column: $("birthdayDateCol").value,
    send_time: $("birthdaySendTime").value || "09:00",
    birthday_template: $("birthdayTemplate").value,
    merchant_phone: $("merchantPhone").value.trim(),
    merchant_template: $("merchantTemplate").value,
  };
  if ($("customerApiKey").value.trim()) settings.api_key = $("customerApiKey").value.trim();
  state.customerSettings = await api("/api/customer-settings", { method: "POST", body: JSON.stringify(settings) });
  bindCustomerSettings();
  toast("客户设置已保存");
}

async function saveCustomerSettingsSilent() {
  const settings = {
    model: $("customerModel").value.trim(),
    api_url: $("customerApiUrl").value.trim(),
    birthday_enabled: $("birthdayEnabled").checked,
    phone_column: $("birthdayPhoneCol").value,
    birthday_column: $("birthdayDateCol").value,
    send_time: $("birthdaySendTime").value || "09:00",
    birthday_template: $("birthdayTemplate").value,
    merchant_phone: $("merchantPhone").value.trim(),
    merchant_template: $("merchantTemplate").value,
  };
  if ($("customerApiKey").value.trim()) settings.api_key = $("customerApiKey").value.trim();
  state.customerSettings = await api("/api/customer-settings", { method: "POST", body: JSON.stringify(settings) });
}

function scheduleCustomerSettingsAutoSave() {
  if (!state.ready || state.isBinding) return;
  clearTimeout(state.customerSettingsTimer);
  state.customerSettingsTimer = setTimeout(async () => {
    try {
      await saveCustomerSettingsSilent();
      toast("已自动保存");
    } catch (err) {
      toast(`客户设置自动保存失败：${err.message}`);
    }
  }, 1000);
}

async function recognizeIdentityFile(file) {
  if (!file) return;
  await saveCustomerDataSilent();
  await saveCustomerSettingsSilent();
  $("ocrResult").textContent = `正在识别：${file.name}`;
  const form = new FormData();
  form.append("file", file);
  const result = await api("/api/customer/identity-ocr", { method: "POST", body: form });
  $("ocrResult").textContent = `识别结果：姓名 ${result.filled.name || "-"}，身份证号 ${result.filled.id_no || "-"}，生日 ${result.filled.birthday || "-"}`;
  state.customerData = await api("/api/customer-data");
  renderCustomerTable();
  await refreshLogs();
}

function renderLogs(logs) {
  const lines = logs || [];
  const text = lines.length ? [`共 ${lines.length} 条日志`, ...lines].join("\n") : "暂无日志";
  if ($("logBox")) {
    $("logBox").textContent = text;
    $("logBox").scrollTop = $("logBox").scrollHeight;
  }
  if ($("customerLogBox")) {
    $("customerLogBox").textContent = text;
    $("customerLogBox").scrollTop = $("customerLogBox").scrollHeight;
  }
}

async function refreshLogs() {
  renderLogs(await api("/api/logs?limit=2000"));
}

function setupEvents() {
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      const system = tab.closest(".system-view");
      system.querySelectorAll(".tab").forEach((node) => node.classList.remove("active"));
      system.querySelectorAll(".tab-panel").forEach((node) => node.classList.remove("active"));
      tab.classList.add("active");
      $(tab.dataset.tab).classList.add("active");
      if (tab.dataset.tab === "logsTab" || tab.dataset.tab === "customerLogsTab") refreshLogs();
    });
  });

  $("systemTitle").addEventListener("click", () => {
    $("bondSystem").classList.toggle("active");
    $("customerSystem").classList.toggle("active");
    $("systemTitle").textContent = $("customerSystem").classList.contains("active") ? "客户管理系统" : "债券付息兑付智能提醒系统";
  });
  $("backBondBtn").addEventListener("click", () => $("systemTitle").click());
  $("sharedSettingsBtn").addEventListener("click", () => $("sharedSettingsDialog").showModal());
  $("closeSharedSettingsBtn").addEventListener("click", () => {
    $("sharedSettingsDialog").close();
  });
  $("refreshBtn").addEventListener("click", () => loadAll().then(() => toast("已刷新")).catch((err) => toast(err.message)));
  setupConfigAutoSave();
  $("sharedSettingsDialog").addEventListener("input", (event) => {
    if (["customerModel", "customerApiUrl"].includes(event.target.id)) {
      scheduleCustomerSettingsAutoSave();
    }
  });
  $("sharedSettingsDialog").addEventListener("change", (event) => {
    if (["customerApiKey", "customerModel", "customerApiUrl"].includes(event.target.id)) {
      scheduleCustomerSettingsAutoSave();
    }
  });
  $("customerBirthdayTab").addEventListener("input", () => scheduleCustomerSettingsAutoSave());
  $("customerBirthdayTab").addEventListener("change", () => scheduleCustomerSettingsAutoSave());

  $("bondFile").addEventListener("change", async () => {
    const file = $("bondFile").files[0];
    if (!file) return;
    const form = new FormData();
    form.append("file", file);
    form.append("header", $("headerRow").value || "0");
    state.preview = await api("/api/upload/bond-data", { method: "POST", body: form });
    state.config = await api("/api/config");
    bindConfig();
    renderPreview();
    renderColumns();
    $("bondFile").value = "";
    toast("债券数据已上传并缓存");
  });
  $("refreshPreviewBtn").addEventListener("click", async () => {
    state.preview = await api("/api/bond-preview");
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
  $("importWeeklyReceiversBtn").addEventListener("click", async () => {
    const picked = await pickContacts("email", false);
    if (!picked.length) return;
    state.config.receiver_list = state.config.receiver_list || [];
    for (const item of picked) {
      if (!state.config.receiver_list.some((receiver) => receiver.email === item.value)) {
        state.config.receiver_list.push({ email: item.value, remark: item.name || "通讯录" });
      }
    }
    renderReceivers();
    scheduleConfigAutoSave();
    toast("已从通讯录导入周报收件人");
  });
  $("importDailyReceiverBtn").addEventListener("click", async () => {
    const picked = await pickContacts("email", true);
    if (!picked.length) return;
    $("dailyEmailReceiver").value = picked[0].value;
    scheduleConfigAutoSave();
    toast("已填入短信中转邮箱");
  });
  $("receiversTable").addEventListener("click", (event) => {
    const idx = event.target.dataset.removeReceiver;
    if (idx !== undefined) {
      state.config.receiver_list.splice(Number(idx), 1);
      renderReceivers();
      scheduleConfigAutoSave();
    }
  });

  $("addContactBtn").addEventListener("click", () => {
    state.contacts.push({ name: "", phone: "", email: "" });
    renderContacts();
  });
  $("saveContactsBtn").addEventListener("click", () => saveContacts().catch((err) => toast(err.message)));
  $("contactsTable").addEventListener("click", (event) => {
    const idx = event.target.dataset.removeContact;
    if (idx !== undefined) {
      state.contacts.splice(Number(idx), 1);
      renderContacts();
    }
  });

  $("addTaskBtn").addEventListener("click", () => openTaskDialog());
  $("taskTimeType").addEventListener("change", updateTaskVisibility);
  $("taskSendType").addEventListener("change", updateTaskVisibility);
  $("importTaskReceiversBtn").addEventListener("click", async () => {
    const valueType = $("taskSendType").value === "sms" ? "phone" : "email";
    const picked = await pickContacts(valueType, false);
    if (!picked.length) return;
    const existing = new Set($("taskReceivers").value.split(/\n|,|;/).map((item) => item.trim()).filter(Boolean));
    for (const item of picked) existing.add(item.value);
    $("taskReceivers").value = [...existing].join("\n");
    toast("已从通讯录导入任务收件人");
  });
  $("cancelTaskBtn").addEventListener("click", () => $("taskDialog").close());
  $("saveTaskBtn").addEventListener("click", saveTaskFromDialog);
  $("tasksTable").addEventListener("click", async (event) => {
    const edit = event.target.dataset.editTask;
    const del = event.target.dataset.deleteTask;
    const toggle = event.target.dataset.toggleTask;
    const run = event.target.dataset.runTask;
    if (edit !== undefined) openTaskDialog(Number(edit));
    if (del !== undefined && confirm("确定删除该任务吗？")) {
      state.tasks = await api(`/api/tasks/${del}`, { method: "DELETE" });
      renderTasks();
    }
    if (toggle !== undefined) {
      state.tasks = await api(`/api/tasks/${toggle}/toggle`, { method: "POST" });
      renderTasks();
    }
    if (run !== undefined) {
      await api(`/api/tasks/${run}/run`, { method: "POST" });
      await refreshLogs();
      toast("任务已触发");
    }
  });

  $("runManualBtn").addEventListener("click", async () => {
    await saveConfig();
    await api("/api/run/manual", { method: "POST" });
    await refreshLogs();
  });
  $("runWeeklyBtn").addEventListener("click", async () => {
    await saveConfig();
    await api("/api/run/weekly", { method: "POST" });
    await refreshLogs();
  });
  $("runDailyBtn").addEventListener("click", async () => {
    await saveConfig();
    await api("/api/run/daily", { method: "POST" });
    await refreshLogs();
  });
  $("clearLogsBtn").addEventListener("click", async () => {
    await api("/api/logs", { method: "DELETE" });
    await refreshLogs();
  });
  $("refreshCustomerLogsBtn").addEventListener("click", refreshLogs);
  $("clearCustomerLogsBtn").addEventListener("click", async () => {
    await api("/api/logs", { method: "DELETE" });
    await refreshLogs();
  });

  $("customerFile").addEventListener("change", async () => {
    const file = $("customerFile").files[0];
    if (!file) return;
    const form = new FormData();
    form.append("file", file);
    state.customerData = await api("/api/upload/customer-data", { method: "POST", body: form });
    renderCustomerTable();
    toast("客户表已导入");
  });
  $("addCustomerColumnBtn").addEventListener("click", async () => {
    const name = prompt("列名：");
    if (!name) return;
    state.customerData = collectCustomerData();
    if (state.customerData.columns.includes(name)) return toast("列名已存在");
    state.customerData.columns.push(name);
    state.customerData.rows.forEach((row) => row[name] = "");
    renderCustomerTable();
    try {
      await saveCustomerDataSilent();
      toast("已自动保存");
    } catch (err) {
      toast(`客户表自动保存失败：${err.message}`);
    }
  });
  $("addCustomerRowBtn").addEventListener("click", async () => {
    state.customerData = collectCustomerData();
    const row = {};
    state.customerData.columns.forEach((col) => row[col] = "");
    state.customerData.rows.push(row);
    renderCustomerTable();
    try {
      await saveCustomerDataSilent();
      toast("已自动保存");
    } catch (err) {
      toast(`客户表自动保存失败：${err.message}`);
    }
  });
  $("customerTable").addEventListener("click", async (event) => {
    const rowIdx = event.target.dataset.deleteCustomerRow;
    const colIdx = event.target.dataset.deleteCustomerCol;
    let changed = false;
    if (rowIdx !== undefined) {
      state.customerData = collectCustomerData();
      state.customerData.rows.splice(Number(rowIdx), 1);
      renderCustomerTable();
      changed = true;
    }
    if (colIdx !== undefined) {
      state.customerData = collectCustomerData();
      const col = state.customerData.columns.splice(Number(colIdx), 1)[0];
      state.customerData.rows.forEach((row) => delete row[col]);
      renderCustomerTable();
      changed = true;
    }
    if (changed) {
      try {
        await saveCustomerDataSilent();
        toast("已自动保存");
      } catch (err) {
        toast(`客户表自动保存失败：${err.message}`);
      }
    }
  });
  $("customerTable").addEventListener("input", (event) => {
    if (event.target.classList.contains("customer-cell") || event.target.classList.contains("customer-col-name")) {
      scheduleCustomerDataAutoSave();
    }
  });
  $("identityDropArea").addEventListener("click", () => $("identityFile").click());
  $("identityDropArea").addEventListener("dragover", (event) => {
    event.preventDefault();
    $("identityDropArea").classList.add("drag-over");
  });
  $("identityDropArea").addEventListener("dragleave", () => $("identityDropArea").classList.remove("drag-over"));
  $("identityDropArea").addEventListener("drop", async (event) => {
    event.preventDefault();
    $("identityDropArea").classList.remove("drag-over");
    try {
      await recognizeIdentityFile(event.dataTransfer.files[0]);
    } catch (err) {
      toast(err.message);
      $("ocrResult").textContent = `识别失败：${err.message}`;
    }
  });
  $("identityFile").addEventListener("change", async () => {
    try {
      await recognizeIdentityFile($("identityFile").files[0]);
      $("identityFile").value = "";
    } catch (err) {
      toast(err.message);
      $("ocrResult").textContent = `识别失败：${err.message}`;
    }
  });
  $("runBirthdayBtn").addEventListener("click", async () => {
    await saveCustomerSettings();
    const result = await api("/api/customer/birthday-check", { method: "POST" });
    toast(`生日提醒处理完成：客户 ${result.customer_count} 条，订单 ${result.merchant_count} 条`);
    await refreshLogs();
  });
}

setupEvents();
loadAll().catch((err) => toast(err.message));
setInterval(() => {
  if ($("logsTab").classList.contains("active") || $("customerLogsTab").classList.contains("active")) {
    refreshLogs().catch(() => {});
  }
}, 5000);
