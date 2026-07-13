# 台股AI分析 - GitHub Pages 前端原型

架構:GitHub Actions 排程抓資料 → 存成 JSON → GitHub Pages 靜態網站用
[lightweight-charts](https://github.com/tradingview/lightweight-charts)(TradingView開源的圖表庫)
渲染互動式K線 + RSI圖表。

```
repo/
├── .github/workflows/update_data.yml   # 排程:每個交易日自動抓資料
├── scripts/
│   ├── config.py          # 股票清單、抓取參數
│   ├── data_fetcher.py    # 呼叫 FinMind API
│   ├── indicators.py      # RSI / 均線計算
│   └── build_data.py      # 主程式:輸出 docs/data/*.json
├── docs/                   # GitHub Pages 發布目錄
│   ├── index.html
│   ├── style.css
│   ├── app.js              # lightweight-charts 渲染邏輯
│   └── data/                # 由 GitHub Actions 自動產生/更新
│       ├── manifest.json    # 股票清單索引
│       └── {股票代號}.json
└── requirements.txt
```

## 部署步驟

1. **建立 GitHub repo**,把這些檔案 push 上去。

2. **設定 GitHub Pages**
   Repo → Settings → Pages → Source 選 `Deploy from a branch`,
   Branch 選 `main`,資料夾選 `/docs`,存檔。
   幾分鐘後就能用 `https://<你的帳號>.github.io/<repo名稱>/` 打開網站。

3. **(可選)申請 FinMind token 並設定 Secret**
   如果免費額度不夠用,到 [FinMind官網](https://finmindtrade.com/) 註冊拿 token,
   然後在 repo → Settings → Secrets and variables → Actions,
   新增一個 secret,名稱設為 `FINMIND_TOKEN`,值貼上你的 token。
   Workflow 會自動讀取這個 secret(見 `update_data.yml` 裡的 `env:` 設定)。

4. **手動觸發第一次資料抓取**
   Repo → Actions → 左側選 `Update Stock Data` → 右側 `Run workflow` 按鈕。
   跑完之後 `docs/data/` 下會自動 commit 出 JSON 檔案,GitHub Pages 就會顯示資料了。
   之後每個交易日下午會自動跑一次(見下方排程說明)。

## 排程時間

`.github/workflows/update_data.yml` 目前設定:每週一到五 台灣時間 14:30 自動執行一次
(GitHub Actions 的排程是 UTC 時間,可能會有幾分鐘延遲,屬正常現象)。
要改時間的話,調整 workflow 裡的 cron 設定即可。

## 想追蹤的股票清單

改 `scripts/config.py` 裡的 `STOCK_LIST`,例如:

```python
STOCK_LIST = ["2330", "2317", "2454", "2308"]
```

改完 push 上去,下次排程跑就會自動抓新加的股票。

## 本地測試(不用等排程,先在自己電腦跑跑看)

```bash
pip install -r requirements.txt
python scripts/build_data.py 2330
```

跑完後 `docs/data/2330.json` 會有資料,接著可以用本地伺服器預覽網頁:

```bash
cd docs
python3 -m http.server 8000
```

瀏覽器開 `http://localhost:8000` 應該就能看到互動圖表。

## 前端功能

- 上拉選單切換股票(讀 `manifest.json` 自動列出)
- K線圖疊加 MA5/10/20/60(依資料是否存在自動顯示對應均線)
- RSI6 / RSI14 副圖,跟K線圖的時間軸同步縮放/拖曳
- 深色主題,紅漲綠跌(台股習慣)

## 已知限制

- 這個沙盒環境沒有對外網路,所以 FinMind API 真實抓取這部分我沒辦法在這裡實測,
  是用模擬資料驗證過整個 JSON 輸出格式和前端渲染邏輯是對的。
  你部署後第一次手動觸發 workflow 時,建議去 Actions 頁面看一下 log 確認有成功抓到資料。
- lightweight-charts 是免費開源版本,不支援分不同視窗顯示多組指標(所以RSI是另開一張圖,
  用時間軸同步的方式做出「兩張圖但看起來像一張」的效果)。

## 下一步

之前規劃的三大法人、融資融券、基本面資料,可以比照同樣模式擴充:
在 `data_fetcher.py` 加對應的抓取函式,`build_data.py` 多輸出幾個欄位到JSON,
前端 `app.js` 再加對應的圖表或表格區塊即可,架構不用大改。
