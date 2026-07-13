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
const valuationChartEl = document.getElementById("valuation-chart");
const selectEl = document.getElementById("stock-select");
const pageSelectEl = document.getElementById("page-select");
const pageGroupEls = document.querySelectorAll(".page-group");
const updatedAtEl = document.getElementById("updated-at");
const maLegendEl = document.getElementById("ma-legend");
const fundHeadEl = document.getElementById("fund-table-head");
const fundBodyEl = document.getElementById("fund-table-body");
const stockLabelEl = document.getElementById("stock-label");
const trendNarrativeEl = document.getElementById("trend-narrative");
const probStateLabelEl = document.getElementById("prob-state-label");
const probBarUpEl = document.getElementById("prob-bar-up");
const probBarDownEl = document.getElementById("prob-bar-down");
const probUpPctEl = document.getElementById("prob-up-pct");
const probDownPctEl = document.getElementById("prob-down-pct");
const probSampleSizeEl = document.getElementById("prob-sample-size");
const newsTotalEl = document.getElementById("news-total");
const newsBarPosEl = document.getElementById("news-bar-pos");
const newsBarNeuEl = document.getElementById("news-bar-neu");
const newsBarNegEl = document.getElementById("news-bar-neg");
const newsPosCountEl = document.getElementById("news-pos-count");
const newsNeuCountEl = document.getElementById("news-neu-count");
const newsNegCountEl = document.getElementById("news-neg-count");
const newsListEl = document.getElementById("news-list");

let manifestStockNames = {};
let currentPage = "price";

let priceChart, rsiChart, instChart, marginChart, valuationChart;
let candleSeries, rsiSeries14, rsiSeries6;
let foreignSeries, trustSeries, dealerSeries, marginBalanceSeries, shortBalanceSeries;
let perSeries, pbrSeries;
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

  // ---------- 本益比 / 淨值比(PER左軸, PBR右軸) ----------
  valuationChart = LightweightCharts.createChart(valuationChartEl, {
    ...chartBaseOptions(),
    width: valuationChartEl.clientWidth,
    height: valuationChartEl.clientHeight,
    leftPriceScale: { visible: true, borderColor: "#262a36" },
  });
  perSeries = valuationChart.addLineSeries({
    color: "#4d8dff", lineWidth: 1.5, priceScaleId: "left",
  });
  pbrSeries = valuationChart.addLineSeries({
    color: "#ff6fa5", lineWidth: 1.5, priceScaleId: "right",
  });

  // 五張日資料圖的時間軸互相同步(基本面表格是季資料,不在此同步群組內)
  const syncGroup = [priceChart, rsiChart, instChart, marginChart, valuationChart];
  syncGroup.forEach((source) => {
    syncGroup.forEach((target) => {
      if (source !== target) syncTimeScales(source, target);
    });
  });

  window.addEventListener("resize", () => resizeChartsForPage(currentPage));
}

// 每個分頁包含哪些圖表,切換分頁或視窗resize時,只需要重繪「目前看得到的」那些圖表就好
// (隱藏中的分頁,對應的DOM容器寬高會是0,這時候resize沒有意義,等使用者切過去看時才重繪)
function resizeChartsForPage(page) {
  if (page === "price") {
    priceChart.resize(priceChartEl.clientWidth, priceChartEl.clientHeight);
  } else if (page === "indicators") {
    rsiChart.resize(rsiChartEl.clientWidth, rsiChartEl.clientHeight);
    instChart.resize(instChartEl.clientWidth, instChartEl.clientHeight);
    marginChart.resize(marginChartEl.clientWidth, marginChartEl.clientHeight);
  } else if (page === "fundamentals") {
    valuationChart.resize(valuationChartEl.clientWidth, valuationChartEl.clientHeight);
  }
}

