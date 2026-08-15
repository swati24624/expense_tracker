/* app.js — glues the views, forms and API together */

const state = {
  month: new Date().getMonth() + 1,
  year: new Date().getFullYear(),
  categories: [],
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatMoney(value, short = false) {
  const n = Number(value) || 0;
  if (short && Math.abs(n) >= 1000) {
    return "₹" + (n / 1000).toFixed(1) + "k";
  }
  return "₹" + n.toLocaleString("en-IN", { maximumFractionDigits: 0 });
}

function showToast(message, isError = false) {
  const toast = document.getElementById("toast");
  toast.textContent = message;
  toast.style.background = isError ? "#A8453B" : "#16302B";
  toast.classList.add("show");
  clearTimeout(showToast._t);
  showToast._t = setTimeout(() => toast.classList.remove("show"), 2600);
}

function todayISO() {
  return new Date().toISOString().slice(0, 10);
}

// ---------------------------------------------------------------------------
// Navigation
// ---------------------------------------------------------------------------

function initNav() {
  document.querySelectorAll(".nav-item").forEach(btn => {
    btn.addEventListener("click", () => switchView(btn.dataset.view));
  });
  document.querySelectorAll("[data-goto]").forEach(btn => {
    btn.addEventListener("click", () => switchView(btn.dataset.goto));
  });
}

function switchView(view) {
  document.querySelectorAll(".nav-item").forEach(b => b.classList.toggle("active", b.dataset.view === view));
  document.querySelectorAll(".view").forEach(v => v.classList.toggle("active", v.id === `view-${view}`));
  loadView(view);
}

function loadView(view) {
  if (view === "dashboard") loadDashboard();
  else if (view === "transactions") loadTransactionsView();
  else if (view === "analytics") loadAnalyticsView();
  else if (view === "budget") loadBudgetView();
  else if (view === "calendar") loadCalendarView();
  else if (view === "insights") loadInsightsView();
}

// ---------------------------------------------------------------------------
// Month / year selectors
// ---------------------------------------------------------------------------

function initMonthYearSelectors() {
  const monthSel = document.getElementById("global-month");
  const monthNames = ["January","February","March","April","May","June","July","August","September","October","November","December"];
  monthNames.forEach((name, i) => {
    const opt = document.createElement("option");
    opt.value = i + 1;
    opt.textContent = name;
    monthSel.appendChild(opt);
  });
  monthSel.value = state.month;

  const yearSel = document.getElementById("global-year");
  const thisYear = new Date().getFullYear();
  for (let y = thisYear - 3; y <= thisYear + 1; y++) {
    const opt = document.createElement("option");
    opt.value = y;
    opt.textContent = y;
    yearSel.appendChild(opt);
  }
  yearSel.value = state.year;

  monthSel.addEventListener("change", () => { state.month = Number(monthSel.value); refreshActiveView(); });
  yearSel.addEventListener("change", () => { state.year = Number(yearSel.value); refreshActiveView(); });
}

function refreshActiveView() {
  const active = document.querySelector(".view.active");
  if (active) loadView(active.id.replace("view-", ""));
  loadSidebarScore();
}

// ---------------------------------------------------------------------------
// Categories (shared dropdowns)
// ---------------------------------------------------------------------------

async function loadCategories() {
  state.categories = await API.listCategories();
  const txnSelect = document.getElementById("txn-category");
  const filterSelect = document.getElementById("filter-category");
  const budgetSelect = document.getElementById("budget-category");

  txnSelect.innerHTML = "";
  filterSelect.innerHTML = '<option value="">All categories</option>';
  budgetSelect.innerHTML = '<option value="">Overall (all categories)</option>';

  state.categories.forEach(c => {
    const opt1 = document.createElement("option");
    opt1.value = c.name; opt1.textContent = `${c.name} (${c.type})`;
    txnSelect.appendChild(opt1);

    const opt2 = document.createElement("option");
    opt2.value = c.name; opt2.textContent = c.name;
    filterSelect.appendChild(opt2);

    if (c.type === "expense") {
      const opt3 = document.createElement("option");
      opt3.value = c.name; opt3.textContent = c.name;
      budgetSelect.appendChild(opt3);
    }
  });
}

// ---------------------------------------------------------------------------
// Quick add (NLP)
// ---------------------------------------------------------------------------

function initQuickAdd() {
  const form = document.getElementById("quick-add-form");
  const input = document.getElementById("quick-add-input");
  const preview = document.getElementById("quick-add-preview");

  input.addEventListener("input", async () => {
    const text = input.value.trim();
    if (!text) { preview.textContent = ""; return; }
    try {
      const parsed = await API.nlpEntry(text, false);
      const verb = parsed.type === "income" ? "Income" : "Expense";
      preview.innerHTML = `<span class="ok">${verb} · ₹${parsed.amount} · ${parsed.category} · ${parsed.date}</span> — press Enter to add`;
    } catch (e) {
      preview.innerHTML = `<span class="err">${e.message}</span>`;
    }
  });

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const text = input.value.trim();
    if (!text) return;
    try {
      await API.nlpEntry(text, true);
      input.value = "";
      preview.textContent = "";
      showToast("Entry added");
      refreshActiveView();
    } catch (err) {
      showToast(err.message, true);
    }
  });
}

