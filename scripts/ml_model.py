# scripts/ml_model.py
"""
機器學習版的隔日漲跌預測(實驗性功能)。

跟「歷史統計法」(analysis.py)並存,兩邊各自透過 prediction_tracker
累積實際命中率,跑一段時間後可以客觀比較哪個方法比較準。

方法說明:
- 模型: 邏輯迴歸(LogisticRegression),刻意選最簡單的模型,
  降低在歷史資料上過度配適(overfitting)的風險。
- 特徵: 全部由既有的股價資料衍生(報酬率、RSI、均線乖離率、均線排列、量比),
  不需要多打任何API。
- 驗證: 用「時間序列切分」— 前面的資料訓練、最後60個交易日驗證,
  絕對不能隨機打散(隨機切分會讓模型偷看到未來資料,回測準確率會虛高)。
  回測準確率會誠實顯示在畫面上,讓使用者知道這個模型歷史上大概準幾成。

重要提醒(也會顯示在前端):
股價短期漲跌非常接近隨機,任何方法(包括這個模型)的長期準確率
通常都只在50%上下徘徊,這個功能主要是技術實驗性質,不是可靠的交易訊號。
"""

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline

# 用最後幾個交易日做回測驗證(不參與第一次訓練,當作誠實的考卷)
BACKTEST_DAYS = 60

# 至少要有幾筆有效樣本才訓練(太少會不穩定)
MIN_TRAIN_SAMPLES = 200


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    從既有的股價資料(close/volume/MA/RSI欄位)衍生模型特徵。
    所有特徵都只用「當天以前」的資訊,不能摻入任何未來資料。
    """
    feat = pd.DataFrame(index=df.index)
    close = df["close"]
    volume = df["volume"]

    # 動能: 近1/5/20日報酬率
    feat["ret_1"] = close.pct_change(1)
    feat["ret_5"] = close.pct_change(5)
    feat["ret_20"] = close.pct_change(20)

    # RSI (縮到0-1之間)
    feat["rsi14"] = df["RSI14"] / 100
    feat["rsi6"] = df["RSI6"] / 100

    # 均線乖離率: 股價偏離均線的程度
    feat["bias_ma5"] = (close - df["MA5"]) / df["MA5"]
    feat["bias_ma20"] = (close - df["MA20"]) / df["MA20"]
    feat["bias_ma60"] = (close - df["MA60"]) / df["MA60"]

    # 均線排列(多頭/空頭的0-1旗標)
    feat["ma5_gt_ma20"] = (df["MA5"] > df["MA20"]).astype(float)
    feat["ma20_gt_ma60"] = (df["MA20"] > df["MA60"]).astype(float)

    # 量比: 今天成交量相對近20日均量
    vol_ma20 = volume.rolling(20).mean()
    feat["vol_ratio"] = volume / vol_ma20

    return feat


def train_and_predict(df: pd.DataFrame) -> dict:
    """
    訓練模型並預測「最新一個交易日的隔天」漲跌機率。
    df 需含欄位: date, close, volume, MA5, MA20, MA60, RSI6, RSI14,由舊到新排序。

    回傳格式與統計法一致(up_pct/down_pct/state_label),可以直接餵給 prediction_tracker。
    """
    feat = build_features(df)
    target = (df["close"].shift(-1) > df["close"]).astype(float)
    target[df["close"].shift(-1).isna()] = np.nan  # 最新一天沒有「明天」,不能當訓練樣本

    combined = pd.concat([feat, target.rename("target")], axis=1).dropna()
    if len(combined) < MIN_TRAIN_SAMPLES:
        raise ValueError(f"有效訓練樣本只有{len(combined)}筆,少於下限{MIN_TRAIN_SAMPLES},不訓練")

    feature_cols = list(feat.columns)
    X = combined[feature_cols].values
    y = combined["target"].values.astype(int)

    # ---- 時間序列切分回測(前面訓練,最後BACKTEST_DAYS天當考卷) ----
    split = len(combined) - BACKTEST_DAYS
    model = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000))
    model.fit(X[:split], y[:split])
    backtest_accuracy = round(float(model.score(X[split:], y[split:])) * 100, 1)

    # ---- 用全部歷史重新訓練,對最新一天做預測 ----
    model.fit(X, y)

    latest_feat = feat.iloc[[-1]].values
    if np.isnan(latest_feat).any():
        raise ValueError("最新一天的特徵含有缺值,無法預測")

    prob_up = float(model.predict_proba(latest_feat)[0][1])
    up_pct = round(prob_up * 100, 1)
    down_pct = round(100 - up_pct, 1)

    return {
        "up_pct": up_pct,
        "down_pct": down_pct,
        "sample_size": len(combined),
        "backtest_accuracy": backtest_accuracy,
        "backtest_days": BACKTEST_DAYS,
        "state_label": f"邏輯迴歸 · 訓練樣本{len(combined)}天 · 近{BACKTEST_DAYS}天回測準確率{backtest_accuracy}%",
    }
