# scripts/us_news_translate.py
"""
用 MyMemory 免費翻譯API,把英文新聞標題翻成繁體中文。

MyMemory 完全不需要註冊、不需要信用卡、不需要申請API金鑰,直接發HTTP request就能用。
免費額度: 不帶Email約5000字元/天,帶Email(選填,不需要驗證)約50000字元/天。
以我們的用量(每次執行最多翻15則新聞標題)來說,不帶Email的額度也很夠用。

翻譯結果會再用 OpenCC 轉一次繁體中文(當作保險機制):不管MyMemory實際回傳的是
簡體還是繁體,這一步都會確保最終顯示是繁體,而且轉換「已經是繁體」的文字不會有副作用。

MyMemory 的翻譯品質來自「翻譯記憶庫」(蒐集自歐盟/聯合國等專業文件)加上機器翻譯輔助,
遇到記憶庫沒有對應內容時,品質可能不穩定,請以英文原文連結為準,不保證完全精準。
"""

import requests

MYMEMORY_URL = "https://api.mymemory.translated.net/get"
MYMEMORY_EMAIL = ""  # 選填: 填了額度會從5000字/天提高到50000字/天,不需要驗證這個Email是不是真的

_opencc_converter = None


def _get_opencc_converter():
    """惰性初始化OpenCC轉換器(簡體->繁體,台灣慣用詞),只需要建立一次重複使用"""
    global _opencc_converter
    if _opencc_converter is None:
        from opencc import OpenCC
        _opencc_converter = OpenCC("s2twp")  # 簡體 -> 繁體中文(台灣標準,含慣用詞轉換)
    return _opencc_converter


def _to_traditional(text: str) -> str:
    """
    確保輸出是繁體中文的保險機制。
    轉換失敗會印出真正的錯誤原因(不要默默吞掉),並直接回傳MyMemory原本的回應。
    """
    if not text:
        return text
    try:
        return _get_opencc_converter().convert(text)
    except Exception as e:
        print(f"    [美股新聞翻譯] OpenCC繁體轉換失敗,直接使用MyMemory原始回傳: {e}")
        return text


def translate_en_to_zh(text: str) -> str:
    """翻譯單一段文字,英文->繁體中文"""
    if not text:
        return text

    params = {
        "q": text[:490],  # MyMemory單次查詢有500字元上限,保留一點緩衝空間
        "langpair": "en|zh-TW",
    }
    if MYMEMORY_EMAIL:
        params["de"] = MYMEMORY_EMAIL

    resp = requests.get(MYMEMORY_URL, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    if data.get("responseStatus") != 200:
        raise RuntimeError(data.get("responseDetails", "MyMemory翻譯失敗,原因不明"))

    translated = data["responseData"]["translatedText"]
    return _to_traditional(translated)


def translate_titles(titles: list) -> list:
    """
    批次翻譯一批新聞標題。單一標題翻譯失敗不會讓整批失敗,
    失敗的那幾則會退回顯示英文原文,並在標題前加註記,不隱藏這個狀況。
    """
    results = []
    for title in titles:
        try:
            results.append(translate_en_to_zh(title))
        except Exception as e:
            print(f"    [美股新聞翻譯] 單則翻譯失敗,顯示原文: {e}")
            results.append(f"[翻譯失敗,顯示原文] {title}")
    return results
