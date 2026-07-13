# scripts/build_data.py
"""
給 GitHub Actions 排程執行的主程式。
流程: 抓股價 -> 算均線/RSI -> 輸出成 docs/data/{stock_id}.json 給前端讀取。

用法:
    python build_data.py                # 抓 config.py 裡 STOCK_LIST 全部
    python build_data.py 2330 2317      # 只抓指定股票代號
"""

import sys
import os
import json
import math
from datetime import datetime, timedelta

# 確保無論從哪個目錄執行,都能正確定位到 repo 根目錄下的 docs/data
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)

from config import (
    STOCK_LIST, LOOKBACK_DAYS, RSI_PERIODS, MA_WINDOWS, FUNDAMENTALS_QUARTERS,
    ANALYSIS_LOOKBACK_YEARS, NEWS_LOOKBACK_DAYS, NEWS_MAX_ARTICLES, OUTPUT_DIR,
)
from data_fetcher import (
    get_stock_price, get_institutional_investors, get_margin_trading,
    get_valuation_ratios, get_financial_statements, get_balance_sheet, get_cash_flow,
    get_stock_names, get_stock_news,
)
from indicators import add_moving_averages, add_rsi_columns
from analysis import generate_trend_narrative, compute_next_day_probability
from news_analysis import summarize_news
from prediction_tracker import load_log, save_log, resolve_pending, add_new_prediction, compute_track_record

OUTPUT_DIR_ABS = os.path.join(REPO_ROOT, OUTPUT_DIR)


def _clean(value):
    """NaN / None 統一轉成 JSON 合法的 null"""
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


def _series_from_df(df, value_cols: list) -> dict:
    """把 dataframe(需有 date 欄位)轉成 {col: [{time, value}, ...]} 格式,自動跳過NaN"""
    series = {col: [] for col in value_cols}
    for _, row in df.iterrows():
        t = row["date"].strftime("%Y-%m-%d")
        for col in value_cols:
            v = _clean(row[col])
            if v is not None:
                series[col].append({"time": t, "value": v})
    return series


