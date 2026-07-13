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
