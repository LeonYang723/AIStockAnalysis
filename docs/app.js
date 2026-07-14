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
const trackSummaryEl = document.getElementById("track-record-summary");
const trackBodyEl = document.getElementById("track-record-body");
const mlStateLabelEl = document.getElementById("ml-state-label");
const mlBarUpEl = document.getElementById("ml-bar-up");
const mlBarDownEl = document.getElementById("ml-bar-down");
const mlUpPctEl = document.getElementById("ml-up-pct");
const mlDownPctEl = document.getElementById("ml-down-pct");
const mlTrackInlineEl = document.getElementById("ml-track-inline");
const mlTrackSummaryEl = document.getElementById("ml-track-summary");
const mlTrackBodyEl = document.getElementById("ml-track-body");
const instAnomalyBadgesEl = document.getElementById("inst-anomaly-badges");
const overviewStockTitleEl = document.getElementById("overview-stock-title");
const overviewUpdatedEl = document.getElementById("overview-updated");
const overviewCloseEl = document.getElementById("overview-close");
const overviewChangeEl = document.getElementById("overview-change");
const overviewPerEl = document.getElementById("overview-per");
const overviewPbrEl = document.getElementById("overview-pbr");
const overviewRsiEl = document.getElementById("overview-rsi");
const overviewRsiStateEl = document.getElementById("overview-rsi-state");
const overviewMaStateEl = document.getElementById("overview-ma-state");
const overviewInstitutionalEl = document.getElementById("overview-institutional");
const overviewNextDayEl = document.getElementById("overview-next-day");
const overviewNewsEl = document.getElementById("overview-news");
const overviewAnomalyBannerEl = document.getElementById("overview-anomaly-banner");
const staleWarningEl = document.getElementById("stale-warning");
const compareCountEl = document.getElementById("compare-count");
const compareTableBodyEl = document.getElementById("compare-table-body");

const STALE_WARNING_DAYS = 4; // 資料超過幾天沒更新就跳警示(平日排程+跨週末的合理緩衝)
let manifestStockIds = [];
let compareDataLoaded = false;

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

  if (page === "compare") {
    loadCompareTable();
  }
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