def build_one(stock_id: str, token: str = None, stock_name: str = None) -> dict:
    end_date = datetime.today().strftime("%Y-%m-%d")

    # 「隔日漲跌機率」的統計需要比較長的歷史資料才夠可靠,
    # 所以股價改抓 ANALYSIS_LOOKBACK_YEARS 年份,均線/RSI也算在這個較長的區間上,
    # 圖表顯示時再裁切成最近 LOOKBACK_DAYS 筆,兩邊互不影響。
    analysis_start_date = (datetime.today() - timedelta(days=int(ANALYSIS_LOOKBACK_YEARS * 365))).strftime("%Y-%m-%d")
    start_date = (datetime.today() - timedelta(days=int(LOOKBACK_DAYS * 1.6))).strftime("%Y-%m-%d")
    # start_date(較短區間)用來過濾三大法人/融資融券/本益比這些「顯示用」的日資料

    full_df = get_stock_price(stock_id, analysis_start_date, end_date, token=token)
    full_df = add_moving_averages(full_df, windows=MA_WINDOWS)
    full_df = add_rsi_columns(full_df, periods=RSI_PERIODS)

    # 只保留最近 LOOKBACK_DAYS 個交易日給圖表顯示,避免檔案太大
    df = full_df.tail(LOOKBACK_DAYS).reset_index(drop=True)

    price = []
    volume = []
    ma_series = {f"MA{w}": [] for w in MA_WINDOWS}
    rsi_series = {f"RSI{p}": [] for p in RSI_PERIODS}

    for _, row in df.iterrows():
        t = row["date"].strftime("%Y-%m-%d")
        price.append({
            "time": t,
            "open": _clean(row["open"]),
            "high": _clean(row["high"]),
            "low": _clean(row["low"]),
            "close": _clean(row["close"]),
        })
        volume.append({"time": t, "value": _clean(row["volume"])})

        for w in MA_WINDOWS:
            v = _clean(row[f"MA{w}"])
            if v is not None:
                ma_series[f"MA{w}"].append({"time": t, "value": v})

        for p in RSI_PERIODS:
            v = _clean(row[f"RSI{p}"])
            if v is not None:
                rsi_series[f"RSI{p}"].append({"time": t, "value": v})

    # ---------- 近期走向分析 + 隔日漲跌機率(用 full_df 完整歷史資料統計) ----------
    try:
        narrative = generate_trend_narrative(full_df)
    except Exception as e:
        print(f"  近期走向分析產生失敗({stock_id}): {e}")
        narrative = ""

    try:
        next_day = compute_next_day_probability(full_df)
    except Exception as e:
        print(f"  隔日漲跌機率統計失敗({stock_id}): {e}")
        next_day = {"up_pct": None, "down_pct": None, "sample_size": 0,
                    "match_level": "error", "state_label": "統計時發生錯誤"}

    # ---------- 預測準確率追蹤(持續累積,存成獨立檔案跨執行留存) ----------
    try:
        pred_log_path = os.path.join(OUTPUT_DIR_ABS, f"{stock_id}_predictions.json")
        pred_log = load_log(pred_log_path)
        pred_log = resolve_pending(pred_log, full_df[["date", "close"]])

        latest_date_str = full_df["date"].max().strftime("%Y-%m-%d")
        pred_log = add_new_prediction(pred_log, latest_date_str, next_day)

        save_log(pred_log_path, pred_log)
        track_record = compute_track_record(pred_log)
    except Exception as e:
        print(f"  預測準確率追蹤失敗({stock_id}): {e}")
        track_record = {"total_predictions": 0, "resolved_count": 0, "correct_count": 0,
                         "accuracy_pct": None, "recent": []}

    next_day["track_record"] = track_record
    analysis = {"narrative": narrative, "next_day": next_day}

    # ---------- 三大法人 ----------
    try:
        inst_df = get_institutional_investors(stock_id, start_date, end_date, token=token)
        inst_df = inst_df[inst_df["date"] >= df["date"].min()].reset_index(drop=True)
        # 原始資料單位是「股」,換算成「張」(1張=1000股)較符合台股看盤習慣
        for col in ["foreign_net", "trust_net", "dealer_net", "total_net"]:
            inst_df[col] = (inst_df[col] / 1000).round().astype(int)
        institutional = _series_from_df(inst_df, ["foreign_net", "trust_net", "dealer_net", "total_net"])
    except Exception as e:
        print(f"  三大法人資料抓取失敗({stock_id}): {e}")
        institutional = {"foreign_net": [], "trust_net": [], "dealer_net": [], "total_net": []}

    # ---------- 融資融券 ----------
    try:
        margin_df = get_margin_trading(stock_id, start_date, end_date, token=token)
        margin_df = margin_df[margin_df["date"] >= df["date"].min()].reset_index(drop=True)
        margin = _series_from_df(
            margin_df,
            ["margin_balance", "margin_buy", "margin_sell", "short_balance", "short_buy", "short_sell"],
        )
    except Exception as e:
        print(f"  融資融券資料抓取失敗({stock_id}): {e}")
        margin = {k: [] for k in
                  ["margin_balance", "margin_buy", "margin_sell", "short_balance", "short_buy", "short_sell"]}

    # ---------- 本益比 / 淨值比 / 殖利率(每日資料) ----------
    try:
        val_df = get_valuation_ratios(stock_id, start_date, end_date, token=token)
        val_df = val_df[val_df["date"] >= df["date"].min()].reset_index(drop=True)
        valuation = _series_from_df(val_df, ["PER", "PBR", "dividend_yield"])
    except Exception as e:
        print(f"  本益比/淨值比資料抓取失敗({stock_id}): {e}")
        valuation = {"PER": [], "PBR": [], "dividend_yield": []}

    # ---------- 基本面季報(EPS/毛利率/營益率/ROE/ROA/負債比/現金流) ----------
    try:
        # 財報是季更新,抓近3年份確保有足夠的季數可以裁到 FUNDAMENTALS_QUARTERS 筆
        fund_start_date = (datetime.today() - timedelta(days=3 * 365)).strftime("%Y-%m-%d")

        fin_df = get_financial_statements(stock_id, fund_start_date, end_date, token=token)
        bs_df = get_balance_sheet(stock_id, fund_start_date, end_date, token=token)
        cf_df = get_cash_flow(stock_id, fund_start_date, end_date, token=token)

        merged = fin_df.merge(bs_df, on="date", how="inner").merge(cf_df, on="date", how="left")
        merged["roe"] = merged["net_income"] / merged["equity"] * 100
        merged["roa"] = merged["net_income"] / merged["total_assets"] * 100

        # 大數字換算成「億元」比較好讀
        merged["revenue_yi"] = merged["revenue"] / 1e8
        merged["operating_cash_flow_yi"] = merged["operating_cash_flow"] / 1e8

        merged = merged.sort_values("date").tail(FUNDAMENTALS_QUARTERS).reset_index(drop=True)

        quarters = []
        for _, row in merged.iterrows():
            quarters.append({
                "date": row["date"].strftime("%Y-%m-%d"),
                "eps": _clean(row.get("eps")),
                "revenue_yi": _clean(row.get("revenue_yi")),
                "gross_margin": _clean(row.get("gross_margin")),
                "operating_margin": _clean(row.get("operating_margin")),
                "roe": _clean(row.get("roe")),
                "roa": _clean(row.get("roa")),
                "debt_ratio": _clean(row.get("debt_ratio")),
                "operating_cash_flow_yi": _clean(row.get("operating_cash_flow_yi")),
            })
        fundamentals = {"quarters": quarters}
    except Exception as e:
        print(f"  基本面季報資料抓取失敗({stock_id}): {e}")
        fundamentals = {"quarters": []}

    # ---------- 財經新聞(關鍵字利多/利空比對) ----------
    try:
        news_end_date = end_date
        news_start_date = (datetime.today() - timedelta(days=NEWS_LOOKBACK_DAYS)).strftime("%Y-%m-%d")
        news_df = get_stock_news(stock_id, news_start_date, news_end_date, token=token)
        news = summarize_news(news_df, max_articles=NEWS_MAX_ARTICLES)
    except Exception as e:
        print(f"  財經新聞資料抓取失敗({stock_id}): {e}")
        news = {"total": 0, "positive_count": 0, "negative_count": 0, "neutral_count": 0, "articles": []}

    return {
        "stock_id": stock_id,
        "stock_name": stock_name,
        "updated_at": datetime.now().isoformat(),
        "price": price,
        "volume": volume,
        "ma": ma_series,
        "rsi": rsi_series,
        "institutional": institutional,
        "margin": margin,
        "valuation": valuation,
        "fundamentals": fundamentals,
        "analysis": analysis,
        "news": news,
    }