// ---------------------------------------------------------------------------
// Dashboard
// ---------------------------------------------------------------------------

async function loadDashboard() {
  const [summary, trend, breakdown, txns] = await Promise.all([
    API.dashboard(state.month, state.year),
    API.trends(6),
    API.categoryBreakdown(state.month, state.year, "expense"),
    API.listTransactions(),
  ]);

  document.getElementById("stat-income").textContent = formatMoney(summary.income);
  document.getElementById("stat-expense").textContent = formatMoney(summary.expense);
  document.getElementById("stat-balance").textContent = formatMoney(summary.balance);
  document.getElementById("stat-savings").textContent = summary.savings_rate + "%";

  renderTrendChart("chart-trend", "dashTrend", trend);
  if (breakdown.length) {
    renderDonutChart("chart-category-donut", "dashDonut", breakdown);
  }

  const recentBox = document.getElementById("recent-transactions");
  recentBox.innerHTML = "";
  txns.slice(0, 6).forEach(t => recentBox.appendChild(txnRowEl(t)));
  if (!txns.length) recentBox.innerHTML = '<p class="empty-note">No entries yet — add one above to get started.</p>';

  loadSidebarScore();
}

function txnRowEl(t) {
  const row = document.createElement("div");
  row.className = "txn-row";
  row.innerHTML = `
    <div class="txn-main">
      <span class="txn-cat">${t.category}</span>
      <span class="txn-desc">${t.description || "—"}</span>
    </div>
    <div style="text-align:right">
      <div class="txn-amount ${t.type}">${t.type === "income" ? "+" : "-"}${formatMoney(t.amount)}</div>
      <div class="txn-date">${t.date}</div>
    </div>`;
  return row;
}

async function loadSidebarScore() {
  const s = await API.score(state.month, state.year);
  document.getElementById("sidebar-score-value").textContent = s.score;
}

// ---------------------------------------------------------------------------
// Transactions view
// ---------------------------------------------------------------------------

function initTransactionForm() {
  const form = document.getElementById("txn-form");
  const cancelBtn = document.getElementById("txn-cancel-btn");
  document.getElementById("txn-date").value = todayISO();

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const id = document.getElementById("txn-id").value;
    const payload = {
      type: document.getElementById("txn-type").value,
      amount: document.getElementById("txn-amount").value,
      category: document.getElementById("txn-category").value,
      description: document.getElementById("txn-description").value,
      date: document.getElementById("txn-date").value,
    };
    try {
      if (id) {
        await API.updateTransaction(id, payload);
        showToast("Entry updated");
      } else {
        await API.createTransaction(payload);
        showToast("Entry added");
      }
      resetTxnForm();
      loadTransactionsView();
    } catch (err) {
      showToast(err.message, true);
    }
  });

  cancelBtn.addEventListener("click", resetTxnForm);

  document.getElementById("filter-search").addEventListener("input", debounce(loadTransactionsTable, 300));
  document.getElementById("filter-type").addEventListener("change", loadTransactionsTable);
  document.getElementById("filter-category").addEventListener("change", loadTransactionsTable);
}

function resetTxnForm() {
  document.getElementById("txn-id").value = "";
  document.getElementById("txn-form").reset();
  document.getElementById("txn-date").value = todayISO();
  document.getElementById("txn-submit-btn").textContent = "Add entry";
  document.getElementById("txn-cancel-btn").style.display = "none";
}