function setActivePage(page) {
  currentPage = page;
  pageGroupEls.forEach((el) => {
    el.style.display = el.dataset.page === page ? "" : "none";
  });
  // 分頁切回可見狀態的當下,容器才會有正確的寬高,所以在下一個畫面更新時機再重繪圖表
  requestAnimationFrame(() => resizeChartsForPage(page));
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

const FUND_ROWS = [
  { key: "eps", label: "EPS(元)", digits: 2 },
  { key: "revenue_yi", label: "營收(億)", digits: 1 },
  { key: "gross_margin", label: "毛利率(%)", digits: 1 },
  { key: "operating_margin", label: "營益率(%)", digits: 1 },
  { key: "roe", label: "ROE(%)", digits: 1 },
  { key: "roa", label: "ROA(%)", digits: 1 },
  { key: "debt_ratio", label: "負債比(%)", digits: 1 },
  { key: "operating_cash_flow_yi", label: "營業現金流(億)", digits: 1 },
];

function formatQuarterLabel(dateStr) {
  const d = new Date(dateStr);
  const year = d.getFullYear() % 100;
  const month = d.getMonth() + 1; // 0-indexed
  const quarter = Math.floor((month - 1) / 3) + 1;
  return `${year}Q${quarter}`;
}

function renderFundamentalsTable(fundamentals) {
  fundHeadEl.innerHTML = "";
  fundBodyEl.innerHTML = "";

  const quarters = fundamentals?.quarters || [];
  if (quarters.length === 0) {
    fundHeadEl.innerHTML = `<th>季度</th><th>無資料</th>`;
    return;
  }

  // 表頭:第一格空白(給列標籤用),其餘是每一季的標籤
  let headHtml = `<th>季度</th>`;
  quarters.forEach((q) => {
    headHtml += `<th>${formatQuarterLabel(q.date)}</th>`;
  });
  fundHeadEl.innerHTML = headHtml;

  // 每個指標一列,橫向對照各季數值
  FUND_ROWS.forEach((rowDef) => {
    let rowHtml = `<td>${rowDef.label}</td>`;
    quarters.forEach((q) => {
      const v = q[rowDef.key];
      rowHtml += `<td>${v === null || v === undefined ? "-" : v.toFixed(rowDef.digits)}</td>`;
    });
    const tr = document.createElement("tr");
    tr.innerHTML = rowHtml;
    fundBodyEl.appendChild(tr);
  });
}

function renderAnalysis(analysis) {
  const narrative = analysis?.narrative || "目前沒有足夠資料可以產生分析。";
  trendNarrativeEl.textContent = narrative;

  const nextDay = analysis?.next_day || {};
  if (nextDay.up_pct === null || nextDay.up_pct === undefined) {
    probStateLabelEl.textContent = nextDay.state_label || "資料不足";
    probBarUpEl.style.width = "50%";
    probBarDownEl.style.width = "50%";
    probUpPctEl.textContent = "-";
    probDownPctEl.textContent = "-";
    probSampleSizeEl.textContent = "";
    return;
  }

  probStateLabelEl.textContent = nextDay.state_label || "";
  probBarUpEl.style.width = `${nextDay.up_pct}%`;
  probBarDownEl.style.width = `${nextDay.down_pct}%`;
  probUpPctEl.textContent = nextDay.up_pct;
  probDownPctEl.textContent = nextDay.down_pct;
  probSampleSizeEl.textContent = `樣本數: ${nextDay.sample_size} 天`;
}

const SENTIMENT_TAG_CLASS = { "利多": "pos", "利空": "neg", "中性": "neu" };

function renderNews(news) {
  const total = news?.total || 0;
  const pos = news?.positive_count || 0;
  const neu = news?.neutral_count || 0;
  const neg = news?.negative_count || 0;

  newsTotalEl.textContent = `近 ${total} 則相關新聞`;

  if (total === 0) {
    newsBarPosEl.style.width = "0%";
    newsBarNeuEl.style.width = "100%";
    newsBarNegEl.style.width = "0%";
  } else {
    newsBarPosEl.style.width = `${(pos / total) * 100}%`;
    newsBarNeuEl.style.width = `${(neu / total) * 100}%`;
    newsBarNegEl.style.width = `${(neg / total) * 100}%`;
  }
  newsPosCountEl.textContent = pos;
  newsNeuCountEl.textContent = neu;
  newsNegCountEl.textContent = neg;

  newsListEl.innerHTML = "";
  const articles = news?.articles || [];
  if (articles.length === 0) {
    const li = document.createElement("li");
    li.textContent = "目前沒有相關新聞資料。";
    newsListEl.appendChild(li);
    return;
  }

  articles.forEach((a) => {
    const li = document.createElement("li");
    const tagClass = SENTIMENT_TAG_CLASS[a.sentiment] || "neu";

    const tag = document.createElement("span");
    tag.className = `news-tag ${tagClass}`;
    tag.textContent = a.sentiment;

    const titleLink = document.createElement("a");
    titleLink.className = "news-item-title";
    titleLink.href = a.link || "#";
    titleLink.target = "_blank";
    titleLink.rel = "noopener noreferrer";
    titleLink.textContent = a.title;

    const meta = document.createElement("span");
    meta.className = "news-item-meta";
    meta.textContent = `${a.source || ""} · ${a.date || ""}`;

    li.appendChild(tag);
    li.appendChild(titleLink);
    li.appendChild(meta);
    newsListEl.appendChild(li);
  });
}

async function loadStock(stockId) {
  const res = await fetch(`data/${stockId}.json?t=${Date.now()}`);
  if (!res.ok) {
    alert(`找不到 ${stockId} 的資料`);
    return;
  }
  const data = await res.json();

  const stockName = data.stock_name || manifestStockNames[stockId] || "";
  stockLabelEl.innerHTML = stockName
    ? `${stockName}<span class="stock-id">${stockId}</span>`
    : `<span class="stock-id">${stockId}</span>`;

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

  const valuation = data.valuation || {};
  perSeries.setData(valuation.PER || []);
  pbrSeries.setData(valuation.PBR || []);

  renderFundamentalsTable(data.fundamentals);
  renderAnalysis(data.analysis);
  renderNews(data.news);

  priceChart.timeScale().fitContent();
  rsiChart.timeScale().fitContent();
  instChart.timeScale().fitContent();
  marginChart.timeScale().fitContent();
  valuationChart.timeScale().fitContent();

  const updated = new Date(data.updated_at);
  updatedAtEl.textContent = `資料更新: ${updated.toLocaleString("zh-TW")}`;
}

async function loadManifestAndInit() {
  const res = await fetch(`data/manifest.json?t=${Date.now()}`);
  const manifest = await res.json();
  manifestStockNames = manifest.stock_names || {};

  selectEl.innerHTML = "";
  manifest.stocks.forEach((id) => {
    const opt = document.createElement("option");
    opt.value = id;
    const name = manifestStockNames[id];
    opt.textContent = name ? `${id} ${name}` : id;
    selectEl.appendChild(opt);
  });

  selectEl.addEventListener("change", () => loadStock(selectEl.value));

  if (manifest.stocks.length > 0) {
    await loadStock(manifest.stocks[0]);
  }
}

pageSelectEl.addEventListener("change", () => setActivePage(pageSelectEl.value));

initCharts();
// 一定要在 initCharts() 之後才切換分頁可見度:
// 圖表建立當下需要容器有實際寬高,這時候三個分頁都還是可見的,寬高才會正確量到。
setActivePage("price");
loadManifestAndInit();