def main():
    stock_ids = sys.argv[1:] if len(sys.argv) > 1 else STOCK_LIST
    token = os.environ.get("FINMIND_TOKEN", "")  # GitHub Actions Secrets 可帶入

    os.makedirs(OUTPUT_DIR_ABS, exist_ok=True)

    # 股票名稱對照表只需要抓一次(不是每支股票各抓一次),抓不到就用空字典,
    # 前端會 fallback 成只顯示股票代碼
    try:
        name_map = get_stock_names(token=token)
        print(f"已取得股票名稱對照表,共 {len(name_map)} 檔")
    except Exception as e:
        print(f"股票名稱對照表抓取失敗: {e}")
        name_map = {}

    manifest = []
    manifest_names = {}

    for stock_id in stock_ids:
        print(f"抓取並計算 {stock_id} ...")
        stock_name = name_map.get(stock_id)
        try:
            data = build_one(stock_id, token=token, stock_name=stock_name)
        except Exception as e:
            print(f"  跳過 {stock_id},失敗原因: {e}")
            continue

        out_path = os.path.join(OUTPUT_DIR_ABS, f"{stock_id}.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        print(f"  已輸出: {out_path} ({len(data['price'])} 筆)")
        manifest.append(stock_id)
        manifest_names[stock_id] = stock_name

    # 輸出股票清單索引,前端下拉選單會讀這個
    manifest_path = os.path.join(OUTPUT_DIR_ABS, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump({
            "stocks": manifest,
            "stock_names": manifest_names,
            "updated_at": datetime.now().isoformat(),
        }, f, ensure_ascii=False)
    print(f"已輸出股票清單索引: {manifest_path}")


if __name__ == "__main__":
    main()
