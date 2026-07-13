# scripts/config.py

FINMIND_API_URL = "https://api.finmindtrade.com/api/v4/data"

# 若有 FinMind token 填這裡(可用 GitHub Actions Secrets 帶入環境變數覆蓋,見 build_data.py)
FINMIND_TOKEN = ""

# 想追蹤的股票清單(之後要加股票,改這裡就好)
STOCK_LIST = ["2330", "2317", "2454"]

# 抓取區間:抓近 N 個交易日,避免每次抓全部歷史資料
LOOKBACK_DAYS = 250

# RSI 參數
RSI_PERIODS = [6, 14]

# 均線參數
MA_WINDOWS = [5, 10, 20, 60]

# 基本面資料(EPS/ROE等)要顯示近幾季
FUNDAMENTALS_QUARTERS = 8

# 輸出JSON存放位置(GitHub Pages 會發布 docs/ 目錄)
OUTPUT_DIR = "docs/data"
