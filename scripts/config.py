# scripts/config.py

FINMIND_API_URL = "https://api.finmindtrade.com/api/v4/data"

# 若有 FinMind token 填這裡(可用 GitHub Actions Secrets 帶入環境變數覆蓋,見 build_data.py)
FINMIND_TOKEN = ""

# 想追蹤的股票清單(之後要加股票,改這裡就好)
STOCK_LIST = ["2330", "2317", "2454", "3037", "3026", "8299"]

# 抓取區間:抓近 N 個交易日,避免每次抓全部歷史資料
LOOKBACK_DAYS = 250

# RSI 參數
RSI_PERIODS = [6, 14]

# 均線參數
MA_WINDOWS = [5, 10, 20, 60]

# 基本面資料(EPS/ROE等)要顯示近幾季
FUNDAMENTALS_QUARTERS = 8

# 「隔日漲跌機率」統計要抓近幾年的歷史資料(樣本越多統計越穩定,但抓取會比較慢)
ANALYSIS_LOOKBACK_YEARS = 5

# 同一種技術狀態的歷史樣本數至少要達到這個數字,統計才算可信,不夠會自動退回較寬鬆的分類
ANALYSIS_MIN_SAMPLE = 20

# 財經新聞要抓近幾天
NEWS_LOOKBACK_DAYS = 7

# 當天(最新一天)最多保留幾篇新聞(用時間新舊當作「熱門」的代理指標)
NEWS_TODAY_MAX_ARTICLES = 10

# 全部新聞最多保留幾篇(當天10篇 + 其餘幾天平均分配剩下的扣打)
NEWS_MAX_ARTICLES = 30

# 「隔日漲跌機率」預測準確率追蹤,最多保留幾筆歷史紀錄(每個交易日累積一筆)
TRACK_RECORD_MAX_ENTRIES = 180

# 三大法人連續買超/賣超超過幾天算是「異常」,要標記出來提醒
ANOMALY_STREAK_THRESHOLD = 3

# 輸出JSON存放位置(GitHub Pages 會發布 docs/ 目錄)
OUTPUT_DIR = "docs/data"
