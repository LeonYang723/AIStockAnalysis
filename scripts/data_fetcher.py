# scripts/data_fetcher.py

import requests
import pandas as pd
from config import FINMIND_API_URL, FINMIND_TOKEN


def _fetch(dataset: str, data_id: str, start_date: str, end_date: str, token: str = None) -> pd.DataFrame:
    params = {
        "dataset": dataset,
        "data_id": data_id,
        "start_date": start_date,
        "end_date": end_date,
    }
    use_token = token or FINMIND_TOKEN
    if use_token:
        params["token"] = use_token

    resp = requests.get(FINMIND_API_URL, params=params, timeout=15)
    resp.raise_for_status()
    payload = resp.json()

    if payload.get("status") != 200:
        raise RuntimeError(f"FinMind API 錯誤: {payload.get('msg')}")

    df = pd.DataFrame(payload["data"])
    if df.empty:
        raise ValueError(f"查無資料: dataset={dataset}, data_id={data_id}")
    return df


def get_stock_price(stock_id: str, start_date: str, end_date: str, token: str = None) -> pd.DataFrame:
    """取得日K線,回傳欄位: date, open, high, low, close, volume"""
    df = _fetch("TaiwanStockPrice", stock_id, start_date, end_date, token)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    df = df.rename(columns={"max": "high", "min": "low", "Trading_Volume": "volume"})
    return df[["date", "open", "high", "low", "close", "volume"]]


def get_institutional_investors(stock_id: str, start_date: str, end_date: str, token: str = None) -> pd.DataFrame:
    """
    取得三大法人買賣超。
    原始資料是「每天 x 每個細分法人類別」一列(long format),
    這裡整理成寬表,並依照台股慣例把細分類別合併成外資/投信/自營商三大類:
      - 外資 = Foreign_Investor + Foreign_Dealer_Self
      - 投信 = Investment_Trust
      - 自營商 = Dealer_self + Dealer_Hedging

    回傳欄位: date, foreign_net, trust_net, dealer_net, total_net (單位:股)
    """
    df = _fetch("InstitutionalInvestorsBuySell", stock_id, start_date, end_date, token)
    df["date"] = pd.to_datetime(df["date"])
    df["net"] = df["buy"].astype(float) - df["sell"].astype(float)

    pivot = df.pivot_table(index="date", columns="name", values="net", aggfunc="sum").fillna(0)

    foreign_cols = [c for c in ["Foreign_Investor", "Foreign_Dealer_Self"] if c in pivot.columns]
    dealer_cols = [c for c in ["Dealer_self", "Dealer_Hedging"] if c in pivot.columns]
    trust_cols = [c for c in ["Investment_Trust"] if c in pivot.columns]

    result = pd.DataFrame(index=pivot.index)
    result["foreign_net"] = pivot[foreign_cols].sum(axis=1) if foreign_cols else 0
    result["trust_net"] = pivot[trust_cols].sum(axis=1) if trust_cols else 0
    result["dealer_net"] = pivot[dealer_cols].sum(axis=1) if dealer_cols else 0
    result["total_net"] = result["foreign_net"] + result["trust_net"] + result["dealer_net"]

    result = result.reset_index().sort_values("date").reset_index(drop=True)
    return result


def get_margin_trading(stock_id: str, start_date: str, end_date: str, token: str = None) -> pd.DataFrame:
    """
    取得融資融券資料。
    回傳欄位: date, margin_balance(融資餘額), margin_buy(融資買進), margin_sell(融資賣出),
              short_balance(融券餘額), short_buy(融券買進), short_sell(融券賣出)
    """
    df = _fetch("TaiwanStockMarginPurchaseShortSale", stock_id, start_date, end_date, token)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)

    df = df.rename(columns={
        "MarginPurchaseTodayBalance": "margin_balance",
        "MarginPurchaseBuy": "margin_buy",
        "MarginPurchaseSell": "margin_sell",
        "ShortSaleTodayBalance": "short_balance",
        "ShortSaleBuy": "short_buy",
        "ShortSaleSell": "short_sell",
    })
    cols = ["date", "margin_balance", "margin_buy", "margin_sell", "short_balance", "short_buy", "short_sell"]
    return df[cols]
