/* api.js — thin wrapper around fetch() for every backend endpoint */

const API = {
  base: "/api",

  async _req(path, options = {}) {
    const res = await fetch(this.base + path, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.error || `Request failed (${res.status})`);
    }
    return res.json();
  },

  // Transactions
  listTransactions(params = {}) {
    const qs = new URLSearchParams(params).toString();
    return this._req(`/transactions${qs ? "?" + qs : ""}`);
  },
  createTransaction(data) {
    return this._req("/transactions", { method: "POST", body: JSON.stringify(data) });
  },
  updateTransaction(id, data) {
    return this._req(`/transactions/${id}`, { method: "PUT", body: JSON.stringify(data) });
  },
  deleteTransaction(id) {
    return this._req(`/transactions/${id}`, { method: "DELETE" });
  },

  // Categories
  listCategories() {
    return this._req("/categories");
  },

  // NLP
  nlpEntry(text, save = false) {
    return this._req("/nlp-entry", { method: "POST", body: JSON.stringify({ text, save }) });
  },

  // Dashboard / analytics
  dashboard(month, year) {
    return this._req(`/dashboard?month=${month}&year=${year}`);
  },
  trends(months = 6) {
    return this._req(`/analytics/trends?months=${months}`);
  },
  categoryBreakdown(month, year, type = "expense") {
    return this._req(`/analytics/category-breakdown?month=${month}&year=${year}&type=${type}`);
  },
  calendarData(month, year) {
    return this._req(`/analytics/calendar?month=${month}&year=${year}`);
  },

  // Budgets
  listBudgets(month, year) {
    return this._req(`/budgets?month=${month}&year=${year}`);
  },
  setBudget(data) {
    return this._req("/budgets", { method: "POST", body: JSON.stringify(data) });
  },
  deleteBudget(id) {
    return this._req(`/budgets/${id}`, { method: "DELETE" });
  },
  budgetStatus(month, year) {
    return this._req(`/budgets/status?month=${month}&year=${year}`);
  },

  // Predictions
  forecast() {
    return this._req("/predictions/forecast");
  },
  anomalies(months = 3) {
    return this._req(`/predictions/anomalies?months=${months}`);
  },
  recurring() {
    return this._req("/predictions/recurring");
  },

  // Insights / score / alerts
  insights(month, year) {
    return this._req(`/insights?month=${month}&year=${year}`);
  },
  score(month, year) {
    return this._req(`/score?month=${month}&year=${year}`);
  },
  alerts(month, year) {
    return this._req(`/alerts?month=${month}&year=${year}`);
  },

  // Import
  async importCsv(file) {
    const formData = new FormData();
    formData.append("file", file);
    const res = await fetch(this.base + "/import", { method: "POST", body: formData });
    if (!res.ok) throw new Error("Import failed");
    return res.json();
  },
};
