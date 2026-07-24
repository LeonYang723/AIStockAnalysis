# scripts/us_news_translate.py
"""
用 Argos Translate 把英文新聞標題翻成中文,完全在 GitHub Actions 執行環境裡跑,
不需要申請任何翻譯API金鑰,也不會把資料送到外部翻譯服務。

注意: 第一次載入語言模型需要下載(~200-300MB),因為 GitHub Actions 每次都是全新環境,
不會保留上次下載的模型,所以每次執行都要重新下載,會讓這個步驟多花幾十秒到一兩分鐘,
這是離線翻譯換來的取捨(不用金鑰,但每次都要重新下載模型)。

Argos的英文->中文模型輸出的是簡體字,翻譯完之後會再用 OpenCC 轉成繁體中文
(台灣慣用詞版本,例如「软件」會轉成「軟體」而不是只轉成「軟件」)。

如果 Argos Translate 沒有安裝成功、或下載模型失敗,翻譯會直接失敗並拋出例外,
呼叫端(build_data.py)要用 try/except 接住,退回顯示英文原文,不要讓整個程式掛掉。
"""

_translator_ready = False
_opencc_converter = None


def _ensure_translator_installed():
    """確認英文->中文的翻譯模型已經安裝,第一次呼叫時才會真的觸發下載"""
    global _translator_ready
    if _translator_ready:
        return

    import argostranslate.package
    import argostranslate.translate

    installed_languages = argostranslate.translate.get_installed_languages()
    has_en_zh = any(
        lang.code == "en" and any(t.to_lang.code == "zh" for t in lang.translations_from)
        for lang in installed_languages
    )
    if has_en_zh:
        _translator_ready = True
        return

    argostranslate.package.update_package_index()
    available_packages = argostranslate.package.get_available_packages()
    package_to_install = next(
        (p for p in available_packages if p.from_code == "en" and p.to_code == "zh"), None
    )
    if package_to_install is None:
        raise RuntimeError("找不到 英文->中文 的Argos翻譯語言包")

    argostranslate.package.install_from_path(package_to_install.download())
    _translator_ready = True


def _get_opencc_converter():
    """惰性初始化OpenCC轉換器(簡體->繁體,台灣慣用詞),只需要建立一次重複使用"""
    global _opencc_converter
    if _opencc_converter is None:
        from opencc import OpenCC
        _opencc_converter = OpenCC("s2twp")  # 簡體 -> 繁體中文(台灣標準,含慣用詞轉換)
    return _opencc_converter


def _to_traditional(text: str) -> str:
    """把簡體字轉成繁體中文,轉換失敗就直接回傳原文,不要讓這一步拖垮整個翻譯流程"""
    if not text:
        return text
    try:
        return _get_opencc_converter().convert(text)
    except Exception:
        return text


def translate_en_to_zh(text: str) -> str:
    """翻譯單一段文字,英文->繁體中文"""
    if not text:
        return text

    _ensure_translator_installed()

    import argostranslate.translate
    simplified = argostranslate.translate.translate(text, "en", "zh")
    return _to_traditional(simplified)


def translate_titles(titles: list) -> list:
    """
    批次翻譯一批新聞標題。單一標題翻譯失敗不會讓整批失敗,
    失敗的那幾則會退回顯示英文原文,並在標題前加註記,不隱藏這個狀況。
    """
    _ensure_translator_installed()

    results = []
    for title in titles:
        try:
            results.append(translate_en_to_zh(title))
        except Exception:
            results.append(f"[翻譯失敗,顯示原文] {title}")
    return results
