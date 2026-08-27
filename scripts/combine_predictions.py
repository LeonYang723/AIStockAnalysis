# scripts/combine_predictions.py
"""
走向分頁「第三版」預測: 把「歷史統計法」(analysis.py)與「ML邏輯迴歸模型」(ml_model.py)
組合成一個信心加權的綜合預測,而不是單純把兩個機率取平均。

為什麼不能直接平均:
  1. 兩種方法的可信度天差地遠 —— 統計法在小樣本(比對層級退回到只看RSI、甚至全部歷史平均)
     時的機率波動很大,很容易出現極端值;ML模型可不可信,要看它自己最近60個交易日的回測
     準確率有沒有顯著贏過50%(接近50%代表這次跟隨機亂猜差不多)。如果兩邊等權平均,
     等於讓噪音訊號拉低原本有效的訊號。
  2. 兩者意見分歧時(例如統計法看漲、ML模型看跌),直接平均會把「兩個方法看法不一致」
     這個重要資訊直接抹掉,變成一個看起來煞有介事、其實沒有參考價值的中間數字。所以這裡
     額外算出「分歧程度」與「分歧提示」,交給前端明顯標示出來,而不是靜靜地被平均掉。

做法: 用「信心權重」加權平均,權重規則盡量簡單、可解釋(跟這個專案一貫「透明、不是黑箱」
的風格一致),不是另外訓練一個模型去學權重(那是之後可以做的進階版 stacking,見專案的
設計文件記錄)。

跟其他模組一樣,回傳格式跟統計法/ML法一致(up_pct/down_pct/state_label/match_level),
可以直接餵給 prediction_tracker,獨立追蹤這個「綜合版」自己的命中率,才能實際驗證
綜合預測有沒有比單一方法更準,而不是假設它一定更好。
"""

# ---- 統計法信心權重 ----
# 依比對層級(match_level)決定基準值: 層級越嚴格(比對條件越多)基準權重越高
STAT_MATCH_LEVEL_BASE_WEIGHT = {
    "rsi_and_ma": 1.0,
    "rsi_only": 0.6,
    "all_history": 0.3,
}
# 樣本數要達到這個數字,基準權重才會給到「滿分」(未達到時按比例打折)
# 用 analysis.py 的 ANALYSIS_MIN_SAMPLE(=20)的3倍當作「樣本充足」的門檻
STAT_SAMPLE_SATURATE_AT = 60

# ---- ML模型信心權重 ----
# 回測準確率超過50%多少,權重才會「拉滿」;超過這個差距不再額外加分,
# 避免單一段60天回測剛好運氣好的極端值把權重衝過高(對應回測準確率60%就封頂)
ML_BACKTEST_EDGE_SATURATE_AT = 10.0

# ---- 分歧程度分級 ----
# 兩個方法預測機率相差多少個百分點(以上),視為「方向一致但幅度差異大」
DIVERGENCE_MODERATE = 10.0
# 相差多少個百分點(以上),視為「分歧」(方向直接相反時,不論差距多少都直接算分歧)
DIVERGENCE_HIGH = 20.0


def _stat_confidence(next_day: dict) -> float:
    """統計法的信心權重(0~1): 比對層級 x 樣本數是否充足"""
    if not next_day or next_day.get("up_pct") is None:
        return 0.0
    base = STAT_MATCH_LEVEL_BASE_WEIGHT.get(next_day.get("match_level"), 0.0)
    sample_size = next_day.get("sample_size") or 0
    sample_factor = min(1.0, sample_size / STAT_SAMPLE_SATURATE_AT)
    return base * sample_factor


def _ml_confidence(ml_next_day: dict) -> float:
    """ML模型的信心權重(0~1): 用它自己的回測準確率離50%(隨機亂猜的水準)多遠來衡量"""
    if not ml_next_day or ml_next_day.get("up_pct") is None:
        return 0.0
    backtest_acc = ml_next_day.get("backtest_accuracy")
    if backtest_acc is None:
        return 0.0
    edge = max(0.0, backtest_acc - 50.0)
    return min(1.0, edge / ML_BACKTEST_EDGE_SATURATE_AT)


