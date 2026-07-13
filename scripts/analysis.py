# scripts/analysis.py
"""
「近期走向」和「隔日漲跌機率」都不是機器學習預測,而是:
  1. 近期走向: 依現有技術指標(均線排列、RSI區間、近期漲跌幅)組成規則式的描述文字
  2. 隔日漲跌機率: 統計「歷史上處於相同技術狀態時,隔天實際上漲/下跌的比例」

這兩者都是透明、可回頭驗證的統計方法,不是黑箱預測,也不構成投資建議。
"""

import pandas as pd
from config import ANALYSIS_MIN_SAMPLE


def classify_rsi(rsi) -> str:
    """把RSI數值分類成 超賣 / 中性 / 超買"""
    if rsi is None or pd.isna(rsi):
        return None
    if rsi < 30:
        return "超賣"
    if rsi > 70:
        return "超買"
    return "中性"


def classify_ma_trend(close, ma5, ma20, ma60) -> str:
    """依均線排列分類成 多頭排列 / 空頭排列 / 盤整"""
    if any(v is None or pd.isna(v) for v in [close, ma5, ma20, ma60]):
        return None
    if ma5 > ma20 > ma60 and close > ma5:
        return "多頭排列"
    if ma5 < ma20 < ma60 and close < ma5:
        return "空頭排列"
    return "盤整"


def generate_trend_narrative(df: pd.DataFrame) -> str:
    """
    依最新一筆資料的技術指標,產生近期走向的規則式描述文字。
    df 需有欄位: close, MA5, MA20, MA60, RSI14,已依日期排序(最後一列是最新)。
    """
    latest = df.iloc[-1]
    rsi_state = classify_rsi(latest.get("RSI14"))
    ma_state = classify_ma_trend(latest["close"], latest.get("MA5"), latest.get("MA20"), latest.get("MA60"))

    def pct_change_n(n):
        if len(df) <= n:
            return None
        prev = df.iloc[-1 - n]["close"]
        if prev == 0 or pd.isna(prev):
            return None
        return (latest["close"] - prev) / prev * 100

    chg5 = pct_change_n(5)
    chg20 = pct_change_n(20)

    sentences = []

    if ma_state == "多頭排列":
        sentences.append("均線呈現多頭排列(短期均線在長期均線之上,股價位於均線之上),近期趨勢偏多。")
    elif ma_state == "空頭排列":
        sentences.append("均線呈現空頭排列(短期均線在長期均線之下,股價位於均線之下),近期趨勢偏空。")
    else:
        sentences.append("均線尚未形成明確排列,近期呈現盤整格局。")

    if rsi_state == "超買" and latest.get("RSI14") is not None:
        sentences.append(f"RSI14 為 {latest['RSI14']:.1f},處於超買區間,短線有拉回修正的可能。")
    elif rsi_state == "超賣" and latest.get("RSI14") is not None:
        sentences.append(f"RSI14 為 {latest['RSI14']:.1f},處於超賣區間,短線有反彈的可能。")
    elif rsi_state == "中性" and latest.get("RSI14") is not None:
        sentences.append(f"RSI14 為 {latest['RSI14']:.1f},處於中性區間,尚未出現明顯超買或超賣訊號。")

    if chg5 is not None:
        d5 = "上漲" if chg5 >= 0 else "下跌"
        sentences.append(f"近5個交易日{d5} {abs(chg5):.1f}%。")
    if chg20 is not None:
        d20 = "上漲" if chg20 >= 0 else "下跌"
        sentences.append(f"近20個交易日{d20} {abs(chg20):.1f}%。")

    return "".join(sentences)


def compute_next_day_probability(df: pd.DataFrame) -> dict:
    """
    用「歷史相似技術狀態下,隔日實際漲跌的歷史比例」估算漲跌機率。
    df 需有欄位: close, MA5, MA20, MA60, RSI14,依日期由舊到新排序,筆數越多統計越可靠。

    比對邏輯(由嚴格到寬鬆,樣本不足會自動退回):
      1. RSI狀態 + 均線排列 都相符
      2. 樣本不足 -> 只看RSI狀態
      3. 還是不足 -> 用全部歷史資料
    """
    work = df.copy().reset_index(drop=True)
    work["rsi_state"] = work["RSI14"].apply(classify_rsi)
    work["ma_state"] = work.apply(
        lambda r: classify_ma_trend(r["close"], r.get("MA5"), r.get("MA20"), r.get("MA60")), axis=1
    )
    work["next_close"] = work["close"].shift(-1)
    work["next_up"] = work["next_close"] > work["close"]

    valid = work.dropna(subset=["rsi_state", "ma_state", "next_close"])

    latest = df.iloc[-1]
    cur_rsi_state = classify_rsi(latest.get("RSI14"))
    cur_ma_state = classify_ma_trend(latest["close"], latest.get("MA5"), latest.get("MA20"), latest.get("MA60"))

    if cur_rsi_state is None or cur_ma_state is None:
        return {
            "up_pct": None, "down_pct": None, "sample_size": 0,
            "match_level": "insufficient_data", "state_label": "目前技術指標資料不足,無法統計",
        }

    matched = valid[(valid["rsi_state"] == cur_rsi_state) & (valid["ma_state"] == cur_ma_state)]
    match_level = "rsi_and_ma"

    if len(matched) < ANALYSIS_MIN_SAMPLE:
        matched = valid[valid["rsi_state"] == cur_rsi_state]
        match_level = "rsi_only"

    if len(matched) < ANALYSIS_MIN_SAMPLE:
        matched = valid
        match_level = "all_history"

    sample_size = len(matched)
    if sample_size == 0:
        return {
            "up_pct": None, "down_pct": None, "sample_size": 0,
            "match_level": "insufficient_data", "state_label": "歷史樣本不足,無法統計",
        }

    up_pct = round(float(matched["next_up"].sum()) / sample_size * 100, 1)
    down_pct = round(100 - up_pct, 1)

    state_label_map = {
        "rsi_and_ma": f"RSI{cur_rsi_state} + 均線{cur_ma_state}",
        "rsi_only": f"RSI{cur_rsi_state}(符合「RSI+均線」雙條件的樣本不足,已退回只比對RSI狀態)",
        "all_history": "符合條件的歷史樣本不足,已退回採用全部歷史資料的平均漲跌比例",
    }

    return {
        "up_pct": up_pct,
        "down_pct": down_pct,
        "sample_size": sample_size,
        "match_level": match_level,
        "state_label": state_label_map[match_level],
    }
