/* charts.js — Pure SVG charts
   No Chart.js, no CDN, no external libraries.
*/

const CHART_COLORS = {
  gold: "#B8901E",
  brick: "#A8453B",
  ink: "#16302B",
  sage: "#7C8B7F",
  line: "#E1E3D6",
  palette: [
    "#B8901E",
    "#A8453B",
    "#3C6E8F",
    "#6E8B5C",
    "#8B6E9E",
    "#C97B4A",
    "#4A8B7C",
    "#9E6E6E"
  ]
};

const chartInstances = {};

/* -----------------------------
   Helpers
----------------------------- */

function destroyIfExists(key) {
  const oldChart = chartInstances[key];

  if (oldChart) {
    if (oldChart.parentNode) {
      oldChart.parentNode.innerHTML = "";
    }

    delete chartInstances[key];
  }
}

function getContainer(canvasId) {
  const element = document.getElementById(canvasId);

  if (!element) {
    console.warn(`Chart container "${canvasId}" not found.`);
    return null;
  }

  /*
    If the old HTML still contains a <canvas>,
    replace it with a normal div.
  */
  let container = element;

  if (element.tagName.toLowerCase() === "canvas") {
    container = document.createElement("div");
    container.id = canvasId;
    container.style.width = "100%";
    container.style.height = "100%";

    element.replaceWith(container);
  }

  return container;
}

function createSVG(width = 700, height = 320) {
  const svg = document.createElementNS(
    "http://www.w3.org/2000/svg",
    "svg"
  );

  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  svg.setAttribute("width", "100%");
  svg.setAttribute("height", "100%");
  svg.setAttribute("preserveAspectRatio", "xMidYMid meet");

  return svg;
}

function createSVGElement(tag, attributes = {}) {
  const element = document.createElementNS(
    "http://www.w3.org/2000/svg",
    tag
  );

  Object.entries(attributes).forEach(([key, value]) => {
    element.setAttribute(key, value);
  });

  return element;
}

function formatCurrency(value) {
  return "₹" + Number(value || 0).toLocaleString("en-IN");
}

function niceMax(value) {
  if (!value || value <= 0) return 100;

  const magnitude = Math.pow(10, Math.floor(Math.log10(value)));
  const normalized = value / magnitude;

  let nice;

  if (normalized <= 1) nice = 1;
  else if (normalized <= 2) nice = 2;
  else if (normalized <= 5) nice = 5;
  else nice = 10;

  return nice * magnitude;
}

function addText(svg, x, y, text, options = {}) {
  const element = createSVGElement("text", {
    x,
    y,
    fill: options.color || CHART_COLORS.sage,
    "font-size": options.size || 12,
    "font-family": "Inter, sans-serif",
    "font-weight": options.weight || "400",
    "text-anchor": options.anchor || "start"
  });

  element.textContent = text;
  svg.appendChild(element);

  return element;
}


/* -----------------------------
   LINE CHART
----------------------------- */

