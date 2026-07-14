# scripts/news_analysis.py
"""
新聞標題的利多/利空關鍵字比對。

重要限制(會同步顯示在前端畫面上):
這不是真正理解新聞內容的AI摘要,只是單純數「標題裡出現了幾個利多/利空關鍵字」,
屬於很粗略的字面比對。常見誤判狀況包括:
  - 反諷、疑問句、雙重否定("不看空"其實偏多,但會被當成利空字比對到)
  - 財報文章常同時提到"成長"和"衰退"(例如"A產品成長、B產品衰退"),導致誤判成中性
  - 新聞標題本身可能只是中性描述,沒有明顯情緒字眼
使用時應該把它當作「粗略的關鍵字統計」,不是新聞情緒的正確判讀。
"""

import pandas as pd

# 財經利多關鍵字(常見於正面新聞標題)
POSITIVE_KEYWORDS = [
    "大漲", "上漲", "漲停", "創高", "創新高", "突破",
    "成長", "增長", "營收成長", "獲利成長", "獲利創新高", "優於預期", "超乎預期",
    "看好", "看多", "樂觀", "強勁", "暢旺", "熱銷", "旺季", "需求強勁",
    "調升", "上修", "目標價調升", "目標價上修", "買超", "外資買超", "加碼",
    "擴產", "擴大投資", "新訂單", "大單", "簽約", "合作", "併購",
    "轉盈", "轉虧為盈", "配息", "配發股利", "每股盈餘成長",
]

# 財經利空關鍵字(常見於負面新聞標題)
NEGATIVE_KEYWORDS = [
    "大跌", "下跌", "跌停", "創低", "創新低", "重挫", "崩跌",
    "衰退", "下滑", "營收衰退", "獲利衰退", "不如預期", "低於預期",
    "看空", "看淡", "悲觀", "疲弱", "疲軟", "淡季", "需求疲弱", "需求放緩",
    "調降", "下修", "目標價調降", "目標價下修", "賣超", "外資賣超", "減碼",
    "減產", "裁員", "資遣", "違約", "罰款", "訴訟", "求償", "停工", "停產",
    "虧損", "轉虧", "財報未達標", "警訊", "風險", "疑慮", "下市", "重整",
]


def classify_news_title(title: str) -> dict:
    """
    對單一標題做關鍵字比對,回傳:
    {"sentiment": "利多"/"利空"/"中性", "positive_hits": [...], "negative_hits": [...]}
    """
    if not title:
        return {"sentiment": "中性", "positive_hits": [], "negative_hits": []}

    positive_hits = [kw for kw in POSITIVE_KEYWORDS if kw in title]
    negative_hits = [kw for kw in NEGATIVE_KEYWORDS if kw in title]

    if len(positive_hits) > len(negative_hits):
        sentiment = "利多"
    elif len(negative_hits) > len(positive_hits):
        sentiment = "利空"
    else:
        sentiment = "中性"

    return {"sentiment": sentiment, "positive_hits": positive_hits, "negative_hits": negative_hits}


def select_balanced_articles(df: pd.DataFrame, today_max: int, total_max: int) -> pd.DataFrame:
    """
    從新聞資料裡挑選要顯示的篇數,採用「當天優先、其餘平均分配」邏輯:
      1. 最新一天(通常是今天)最多保留 today_max 篇(依時間新舊排序,當作熱門度的代理指標)
      2. 剩餘扣打(total_max - 當天實際篇數)平均分配給其餘各天,
         分配不整除時,前面幾天多分1篇,盡量不浪費扣打。

    df 需有 date 欄位(datetime),且已經依日期新到舊排序。
    """
    if df.empty:
        return df

    df = df.copy()
    df["_day"] = df["date"].dt.date
    days = list(dict.fromkeys(df["_day"]))  # 保留原本新到舊的順序,同時去重
    latest_day = days[0]
    other_days = days[1:]

    latest_group = df[df["_day"] == latest_day].head(today_max)
    remaining_budget = max(total_max - len(latest_group), 0)

    selected_parts = [latest_group]
    if other_days and remaining_budget > 0:
        per_day_quota = remaining_budget // len(other_days)
        extra = remaining_budget % len(other_days)
        for i, day in enumerate(other_days):
            quota = per_day_quota + (1 if i < extra else 0)
            if quota <= 0:
                continue
            selected_parts.append(df[df["_day"] == day].head(quota))

    result = pd.concat(selected_parts).sort_values("date", ascending=False).reset_index(drop=True)
    return result.drop(columns=["_day"])


def summarize_news(df: pd.DataFrame, max_articles: int = 30, today_max_articles: int = 10) -> dict:
    """
    對一批新聞(需有 date/title/source/link 欄位)做關鍵字比對統計。
    篩選規則: 最新一天最多 today_max_articles 篇,其餘平均分配剩下的扣打。
    回傳:
    {
      "total": 總篇數,
      "positive_count": 利多篇數, "negative_count": 利空篇數, "neutral_count": 中性篇數,
      "articles": [{"date":.., "title":.., "source":.., "link":.., "sentiment":..}, ...]
    }
    """
    articles = []
    positive_count = 0
    negative_count = 0
    neutral_count = 0

    subset = select_balanced_articles(df, today_max=today_max_articles, total_max=max_articles)
    for _, row in subset.iterrows():
        result = classify_news_title(row["title"])
        sentiment = result["sentiment"]
        if sentiment == "利多":
            positive_count += 1
        elif sentiment == "利空":
            negative_count += 1
        else:
            neutral_count += 1

        articles.append({
            "date": row["date"].strftime("%Y-%m-%d %H:%M"),
            "title": row["title"],
            "source": row.get("source"),
            "link": row.get("link"),
            "sentiment": sentiment,
        })

    return {
        "total": len(articles),
        "positive_count": positive_count,
        "negative_count": negative_count,
        "neutral_count": neutral_count,
        "articles": articles,
    }
