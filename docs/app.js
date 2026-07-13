// docs/app.js

const MA_COLORS = {
  MA5: "#f2b705",
  MA10: "#4d8dff",
  MA20: "#a259ff",
  MA60: "#ff6fa5",
};

const priceChartEl = document.getElementById("price-chart");
const rsiChartEl = document.getElementById("rsi-chart");
const instChartEl = document.getElementById("institutional-chart");
const marginChartEl = document.getElementById("margin-chart");
const selectEl = document.getElementById("stock-select");
const updatedAtEl = document.getElementById("updated-at");
const maLegendEl = document.getElementById("ma-legend");
const mfDateEl = document.getElementById("main-force-date");
const mfBuyTableEl = document.querySelector("#mf-buy-table tbody");
const mfSellTableEl = document.querySelector("#mf-sell-table tbody");

let priceChart, rsiChart, instChart, marginChart, candleSeries, rsiSeries14, rsiSeries6;
let foreignSeries, trustSeries, dealerSeries, marginBalanceSeries, shortBalanceSeries;
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
    rightPriceScale: { borderColor: "#262a36", scaleMargins: { top: 0.1, bottom: 0.1 } },
  });

  // RSI 固定在 0-100 區間顯示,用 autoscaleInfoProvider 強制範圍,不受資料本身極值影響
  rsiSeries14 = rsiChart.addLineSeries({
    color: "#4d8dff", lineWidth: 2,
    autoscaleInfoProvider: () => ({ priceRange: { minValue: 0, maxValue: 100 } }),
  });
  rsiSeries6 = rsiChart.addLineSeries({ color: "#f2b705", lineWidth: 1 });

  // ---------- 三大法人買賣超圖(三條淨買賣超折線) ----------
  instChart = LightweightCharts.createChart(instChartEl, {
    ...chartBaseOptions(),
    width: instChartEl.clientWidth,
    height: instChartEl.clientHeight,
  });
  foreignSeries = instChart.addLineSeries({ color: "#d6382e", lineWidth: 1.5 });
  trustSeries = instChart.addLineSeries({ color: "#f2b705", lineWidth: 1.5 });
  dealerSeries = instChart.addLineSeries({ color: "#4d8dff", lineWidth: 1.5 });

  // ---------- 融資融券圖(融資餘額用左軸,融券餘額用右軸,單位量級差很多) ----------
  marginChart = LightweightCharts.createChart(marginChartEl, {
    ...chartBaseOptions(),
    width: marginChartEl.clientWidth,
    height: marginChartEl.clientHeight,
    leftPriceScale: { visible: true, borderColor: "#262a36" },
  });
  marginBalanceSeries = marginChart.addLineSeries({
    color: "#4d8dff", lineWidth: 1.5, priceScaleId: "left",
  });
  shortBalanceSeries = marginChart.addLineSeries({
    color: "#ff6fa5", lineWidth: 1.5, priceScaleId: "right",
  });

  // 四張圖的時間軸互相同步
  [priceChart, rsiChart, instChart, marginChart].forEach((source) => {
    [priceChart, rsiChart, instChart, marginChart].forEach((target) => {
      if (source !== target) syncTimeScales(source, target);
    });
  });

  window.addEventListener("resize", () => {
    priceChart.resize(priceChartEl.clientWidth, priceChartEl.clientHeight);
    rsiChart.resize(rsiChartEl.clientWidth, rsiChartEl.clientHeight);
    instChart.resize(instChartEl.clientWidth, instChartEl.clientHeight);
    marginChart.resize(marginChartEl.clientWidth, marginChartEl.clientHeight);
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

function renderMainForce(mainForce) {
  mfBuyTableEl.innerHTML = "";
  mfSellTableEl.innerHTML = "";

  if (!mainForce || !mainForce.date) {
    mfDateEl.textContent = "無資料";
    return;
  }
  mfDateEl.textContent = `資料日期: ${mainForce.date}`;

  const fillTable = (tbody, rows) => {
    if (!rows || rows.length === 0) {
      const tr = document.createElement("tr");
      tr.innerHTML = `<td class="mf-name" colspan="2">無資料</td>`;
      tbody.appendChild(tr);
      return;
    }
    rows.forEach((row) => {
      const tr = document.createElement("tr");
      const netClass = row.net >= 0 ? "pos" : "neg";
      const sign = row.net > 0 ? "+" : "";
      tr.innerHTML = `
        <td class="mf-name">${row.trader}</td>
        <td class="mf-net ${netClass}">${sign}${row.net}</td>
      `;
      tbody.appendChild(tr);
    });
  };

  fillTable(mfBuyTableEl, mainForce.top_buy);
  fillTable(mfSellTableEl, mainForce.top_sell);
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

  const inst = data.institutional || {};
  foreignSeries.setData(inst.foreign_net || []);
  trustSeries.setData(inst.trust_net || []);
  dealerSeries.setData(inst.dealer_net || []);

  const margin = data.margin || {};
  marginBalanceSeries.setData(margin.margin_balance || []);
  shortBalanceSeries.setData(margin.short_balance || []);

  renderMainForce(data.main_force);

  priceChart.timeScale().fitContent();
  rsiChart.timeScale().fitContent();
  instChart.timeScale().fitContent();
  marginChart.timeScale().fitContent();

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