function editTransaction(t) {
  document.getElementById("txn-id").value = t.id;
  document.getElementById("txn-type").value = t.type;
  document.getElementById("txn-amount").value = t.amount;
  document.getElementById("txn-category").value = t.category;
  document.getElementById("txn-description").value = t.description;
  document.getElementById("txn-date").value = t.date;
  document.getElementById("txn-submit-btn").textContent = "Save changes";
  document.getElementById("txn-cancel-btn").style.display = "inline-flex";
  window.scrollTo({ top: 0, behavior: "smooth" });
}

async function deleteTransactionConfirm(id) {
  if (!confirm("Delete this entry?")) return;
  await API.deleteTransaction(id);
  showToast("Entry deleted");
  loadTransactionsView();
}

function loadTransactionsView() {
  resetTxnForm();
  loadTransactionsTable();
}

async function loadTransactionsTable() {
  const params = {};
  const search = document.getElementById("filter-search").value.trim();
  const type = document.getElementById("filter-type").value;
  const category = document.getElementById("filter-category").value;
  if (search) params.search = search;
  if (type) params.type = type;
  if (category) params.category = category;

  const txns = await API.listTransactions(params);
  const body = document.getElementById("txn-table-body");
  body.innerHTML = "";

  if (!txns.length) {
    body.innerHTML = `<tr><td colspan="5" class="empty-note">No transactions match.</td></tr>`;
    return;
  }

  txns.forEach(t => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${t.date}</td>
      <td>${t.category}</td>
      <td>${t.description || "—"}</td>
      <td class="right amount ${t.type}">${t.type === "income" ? "+" : "-"}${formatMoney(t.amount)}</td>
      <td class="right">
        <div class="row-actions">
          <button class="icon-btn" data-edit="${t.id}">Edit</button>
          <button class="icon-btn" data-del="${t.id}">Delete</button>
        </div>
      </td>`;
    body.appendChild(tr);
  });

  body.querySelectorAll("[data-edit]").forEach(btn => {
    btn.addEventListener("click", () => {
      const t = txns.find(x => x.id == btn.dataset.edit);
      editTransaction(t);
    });
  });
  body.querySelectorAll("[data-del]").forEach(btn => {
    btn.addEventListener("click", () => deleteTransactionConfirm(btn.dataset.del));
  });
}

function debounce(fn, ms) {
  let t;
  return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), ms); };
}

// ---------------------------------------------------------------------------
// Analytics view
// ---------------------------------------------------------------------------

async function loadAnalyticsView() {
  const [trend, breakdown, fc, anomalyList, recurringList] = await Promise.all([
    API.trends(6),
    API.categoryBreakdown(state.month, state.year, "expense"),
    API.forecast(),
    API.anomalies(3),
    API.recurring(),
  ]);

  renderTrendChart("chart-trend-2", "analyticsTrend", trend);
  if (breakdown.length) renderBarChart("chart-category-bar", "analyticsBar", breakdown);

  document.getElementById("fc-income").textContent = formatMoney(fc.predicted_next_month_income);
  document.getElementById("fc-expense").textContent = formatMoney(fc.predicted_next_month_expense);
  document.getElementById("fc-balance").textContent = formatMoney(fc.predicted_next_month_balance);

  const anomalyBox = document.getElementById("anomaly-list");
  anomalyBox.innerHTML = "";
  if (!anomalyList.length) {
    anomalyBox.innerHTML = '<p class="empty-note">Nothing unusual in the last 3 months.</p>';
  } else {
    anomalyList.slice(0, 6).forEach(a => {
      const div = document.createElement("div");
      div.className = "list-item warning";
      div.textContent = `${a.category}: ₹${a.amount.toLocaleString("en-IN")} on ${a.date} (usually ~₹${a.typical_amount.toLocaleString("en-IN")})`;
      anomalyBox.appendChild(div);
    });
  }

  const recurringBox = document.getElementById("recurring-list");
  recurringBox.innerHTML = "";
  if (!recurringList.length) {
    recurringBox.innerHTML = '<p class="empty-note">No recurring pattern detected yet — needs a few months of similar entries.</p>';
  } else {
    recurringList.forEach(r => {
      const div = document.createElement("div");
      div.className = "list-item info";
      div.textContent = `${r.category}: ~₹${r.amount.toLocaleString("en-IN")} roughly every ${r.avg_interval_days} days — next expected ${r.next_expected}`;
      recurringBox.appendChild(div);
    });
  }
}

// ---------------------------------------------------------------------------
// Budget view
// ---------------------------------------------------------------------------

function initBudgetForm() {
  document.getElementById("budget-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const category = document.getElementById("budget-category").value || null;
    const amount = document.getElementById("budget-amount").value;
    try {
      await API.setBudget({ category, amount, month: state.month, year: state.year });
      showToast("Budget saved");
      document.getElementById("budget-form").reset();
      loadBudgetView();
    } catch (err) {
      showToast(err.message, true);
    }
  });
}

async function loadBudgetView() {
  const statuses = await API.budgetStatus(state.month, state.year);
  const box = document.getElementById("budget-status-list");
  box.innerHTML = "";

  if (!statuses.length) {
    box.innerHTML = '<p class="empty-note">No budgets set for this month yet.</p>';
    return;
  }

  statuses.forEach(s => {
    const pct = Math.min(100, s.percent_used);
    const div = document.createElement("div");
    div.className = "budget-item";
    div.innerHTML = `
      <div class="budget-item-head">
        <span class="cat">${s.category}</span>
        <span class="budget-item-figures">${formatMoney(s.spent)} / ${formatMoney(s.budget)}</span>
      </div>
      <div class="bar-track"><div class="bar-fill ${s.over_budget ? "over" : ""}" style="width:${pct}%"></div></div>
    `;
    box.appendChild(div);
  });
}

// ---------------------------------------------------------------------------
// Calendar view
// ---------------------------------------------------------------------------

async function loadCalendarView() {
  const data = await API.calendarData(state.month, state.year);
  renderCalendar(state.month, state.year, data);
}

// ---------------------------------------------------------------------------
// Insights view
// ---------------------------------------------------------------------------

async function loadInsightsView() {
  const [ins, al, sc] = await Promise.all([
    API.insights(state.month, state.year),
    API.alerts(state.month, state.year),
    API.score(state.month, state.year),
  ]);

  const insightsBox = document.getElementById("insights-list");
  insightsBox.innerHTML = "";
  ins.forEach(text => {
    const div = document.createElement("div");
    div.className = "list-item";
    div.textContent = text;
    insightsBox.appendChild(div);
  });

  const alertsBox = document.getElementById("alerts-list");
  alertsBox.innerHTML = "";
  if (!al.length) {
    alertsBox.innerHTML = '<p class="empty-note">No alerts right now.</p>';
  } else {
    al.forEach(a => {
      const div = document.createElement("div");
      div.className = `list-item ${a.level}`;
      div.textContent = a.message;
      alertsBox.appendChild(div);
    });
  }

  document.getElementById("score-number").textContent = sc.score;
  const ring = document.getElementById("score-ring");
  const hue = sc.score >= 70 ? "#B8901E" : sc.score >= 40 ? "#C97B4A" : "#A8453B";
  ring.style.borderColor = hue + "33";
  ring.style.color = hue;
}

// ---------------------------------------------------------------------------
// Import / export
// ---------------------------------------------------------------------------

function initImport() {
  document.getElementById("import-btn").addEventListener("click", async () => {
    const fileInput = document.getElementById("import-file");
    const resultEl = document.getElementById("import-result");
    if (!fileInput.files.length) {
      resultEl.textContent = "Choose a CSV file first.";
      return;
    }
    resultEl.textContent = "Importing…";
    try {
      const result = await API.importCsv(fileInput.files[0]);
      resultEl.textContent = `Imported ${result.inserted} entries${result.skipped ? `, skipped ${result.skipped}` : ""}.`;
      showToast("Import complete");
    } catch (err) {
      resultEl.textContent = "Import failed. Check the file format.";
    }
  });
}

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------

document.addEventListener("DOMContentLoaded", async () => {
  initNav();
  initMonthYearSelectors();
  initQuickAdd();
  initTransactionForm();
  initBudgetForm();
  initImport();

  await loadCategories();
  await loadDashboard();
});
