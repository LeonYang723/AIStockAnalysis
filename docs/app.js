// docs/app.js

const MA_COLORS = {
  MA5: "#f2b705",
  MA10: "#4d8dff",
  MA20: "#a259ff",
  MA60: "#ff6fa5",
};

const priceChartEl = document.getElementById("price-chart");
const rsiChartEl = document.getElementById("rsi-chart");
const selectEl = document.getElementById("stock-select");
const updatedAtEl = document.getElementById("updated-at");
const maLegendEl = document.getElementById("ma-legend");

let priceChart, rsiChart, candleSeries, rsiSeries14, rsiSeries6;
let maSeriesMap = {};
let isSyncingRange = false;

function chartBaseOptions() {
  return {
    layout: {
      background: { color: "transparent" },
      textColor: "#c7cad1",
    },
    grid: {
      vertLines: { color: "#22252f" },
      horzLines: { color: "#22252f" },
    },
    rightPriceScale: { borderColor: "#262a36" },
    timeScale: { borderColor: "#262a36" },
    crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
  };
}

function initCharts() {
  priceChart = LightweightCharts.createChart(priceChartEl, {
    ...chartBaseOptions(),
    width: priceChartEl.clientWidth,
    height: priceChartEl.clientHeight,
  });

  candleSeries = priceChart.addCandlestickSeries({
    upColor: "#d6382e",
    downColor: "#1e9e5a",
    borderUpColor: "#d6382e",
    borderDownColor: "#1e9e5a",
    wickUpColor: "#d6382e",
    wickDownColor: "#1e9e5a",
  });

  rsiChart = LightweightCharts.createChart(rsiChartEl, {
    ...chartBaseOptions(),
    width: rsiChartEl.clientWidth,
    height: rsiChartEl.clientHeight,
  });

  rsiSeries14 = rsiChart.addLineSeries({ color: "#4d8dff", lineWidth: 2 });
  rsiSeries6 = rsiChart.addLineSeries({ color: "#f2b705", lineWidth: 1 });

  // 上下兩張圖的時間軸同步(拖曳/縮放其中一張,另一張跟著動)
  syncTimeScales(priceChart, rsiChart);
  syncTimeScales(rsiChart, priceChart);

  window.addEventListener("resize", () => {
    priceChart.resize(priceChartEl.clientWidth, priceChartEl.clientHeight);
    rsiChart.resize(rsiChartEl.clientWidth, rsiChartEl.clientHeight);
  });
}

function syncTimeScales(source, target) {
  source.timeScale().subscribeVisibleLogicalRangeChange((range) => {
    if (isSyncingRange || !range) return;
    isSyncingRange = true;
    target.timeScale().setVisibleLogicalRange(range);
    isSyncingRange = false;
  });
}

function clearMaSeries() {
  Object.values(maSeriesMap).forEach((s) => priceChart.removeSeries(s));
  maSeriesMap = {};
  maLegendEl.innerHTML = "";
}

function renderMaSeries(maData) {
  clearMaSeries();
  Object.entries(maData).forEach(([key, points]) => {
    if (!points || points.length === 0) return;
    const color = MA_COLORS[key] || "#888";
    const series = priceChart.addLineSeries({ color, lineWidth: 1.5 });
    series.setData(points);
    maSeriesMap[key] = series;

    const tag = document.createElement("span");
    tag.style.color = color;
    tag.textContent = key;
    maLegendEl.appendChild(tag);
  });
}

async function loadStock(stockId) {
  const res = await fetch(`data/${stockId}.json?t=${Date.now()}`);
  if (!res.ok) {
    alert(`找不到 ${stockId} 的資料`);
    return;
  }
  const data = await res.json();

  candleSeries.setData(data.price);
  renderMaSeries(data.ma || {});
  rsiSeries14.setData(data.rsi?.RSI14 || []);
  rsiSeries6.setData(data.rsi?.RSI6 || []);

  priceChart.timeScale().fitContent();
  rsiChart.timeScale().fitContent();

  const updated = new Date(data.updated_at);
  updatedAtEl.textContent = `資料更新: ${updated.toLocaleString("zh-TW")}`;
}

async function loadManifestAndInit() {
  const res = await fetch(`data/manifest.json?t=${Date.now()}`);
  const manifest = await res.json();

  selectEl.innerHTML = "";
  manifest.stocks.forEach((id) => {
    const opt = document.createElement("option");
    opt.value = id;
    opt.textContent = id;
    selectEl.appendChild(opt);
  });

  selectEl.addEventListener("change", () => loadStock(selectEl.value));

  if (manifest.stocks.length > 0) {
    await loadStock(manifest.stocks[0]);
  }
}

initCharts();
loadManifestAndInit();
