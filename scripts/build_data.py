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

from config import STOCK_LIST, LOOKBACK_DAYS, RSI_PERIODS, MA_WINDOWS, OUTPUT_DIR
from data_fetcher import (
    get_stock_price, get_institutional_investors, get_margin_trading, get_broker_net_trading,
)
from indicators import add_moving_averages, add_rsi_columns

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


def build_one(stock_id: str, token: str = None) -> dict:
    end_date = datetime.today().strftime("%Y-%m-%d")
    start_date = (datetime.today() - timedelta(days=int(LOOKBACK_DAYS * 1.6))).strftime("%Y-%m-%d")
    # *1.6 概略換算交易日 vs 日曆日,確保抓到足夠的交易日數量

    df = get_stock_price(stock_id, start_date, end_date, token=token)
    df = add_moving_averages(df, windows=MA_WINDOWS)
    df = add_rsi_columns(df, periods=RSI_PERIODS)

    # 只保留最近 LOOKBACK_DAYS 個交易日,避免檔案太大
    df = df.tail(LOOKBACK_DAYS).reset_index(drop=True)

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

    # ---------- 主力買賣(券商分點,只有最新交易日的排行榜) ----------
    try:
        latest_date = df["date"].max().strftime("%Y-%m-%d")
        broker_df = get_broker_net_trading(stock_id, latest_date, token=token)

        # 換算成「張」,並取前5買超、前5賣超
        broker_df["net_lots"] = (broker_df["net"] / 1000).round().astype(int)
        top_buy = broker_df.head(5)
        top_sell = broker_df.tail(5).sort_values("net_lots")

        main_force = {
            "date": latest_date,
            "top_buy": [
                {"trader": row["securities_trader"], "net": int(row["net_lots"])}
                for _, row in top_buy.iterrows()
            ],
            "top_sell": [
                {"trader": row["securities_trader"], "net": int(row["net_lots"])}
                for _, row in top_sell.iterrows()
            ],
        }
    except Exception as e:
        print(f"  主力買賣資料抓取失敗({stock_id}): {e}")
        main_force = {"date": None, "top_buy": [], "top_sell": []}

    return {
        "stock_id": stock_id,
        "updated_at": datetime.now().isoformat(),
        "price": price,
        "volume": volume,
        "ma": ma_series,
        "rsi": rsi_series,
        "institutional": institutional,
        "margin": margin,
        "main_force": main_force,
    }


def main():
    stock_ids = sys.argv[1:] if len(sys.argv) > 1 else STOCK_LIST
    token = os.environ.get("FINMIND_TOKEN", "")  # GitHub Actions Secrets 可帶入

    os.makedirs(OUTPUT_DIR_ABS, exist_ok=True)
    manifest = []

    for stock_id in stock_ids:
        print(f"抓取並計算 {stock_id} ...")
        try:
            data = build_one(stock_id, token=token)
        except Exception as e:
            print(f"  跳過 {stock_id},失敗原因: {e}")
            continue

        out_path = os.path.join(OUTPUT_DIR_ABS, f"{stock_id}.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        print(f"  已輸出: {out_path} ({len(data['price'])} 筆)")
        manifest.append(stock_id)

    # 輸出股票清單索引,前端下拉選單會讀這個
    manifest_path = os.path.join(OUTPUT_DIR_ABS, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump({
            "stocks": manifest,
            "updated_at": datetime.now().isoformat(),
        }, f, ensure_ascii=False)
    print(f"已輸出股票清單索引: {manifest_path}")


if __name__ == "__main__":
    main()