function renderTrackRecordGeneric(trackRecord, summaryEl, bodyEl) {
  bodyEl.innerHTML = "";

  const resolvedCount = trackRecord?.resolved_count || 0;
  const correctCount = trackRecord?.correct_count || 0;
  const accuracyPct = trackRecord?.accuracy_pct;

  if (resolvedCount === 0) {
    summaryEl.textContent = "目前還沒有累積到任何已驗證的預測記錄,持續運作一段時間後才會開始顯示命中率。";
  } else {
    summaryEl.innerHTML =
      `目前累積 <b>${resolvedCount}</b> 次已知結果的預測,命中 <b>${correctCount}</b> 次,` +
      `命中率 <b>${accuracyPct}%</b>`;
  }

  const recent = trackRecord?.recent || [];
  if (recent.length === 0) {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td colspan="5">尚無已驗證的記錄</td>`;
    bodyEl.appendChild(tr);
    return;
  }

  const directionText = { up: "漲", down: "跌" };
  recent.forEach((r) => {
    const tr = document.createElement("tr");
    const guessTag = r.correct
      ? `<span class="track-tag hit">✓ 猜中</span>`
      : `<span class="track-tag miss">✕ 猜錯</span>`;
    tr.innerHTML = `
      <td>${r.predict_date}</td>
      <td>${directionText[r.predicted_direction] || "-"}</td>
      <td>${r.target_date || "-"}</td>
      <td>${directionText[r.actual_direction] || "-"}</td>
      <td>${guessTag}</td>
    `;
    bodyEl.appendChild(tr);
  });
}

function renderTrackRecord(trackRecord) {
  renderTrackRecordGeneric(trackRecord, trackSummaryEl, trackBodyEl);
}

const ANOMALY_LABEL_MAP = { foreign: "外資", trust: "投信", dealer: "自營商" };

function renderInstAnomalyBadges(anomalies) {
  instAnomalyBadgesEl.innerHTML = "";
  if (!anomalies) return;

  Object.entries(anomalies).forEach(([key, info]) => {
    const badge = document.createElement("span");
    const dirClass = info.direction === "buy" ? "buy" : "sell";
    const dirText = info.direction === "buy" ? "買超" : "賣超";
    badge.className = `anomaly-badge ${dirClass}`;
    badge.textContent = `⚠ ${ANOMALY_LABEL_MAP[key] || key}連續${info.streak}天${dirText}`;
    instAnomalyBadgesEl.appendChild(badge);
  });
}

function renderOverview(data) {
  const overview = data.overview || {};
  const stockName = data.stock_name || manifestStockNames[data.stock_id] || "";
  overviewStockTitleEl.textContent = stockName ? `${stockName} ${data.stock_id} 總覽` : `${data.stock_id} 總覽`;
  overviewUpdatedEl.textContent = data.updated_at
    ? `資料更新: ${new Date(data.updated_at).toLocaleString("zh-TW")}`
    : "";

  overviewCloseEl.textContent = overview.close != null ? overview.close.toFixed(2) : "-";

  if (overview.change != null) {
    const sign = overview.change > 0 ? "+" : "";
    const cls = overview.change > 0 ? "up" : overview.change < 0 ? "down" : "flat";
    overviewChangeEl.className = `overview-change ${cls}`;
    overviewChangeEl.textContent = `${sign}${overview.change.toFixed(2)} (${sign}${overview.change_pct}%)`;
  } else {
    overviewChangeEl.textContent = "";
  }

  overviewPerEl.textContent = overview.per != null ? overview.per.toFixed(2) : "-";
  overviewPbrEl.textContent = overview.pbr != null ? overview.pbr.toFixed(2) : "-";
  overviewRsiEl.textContent = overview.rsi14 != null ? overview.rsi14 : "-";
  overviewRsiStateEl.textContent = overview.rsi_state || "";
  overviewMaStateEl.textContent = overview.ma_state || "-";

  overviewInstitutionalEl.innerHTML = "";
  [
    { label: "外資", value: overview.foreign_net_today },
    { label: "投信", value: overview.trust_net_today },
    { label: "自營商", value: overview.dealer_net_today },
  ].forEach((item) => {
    const div = document.createElement("div");
    if (item.value == null) {
      div.textContent = `${item.label}: -`;
    } else {
      const cls = item.value > 0 ? "up" : item.value < 0 ? "down" : "";
      const sign = item.value > 0 ? "+" : "";
      div.innerHTML = `${item.label}: <span class="${cls}">${sign}${item.value}</span>`;
    }
    overviewInstitutionalEl.appendChild(div);
  });

  overviewNextDayEl.innerHTML =
    overview.next_day_up_pct != null
      ? `<span class="txt-up">上漲${overview.next_day_up_pct}%</span> / ` +
        `<span class="txt-down">下跌${overview.next_day_down_pct}%</span>`
      : "資料不足";

  const newsTotal = (overview.news_positive || 0) + (overview.news_negative || 0) + (overview.news_neutral || 0);
  overviewNewsEl.innerHTML =
    newsTotal > 0
      ? `<span class="txt-up">利多${overview.news_positive}</span> / ` +
        `<span class="txt-neutral">中性${overview.news_neutral}</span> / ` +
        `<span class="txt-down">利空${overview.news_negative}</span>`
      : "無相關新聞";

  // 把三大法人連續買賣超的異常也整理到總覽頁顯示
  overviewAnomalyBannerEl.innerHTML = "";
  const anomalies = data.institutional?.anomalies || {};
  Object.entries(anomalies).forEach(([key, info]) => {
    const dirText = info.direction === "buy" ? "買超" : "賣超";
    const line = document.createElement("div");
    line.className = "anomaly-line";
    line.textContent = `⚠ ${ANOMALY_LABEL_MAP[key] || key} 連續 ${info.streak} 天${dirText}`;
    overviewAnomalyBannerEl.appendChild(line);
  });
}

function renderStaleWarning(updatedAtStr) {
  if (!updatedAtStr) {
    staleWarningEl.style.display = "none";
    return;
  }
  const updated = new Date(updatedAtStr);
  const daysSince = (Date.now() - updated.getTime()) / (1000 * 60 * 60 * 24);

  if (daysSince > STALE_WARNING_DAYS) {
    staleWarningEl.style.display = "";
    staleWarningEl.textContent =
      `⚠ 資料已經 ${Math.floor(daysSince)} 天沒有更新了(最後更新: ${updated.toLocaleString("zh-TW")}),` +
      `可能是排程沒有正常執行,建議去 GitHub Actions 檢查一下。`;
  } else {
    staleWarningEl.style.display = "none";
  }
}

function formatCompareValue(value, digits, suffix = "") {
  return value != null ? `${value.toFixed(digits)}${suffix}` : "-";
}

function renderCompareTable(rows) {
  compareTableBodyEl.innerHTML = "";
  compareCountEl.textContent = `共 ${rows.length} 檔`;

  if (rows.length === 0) {
    compareTableBodyEl.innerHTML = `<tr><td colspan="10">目前沒有可比較的股票資料</td></tr>`;
    return;
  }

  rows.forEach((data) => {
    const overview = data.overview || {};
    const anomalies = data.institutional?.anomalies || {};
    const hasAnomaly = Object.keys(anomalies).length > 0;

    const changeCls = overview.change > 0 ? "txt-up" : overview.change < 0 ? "txt-down" : "";
    const changeSign = overview.change > 0 ? "+" : "";
    const changeText =
      overview.change_pct != null ? `<span class="${changeCls}">${changeSign}${overview.change_pct}%</span>` : "-";

    const nextDayText =
      overview.next_day_up_pct != null
        ? `<span class="txt-up">${overview.next_day_up_pct}%</span> / <span class="txt-down">${overview.next_day_down_pct}%</span>`
        : "-";

    const newsTotal = (overview.news_positive || 0) + (overview.news_negative || 0) + (overview.news_neutral || 0);
    const newsText =
      newsTotal > 0
        ? `<span class="txt-up">${overview.news_positive}</span>/<span class="txt-neutral">${overview.news_neutral}</span>/<span class="txt-down">${overview.news_negative}</span>`
        : "-";

    const anomalyText = hasAnomaly
      ? Object.entries(anomalies)
          .map(([key, info]) => {
            const cls = info.direction === "buy" ? "txt-up" : "txt-down";
            const dirText = info.direction === "buy" ? "買超" : "賣超";
            return `<span class="${cls}">⚠${ANOMALY_LABEL_MAP[key] || key}${info.streak}天${dirText}</span>`;
          })
          .join(" ")
      : "-";

    const tr = document.createElement("tr");
    if (hasAnomaly) tr.classList.add("has-anomaly");
    tr.innerHTML = `
      <td>${data.stock_id}${data.stock_name ? " " + data.stock_name : ""}</td>
      <td>${formatCompareValue(overview.close, 2)}</td>
      <td>${changeText}</td>
      <td>${formatCompareValue(overview.per, 1)}</td>
      <td>${formatCompareValue(overview.pbr, 1)}</td>
      <td>${overview.rsi14 != null ? overview.rsi14 : "-"}</td>
      <td>${overview.ma_state || "-"}</td>
      <td>${nextDayText}</td>
      <td>${newsText}</td>
      <td>${anomalyText}</td>
    `;
    tr.addEventListener("click", () => {
      selectEl.value = data.stock_id;
      loadStock(data.stock_id);
      pageSelectEl.value = "overview";
      setActivePage("overview");
    });
    compareTableBodyEl.appendChild(tr);
  });
}

async function loadCompareTable(force = false) {
  if (compareDataLoaded && !force) return;

  compareTableBodyEl.innerHTML = `<tr><td colspan="10">載入中...</td></tr>`;
  const rows = [];

  for (const id of manifestStockIds) {
    try {
      const res = await fetch(`data/${id}.json?t=${Date.now()}`);
      if (!res.ok) continue;
      const data = await res.json();
      rows.push(data);
    } catch (e) {
      // 單一股票抓取失敗就跳過,不影響其他股票顯示
    }
  }

  renderCompareTable(rows);
  compareDataLoaded = true;
}

function renderMlPrediction(mlNextDay) {
  if (!mlNextDay || mlNextDay.up_pct === null || mlNextDay.up_pct === undefined) {
    mlStateLabelEl.textContent = mlNextDay?.state_label || "資料不足";
    mlBarUpEl.style.width = "50%";
    mlBarDownEl.style.width = "50%";
    mlUpPctEl.textContent = "-";
    mlDownPctEl.textContent = "-";
    mlTrackInlineEl.textContent = "";
    renderTrackRecordGeneric(mlNextDay?.track_record, mlTrackSummaryEl, mlTrackBodyEl);
    return;
  }

  mlStateLabelEl.textContent = mlNextDay.state_label || "";
  mlBarUpEl.style.width = `${mlNextDay.up_pct}%`;
  mlBarDownEl.style.width = `${mlNextDay.down_pct}%`;
  mlUpPctEl.textContent = mlNextDay.up_pct;
  mlDownPctEl.textContent = mlNextDay.down_pct;

  const tr = mlNextDay.track_record;
  if (tr && tr.resolved_count > 0) {
    mlTrackInlineEl.textContent =
      `實際命中率: ${tr.accuracy_pct}%(已驗證${tr.resolved_count}次,命中${tr.correct_count}次)`;
  } else {
    mlTrackInlineEl.textContent = "實際命中率: 尚未累積已驗證的記錄";
  }

  renderTrackRecordGeneric(tr, mlTrackSummaryEl, mlTrackBodyEl);
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
  renderInstAnomalyBadges(inst.anomalies);

  const margin = data.margin || {};
  marginBalanceSeries.setData(margin.margin_balance || []);
  shortBalanceSeries.setData(margin.short_balance || []);

  const valuation = data.valuation || {};
  perSeries.setData(valuation.PER || []);
  pbrSeries.setData(valuation.PBR || []);

  renderFundamentalsTable(data.fundamentals);
  renderAnalysis(data.analysis);
  renderTrackRecord(data.analysis?.next_day?.track_record);
  renderMlPrediction(data.analysis?.next_day_ml);
  renderNews(data.news);
  renderOverview(data);

  priceChart.timeScale().fitContent();
  rsiChart.timeScale().fitContent();
  instChart.timeScale().fitContent();
  marginChart.timeScale().fitContent();
  valuationChart.timeScale().fitContent();

  const updated = new Date(data.updated_at);
  updatedAtEl.textContent = `資料更新: ${updated.toLocaleString("zh-TW")}`;
  renderStaleWarning(data.updated_at);
}

async function loadManifestAndInit() {
  const res = await fetch(`data/manifest.json?t=${Date.now()}`);
  const manifest = await res.json();
  manifestStockNames = manifest.stock_names || {};
  manifestStockIds = manifest.stocks || [];

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
setActivePage("overview");
loadManifestAndInit();