def _agreement_info(stat_up: float, ml_up: float):
    """回傳 (agreement_level, agreement_label): 兩方法方向/幅度是否一致"""
    diff = abs(stat_up - ml_up)
    stat_dir = "up" if stat_up >= 50 else "down"
    ml_dir = "up" if ml_up >= 50 else "down"

    if stat_dir != ml_dir or diff >= DIVERGENCE_HIGH:
        return "diverge", "兩種方法對後市方向的看法分歧,綜合結果可信度較低,建議謹慎看待"
    if diff >= DIVERGENCE_MODERATE:
        return "moderate", "兩種方法方向一致,但看漲/看跌幅度差異較大"
    return "agree", "兩種方法方向一致且幅度接近,綜合結果相對可信"


def combine_next_day(next_day: dict, ml_next_day: dict) -> dict:
    """
    把統計法(next_day)與ML模型(ml_next_day)兩個獨立預測,組合成信心加權的綜合預測。
    輸入格式分別是 analysis.compute_next_day_probability() 與 ml_model.train_and_predict()
    的回傳值(或其中一個因為資料不足而是 up_pct=None 的失敗結果)。
    """
    stat_up = next_day.get("up_pct") if next_day else None
    ml_up = ml_next_day.get("up_pct") if ml_next_day else None

    if stat_up is None and ml_up is None:
        return {
            "up_pct": None, "down_pct": None,
            "stat_weight": 0.0, "ml_weight": 0.0,
            "divergence": None, "agreement_level": None, "agreement_label": None,
            "match_level": "insufficient_data",
            "state_label": "統計法與ML模型目前都沒有做出有效預測,無法產生綜合結果",
        }

    w_stat = _stat_confidence(next_day)
    w_ml = _ml_confidence(ml_next_day)

    if stat_up is None:
        combined_up = ml_up
        combo_note = "統計法目前無有效預測,綜合結果直接採用ML模型"
        match_level = "ml_only"
    elif ml_up is None:
        combined_up = stat_up
        combo_note = "ML模型目前無有效預測,綜合結果直接採用統計法"
        match_level = "stat_only"
    elif w_stat == 0.0 and w_ml == 0.0:
        # 兩邊信心權重都是0(都不太可信)時,退回單純平均,至少讓使用者看到兩邊原始數字的中點,
        # 而不是完全無法顯示
        combined_up = (stat_up + ml_up) / 2
        combo_note = "兩種方法目前信心權重都偏低,綜合結果僅供參考"
        match_level = "balanced"
    else:
        total_w = w_stat + w_ml
        combined_up = (w_stat * stat_up + w_ml * ml_up) / total_w
        stat_share = round(w_stat / total_w * 100)
        ml_share = round(w_ml / total_w * 100)
        combo_note = f"統計法權重 {stat_share}% · ML模型權重 {ml_share}%"
        if w_stat >= w_ml * 1.5:
            match_level = "stat_dominant"
        elif w_ml >= w_stat * 1.5:
            match_level = "ml_dominant"
        else:
            match_level = "balanced"

    combined_up_pct = round(combined_up, 1)
    combined_down_pct = round(100 - combined_up_pct, 1)

    divergence = None
    agreement_level = None
    agreement_label = None
    if stat_up is not None and ml_up is not None:
        divergence = round(abs(stat_up - ml_up), 1)
        agreement_level, agreement_label = _agreement_info(stat_up, ml_up)

    stat_label = f"{stat_up}%" if stat_up is not None else "-"
    ml_label = f"{ml_up}%" if ml_up is not None else "-"

    return {
        "up_pct": combined_up_pct,
        "down_pct": combined_down_pct,
        "stat_weight": round(w_stat, 2),
        "ml_weight": round(w_ml, 2),
        "divergence": divergence,
        "agreement_level": agreement_level,
        "agreement_label": agreement_label,
        "match_level": match_level,
        "state_label": f"{combo_note}(統計法{stat_label} / ML模型{ml_label})",
    }
