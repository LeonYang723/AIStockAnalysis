# scripts/news_sentiment_log.py
"""
新聞情緒的「每日累積記錄」。

跟 prediction_tracker.py 是同樣的設計精神:FinMind的新聞只能查最近幾天,
沒辦法回填歷史,所以只能每天存一筆「今天的新聞氣氛」,一天一天累積下來。
累積到足夠天數(建議至少一年份的交易日,約250筆)之後,
這份歷史就可以拿去餵給 ml_model.py 當作額外特徵。

存放位置: docs/data/{stock_id}_news_sentiment.json
每筆記錄格式:
{
  "date": "2026-07-15",
  "positive_count": 5, "negative_count": 2, "neutral_count": 3, "total": 10,
  "score": 0.3   # (positive-negative)/total,介於 -1(全是利空) ~ +1(全是利多)
}
"""

import json
import os
from config import NEWS_SENTIMENT_LOG_MAX_ENTRIES


def load_log(path: str) -> list:
    """讀取既有的每日新聞情緒記錄,檔案不存在或壞掉就回傳空清單"""
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_log(path: str, log: list) -> None:
    """儲存記錄,只保留最近 NEWS_SENTIMENT_LOG_MAX_ENTRIES 筆,避免檔案無限長大"""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(log[-NEWS_SENTIMENT_LOG_MAX_ENTRIES:], f, ensure_ascii=False)


def compute_daily_score(news_summary: dict) -> float:
    """把當天的利多/利空篇數換算成 -1~+1 的情緒分數"""
    total = news_summary.get("total", 0)
    if total == 0:
        return 0.0
    pos = news_summary.get("positive_count", 0)
    neg = news_summary.get("negative_count", 0)
    return round((pos - neg) / total, 3)


def add_daily_entry(log: list, date_str: str, news_summary: dict) -> list:
    """
    幫今天新增一筆記錄(如果今天已經記錄過就跳過,不會重複累積)。
    """
    log = list(log)  # 淺拷貝,避免直接改到原本傳入的list
    already_has_today = any(entry["date"] == date_str for entry in log)
    if already_has_today:
        return log

    log.append({
        "date": date_str,
        "positive_count": news_summary.get("positive_count", 0),
        "negative_count": news_summary.get("negative_count", 0),
        "neutral_count": news_summary.get("neutral_count", 0),
        "total": news_summary.get("total", 0),
        "score": compute_daily_score(news_summary),
    })
    return log
