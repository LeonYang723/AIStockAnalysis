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

    resp = requests.get(FINMIND_API_URL, params=params, timeout=30)
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


def get_stock_names(token: str = None) -> dict:
    """
    取得「股票代碼 -> 公司名稱」對照表(TaiwanStockInfo 是靜態參考表,
    一次抓全市場即可,不需要 data_id 也不需要日期區間)。
    回傳: {"2330": "台積電", "2317": "鴻海", ...}
    """
    params = {"dataset": "TaiwanStockInfo"}
    use_token = token or FINMIND_TOKEN
    if use_token:
        params["token"] = use_token

    resp = requests.get(FINMIND_API_URL, params=params, timeout=20)
    resp.raise_for_status()
    payload = resp.json()

    if payload.get("status") != 200:
        raise RuntimeError(f"FinMind API 錯誤: {payload.get('msg')}")

    df = pd.DataFrame(payload["data"])
    if df.empty:
        raise ValueError("查無 TaiwanStockInfo 資料")

    # 同一股票代碼可能因為市場別(上市/上櫃)重複列出,取第一筆即可
    df = df.drop_duplicates(subset="stock_id", keep="first")
    return dict(zip(df["stock_id"], df["stock_name"]))


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
    df = _fetch("TaiwanStockInstitutionalInvestorsBuySell", stock_id, start_date, end_date, token)
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


def get_valuation_ratios(stock_id: str, start_date: str, end_date: str, token: str = None) -> pd.DataFrame:
    """
    取得本益比(P/E)、淨值比(P/B)、殖利率。
    FinMind 這個資料集已經幫忙算好了,不用自己拿股價/EPS重算。
    回傳欄位: date, PER, PBR, dividend_yield
    """
    df = _fetch("TaiwanStockPER", stock_id, start_date, end_date, token)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    return df[["date", "PER", "PBR", "dividend_yield"]]


def _pick_series(df: pd.DataFrame, candidates: list, label: str, exclude: list = None) -> pd.DataFrame:
    """
    財報類資料集是長格式(每個會計科目一列,用 type 欄位區分),
    但 FinMind 官方文件沒有列出每個資料集完整的 type 命名,
    這裡依序嘗試候選關鍵字:先找完全相符,找不到再用模糊比對(contains)。
    exclude: 模糊比對時要排除的關鍵字(避免抓到字串重疊但意義不同的科目,
             例如找「Equity」時可能誤抓到「TotalLiabilitiesAndEquity」)。
    如果都找不到,把目前資料裡實際有哪些 type 印出來,方便除錯調整候選清單。
    """
    exclude = exclude or []

    for keyword in candidates:
        exact = df[df["type"] == keyword]
        if not exact.empty:
            return exact[["date", "value"]].rename(columns={"value": label})

    for keyword in candidates:
        matched = df[df["type"].str.contains(keyword, case=False, na=False)]
        for ex in exclude:
            matched = matched[~matched["type"].str.contains(ex, case=False, na=False)]
        if not matched.empty:
            picked_type = matched["type"].iloc[0]
            sub = df[df["type"] == picked_type][["date", "value"]]
            return sub.rename(columns={"value": label})

    available = sorted(df["type"].unique().tolist())
    raise ValueError(f"找不到符合 {candidates} 的科目(欄位:{label})。實際可用的type: {available}")


def get_financial_statements(stock_id: str, start_date: str, end_date: str, token: str = None) -> pd.DataFrame:
    """
    取得季報損益表相關數字: EPS、營收、毛利、營業利益、稅後淨利,
    並計算毛利率、營益率。

    回傳欄位: date, eps, revenue, gross_profit, operating_income, net_income,
              gross_margin(%), operating_margin(%)
    """
    df = _fetch("TaiwanStockFinancialStatements", stock_id, start_date, end_date, token)
    df["date"] = pd.to_datetime(df["date"])

    eps = _pick_series(df, ["EPS"], "eps")
    revenue = _pick_series(df, ["Revenue"], "revenue")
    gross_profit = _pick_series(df, ["GrossProfit", "GrossProfitLoss"], "gross_profit")
    operating_income = _pick_series(df, ["OperatingIncome"], "operating_income")
    net_income = _pick_series(df, ["IncomeAfterTaxes", "ProfitLoss"], "net_income")

    merged = eps.merge(revenue, on="date", how="outer") \
                .merge(gross_profit, on="date", how="outer") \
                .merge(operating_income, on="date", how="outer") \
                .merge(net_income, on="date", how="outer") \
                .sort_values("date").reset_index(drop=True)

    merged["gross_margin"] = merged["gross_profit"] / merged["revenue"] * 100
    merged["operating_margin"] = merged["operating_income"] / merged["revenue"] * 100
    return merged


def get_balance_sheet(stock_id: str, start_date: str, end_date: str, token: str = None) -> pd.DataFrame:
    """
    取得資產負債表相關數字: 總資產、股東權益,並計算總負債與負債比。

    注意:總負債不直接抓 FinMind 的「TotalLiabilities」科目,
    因為之前實測發現這個科目的模糊比對容易誤抓到「TotalLiabilitiesAndEquity」
    (總負債+權益,依會計恆等式一定等於總資產),導致負債比永遠算成100%。
    改用會計恆等式反推:總負債 = 總資產 - 股東權益,不管 FinMind 那邊科目怎麼命名都準確。

    回傳欄位: date, total_assets, equity, total_liabilities, debt_ratio(%)
    """
    df = _fetch("TaiwanStockBalanceSheet", stock_id, start_date, end_date, token)
    df["date"] = pd.to_datetime(df["date"])

    total_assets = _pick_series(df, ["TotalAssets"], "total_assets")
    equity = _pick_series(
        df, ["EquityAttributableToOwnersOfParent", "TotalEquity", "Equity"], "equity",
        exclude=["Liabilities"],
    )

    merged = total_assets.merge(equity, on="date", how="outer") \
                          .sort_values("date").reset_index(drop=True)
    merged["total_liabilities"] = merged["total_assets"] - merged["equity"]
    merged["debt_ratio"] = merged["total_liabilities"] / merged["total_assets"] * 100
    return merged


def get_cash_flow(stock_id: str, start_date: str, end_date: str, token: str = None) -> pd.DataFrame:
    """取得現金流量表的營業活動現金流。回傳欄位: date, operating_cash_flow"""
    df = _fetch("TaiwanStockCashFlowsStatement", stock_id, start_date, end_date, token)
    df["date"] = pd.to_datetime(df["date"])

    op_cf = _pick_series(
        df, ["CashFlowsFromOperatingActivities", "NetCashFlowsFromOperatingActivities"],
        "operating_cash_flow",
    )
    return op_cf.sort_values("date").reset_index(drop=True)

# 註: 曾嘗試加入「主力買賣(券商分點)」功能,對應 FinMind 的
# TaiwanStockTradingDailyReport 資料集,但該資料集是付費 Sponsor 方案專屬,
# 免費/一般註冊帳號的 token 都無法存取(會回傳 400)。
# 如果之後訂閱了 FinMind Sponsor 方案,可以參考官方文件重新加回:
# https://finmind.github.io/tutor/TaiwanMarket/Chip/