function renderTrendChart(containerId, key, trendData) {
  destroyIfExists(key);

  const container = getContainer(containerId);
  if (!container) return;

  container.innerHTML = "";

  if (!trendData || trendData.length === 0) {
    container.innerHTML = `
      <div style="
        height:100%;
        display:flex;
        align-items:center;
        justify-content:center;
        color:${CHART_COLORS.sage};
        font-family:Inter,sans-serif;
      ">
        No trend data available
      </div>
    `;

    chartInstances[key] = container;
    return;
  }

  const width = 700;
  const height = 330;

  const margin = {
    top: 25,
    right: 25,
    bottom: 55,
    left: 65
  };

  const chartWidth = width - margin.left - margin.right;
  const chartHeight = height - margin.top - margin.bottom;

  const svg = createSVG(width, height);

  /* -----------------------------
     Data
  ----------------------------- */

  const income = trendData.map(d => Number(d.income) || 0);
  const expense = trendData.map(d => Number(d.expense) || 0);

  const maxValue = niceMax(
    Math.max(...income, ...expense)
  );

  /* -----------------------------
     Grid + Y Axis
  ----------------------------- */

  const gridSteps = 5;

  for (let i = 0; i <= gridSteps; i++) {
    const value = (maxValue / gridSteps) * i;

    const y =
      margin.top +
      chartHeight -
      (value / maxValue) * chartHeight;

    const line = createSVGElement("line", {
      x1: margin.left,
      y1: y,
      x2: width - margin.right,
      y2: y,
      stroke: CHART_COLORS.line,
      "stroke-width": 1
    });

    svg.appendChild(line);

    addText(
      svg,
      margin.left - 10,
      y + 4,
      formatCurrency(value),
      {
        size: 10,
        anchor: "end"
      }
    );
  }

  /* -----------------------------
     X Axis Labels
  ----------------------------- */

  trendData.forEach((item, index) => {
    const x =
      margin.left +
      (index / Math.max(trendData.length - 1, 1)) *
        chartWidth;

    addText(
      svg,
      x,
      height - 20,
      item.label,
      {
        size: 10,
        anchor: "middle"
      }
    );
  });

  /* -----------------------------
     Convert values to points
  ----------------------------- */

  function getPoint(value, index) {
    const x =
      margin.left +
      (index / Math.max(trendData.length - 1, 1)) *
        chartWidth;

    const y =
      margin.top +
      chartHeight -
      (value / maxValue) * chartHeight;

    return { x, y };
  }

  function createLine(values, color) {
    const points = values.map((value, index) =>
      getPoint(value, index)
    );

    const pathData = points
      .map((point, index) =>
        `${index === 0 ? "M" : "L"} ${point.x} ${point.y}`
      )
      .join(" ");

    const path = createSVGElement("path", {
      d: pathData,
      fill: "none",
      stroke: color,
      "stroke-width": 3,
      "stroke-linecap": "round",
      "stroke-linejoin": "round"
    });

    svg.appendChild(path);

    /* Points */

    points.forEach(point => {
      const circle = createSVGElement("circle", {
        cx: point.x,
        cy: point.y,
        r: 4,
        fill: "#fff",
        stroke: color,
        "stroke-width": 2
      });

      svg.appendChild(circle);
    });
  }

  createLine(income, CHART_COLORS.gold);
  createLine(expense, CHART_COLORS.brick);

  /* -----------------------------
     Legend
  ----------------------------- */

  function legendItem(x, color, label) {
    const circle = createSVGElement("circle", {
      cx: x,
      cy: height - 3,
      r: 5,
      fill: color
    });

    svg.appendChild(circle);

    addText(
      svg,
      x + 10,
      height + 1,
      label,
      {
        size: 11,
        color: CHART_COLORS.sage
      }
    );
  }

  legendItem(285, CHART_COLORS.gold, "Income");
  legendItem(380, CHART_COLORS.brick, "Expense");

  container.appendChild(svg);

  chartInstances[key] = container;
}


/* -----------------------------
   DONUT CHART
----------------------------- */

