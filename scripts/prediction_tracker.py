# scripts/prediction_tracker.py
"""
「隔日漲跌機率」的自我驗證追蹤器。

運作方式:
1. 每次 build_data.py 執行時,先讀取「上次留下來」的預測紀錄檔(存在 docs/data/
   底下,會隨每次 git commit 一起留存,所以能跨執行持續累積)。
2. 檢查裡面還沒驗證過的舊預測,現在有沒有更新的股價資料可以拿來驗證了
   (拿「做預測那天」跟「後面第一個有資料的交易日」的收盤價比較,漲了算對「上漲」,
   跌了算對「下跌」)。
3. 記錄「今天」根據目前技術狀態做出的新預測(如果今天已經記錄過就不重複新增,
   避免同一天手動又觸發一次workflow時，造成重複紀錄)。
4. 統計目前為止「總共驗證過幾次、猜對幾次、準確率多少%」。

這個統計是「這個指標過去準不準」的誠實記錄,不是新的預測方法,樣本數不夠時
(剛上線沒多久)準確率會不穩定,需要累積一段時間才有參考價值。
"""

import json
import os
import pandas as pd
from config import TRACK_RECORD_MAX_ENTRIES


def load_log(path: str) -> list:
    """讀取既有的預測紀錄檔,不存在或壞掉就回傳空清單"""
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_log(path: str, log: list) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(log[-TRACK_RECORD_MAX_ENTRIES:], f, ensure_ascii=False)


def resolve_pending(log: list, price_df: pd.DataFrame) -> list:
    """
    price_df 需有 date(datetime)、close 欄位。
    對log裡面還沒驗證過的預測,檢查現在有沒有更新的股價資料可以驗證了。
    """
    df = price_df.copy()
    df["date_str"] = df["date"].dt.strftime("%Y-%m-%d")
    close_map = dict(zip(df["date_str"], df["close"]))
    all_dates_sorted = sorted(close_map.keys())

    for entry in log:
        if entry.get("resolved"):
            continue

        predict_date = entry["predict_date"]
        if predict_date not in close_map:
            continue
        predict_close = close_map[predict_date]

        later_dates = [d for d in all_dates_sorted if d > predict_date]
        if not later_dates:
            continue  # 還沒有更新的交易日資料,先跳過,之後再驗證

        target_date = later_dates[0]
        target_close = close_map[target_date]
        actual_direction = "up" if target_close > predict_close else "down"

        entry["target_date"] = target_date
        entry["actual_direction"] = actual_direction
        entry["correct"] = (actual_direction == entry["predicted_direction"])
        entry["resolved"] = True

    return log


def add_new_prediction(log: list, predict_date: str, next_day_result: dict) -> list:
    """新增今天的預測紀錄。如果今天已經記錄過,就不重複新增。"""
    if any(e["predict_date"] == predict_date for e in log):
        return log

    up_pct = next_day_result.get("up_pct")
    if up_pct is None:
        return log  # 樣本不足時沒有做出有效預測,不記錄

    predicted_direction = "up" if up_pct >= 50 else "down"

    log.append({
        "predict_date": predict_date,
        "predicted_direction": predicted_direction,
        "up_pct": up_pct,
        "down_pct": next_day_result.get("down_pct"),
        "state_label": next_day_result.get("state_label"),
        "target_date": None,
        "actual_direction": None,
        "correct": None,
        "resolved": False,
    })
    return log


def compute_track_record(log: list) -> dict:
    """統計目前為止的驗證結果,回傳前端要用的摘要資料"""
    resolved = [e for e in log if e.get("resolved")]
    correct = [e for e in resolved if e.get("correct")]
    total_resolved = len(resolved)
    accuracy_pct = round(len(correct) / total_resolved * 100, 1) if total_resolved > 0 else None

    # 這裡回傳「全部」已驗證記錄(不是只取近10筆),讓前端可以做日期選單查詢
    recent = sorted(resolved, key=lambda e: e["predict_date"], reverse=True)

    return {
        "total_predictions": len(log),
        "resolved_count": total_resolved,
        "correct_count": len(correct),
        "accuracy_pct": accuracy_pct,
        "recent": recent,
    }
