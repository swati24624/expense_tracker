/* calendar.js — renders the month grid for the Calendar view */

function renderCalendar(month, year, dayData) {
  const grid = document.getElementById("calendar-grid");
  grid.innerHTML = "";

  const firstDay = new Date(year, month - 1, 1);
  const startWeekday = firstDay.getDay();
  const daysInMonth = new Date(year, month, 0).getDate();

  for (let i = 0; i < startWeekday; i++) {
    const empty = document.createElement("div");
    empty.className = "cal-cell empty";
    grid.appendChild(empty);
  }

  for (let day = 1; day <= daysInMonth; day++) {
    const dateStr = `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
    const cell = document.createElement("div");
    cell.className = "cal-cell";

    const num = document.createElement("span");
    num.className = "cal-day-num";
    num.textContent = day;
    cell.appendChild(num);

    const data = dayData[dateStr];
    if (data) {
      if (data.income) {
        const inc = document.createElement("span");
        inc.className = "cal-amt income";
        inc.textContent = "+" + formatMoney(data.income, true);
        cell.appendChild(inc);
      }
      if (data.expense) {
        const exp = document.createElement("span");
        exp.className = "cal-amt expense";
        exp.textContent = "-" + formatMoney(data.expense, true);
        cell.appendChild(exp);
      }
    }
    grid.appendChild(cell);
  }
}