function renderDonutChart(containerId, key, categoryData) {
  destroyIfExists(key);

  const container = getContainer(containerId);
  if (!container) return;

  container.innerHTML = "";

  if (!categoryData || categoryData.length === 0) {
    container.innerHTML = `
      <div style="
        height:100%;
        display:flex;
        align-items:center;
        justify-content:center;
        color:${CHART_COLORS.sage};
        font-family:Inter,sans-serif;
      ">
        No category data available
      </div>
    `;

    chartInstances[key] = container;
    return;
  }

  const width = 700;
  const height = 330;

  const svg = createSVG(width, height);

  const cx = 220;
  const cy = 155;
  const radius = 105;
  const innerRadius = 65;

  const values = categoryData.map(d =>
    Number(d.total) || 0
  );

  const total = values.reduce(
    (sum, value) => sum + value,
    0
  );

  if (total === 0) {
    addText(
      svg,
      cx,
      cy,
      "No spending",
      {
        size: 14,
        anchor: "middle",
        color: CHART_COLORS.sage
      }
    );

    container.appendChild(svg);
    chartInstances[key] = container;
    return;
  }

  let currentAngle = -Math.PI / 2;

  categoryData.forEach((item, index) => {
    const value = values[index];

    const sliceAngle =
      (value / total) * Math.PI * 2;

    const startAngle = currentAngle;
    const endAngle = currentAngle + sliceAngle;

    const x1 =
      cx + radius * Math.cos(startAngle);

    const y1 =
      cy + radius * Math.sin(startAngle);

    const x2 =
      cx + radius * Math.cos(endAngle);

    const y2 =
      cy + radius * Math.sin(endAngle);

    const ix1 =
      cx + innerRadius * Math.cos(endAngle);

    const iy1 =
      cy + innerRadius * Math.sin(endAngle);

    const ix2 =
      cx + innerRadius * Math.cos(startAngle);

    const iy2 =
      cy + innerRadius * Math.sin(startAngle);

    const largeArc =
      sliceAngle > Math.PI ? 1 : 0;

    const pathData = [
      `M ${x1} ${y1}`,
      `A ${radius} ${radius} 0 ${largeArc} 1 ${x2} ${y2}`,
      `L ${ix1} ${iy1}`,
      `A ${innerRadius} ${innerRadius} 0 ${largeArc} 0 ${ix2} ${iy2}`,
      "Z"
    ].join(" ");

    const path = createSVGElement("path", {
      d: pathData,
      fill:
        CHART_COLORS.palette[
          index % CHART_COLORS.palette.length
        ],
      stroke: "#fff",
      "stroke-width": 2
    });

    svg.appendChild(path);

    currentAngle = endAngle;
  });

  /* Center text */

  addText(
    svg,
    cx,
    cy - 5,
    formatCurrency(total),
    {
      size: 17,
      weight: "600",
      color: CHART_COLORS.ink,
      anchor: "middle"
    }
  );

  addText(
    svg,
    cx,
    cy + 17,
    "Total",
    {
      size: 11,
      anchor: "middle"
    }
  );

  /* -----------------------------
     Legend
  ----------------------------- */

  categoryData.forEach((item, index) => {
    const y = 45 + index * 32;

    const color =
      CHART_COLORS.palette[
        index % CHART_COLORS.palette.length
      ];

    const circle = createSVGElement("circle", {
      cx: 430,
      cy: y - 4,
      r: 5,
      fill: color
    });

    svg.appendChild(circle);

    addText(
      svg,
      445,
      y,
      item.category,
      {
        size: 11,
        color: CHART_COLORS.ink
      }
    );

    const percentage =
      ((Number(item.total) / total) * 100).toFixed(1);

    addText(
      svg,
      650,
      y,
      `${percentage}%`,
      {
        size: 11,
        anchor: "end"
      }
    );
  });

  container.appendChild(svg);

  chartInstances[key] = container;
}


/* -----------------------------
   HORIZONTAL BAR CHART
----------------------------- */

function renderBarChart(containerId, key, categoryData) {
  destroyIfExists(key);

  const container = getContainer(containerId);
  if (!container) return;

  container.innerHTML = "";

  if (!categoryData || categoryData.length === 0) {
    container.innerHTML = `
      <div style="
        height:100%;
        display:flex;
        align-items:center;
        justify-content:center;
        color:${CHART_COLORS.sage};
        font-family:Inter,sans-serif;
      ">
        No spending data available
      </div>
    `;

    chartInstances[key] = container;
    return;
  }

  const width = 700;
  const rowHeight = 45;

  const height =
    Math.max(260, categoryData.length * rowHeight + 50);

  const svg = createSVG(width, height);

  const margin = {
    top: 25,
    right: 70,
    bottom: 20,
    left: 140
  };

  const chartWidth =
    width - margin.left - margin.right;

  const values = categoryData.map(d =>
    Number(d.total) || 0
  );

  const maxValue = niceMax(Math.max(...values));

  /* -----------------------------
     Bars
  ----------------------------- */

  categoryData.forEach((item, index) => {
    const value = values[index];

    const y =
      margin.top + index * rowHeight;

    const barWidth =
      (value / maxValue) * chartWidth;

    /* Category */

    addText(
      svg,
      margin.left - 12,
      y + 18,
      item.category,
      {
        size: 11,
        color: CHART_COLORS.ink,
        anchor: "end"
      }
    );

    /* Background */

    const background = createSVGElement("rect", {
      x: margin.left,
      y: y + 5,
      width: chartWidth,
      height: 20,
      rx: 4,
      fill: "#F1F2EA"
    });

    svg.appendChild(background);

    /* Bar */

    const bar = createSVGElement("rect", {
      x: margin.left,
      y: y + 5,
      width: Math.max(barWidth, 2),
      height: 20,
      rx: 4,
      fill: CHART_COLORS.gold
    });

    svg.appendChild(bar);

    /* Value */

    addText(
      svg,
      margin.left + barWidth + 10,
      y + 19,
      formatCurrency(value),
      {
        size: 10,
        color: CHART_COLORS.sage
      }
    );
  });

  container.appendChild(svg);

  chartInstances[key] = container;
}