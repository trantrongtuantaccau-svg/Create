"""
Analyzer — Port logic từ Pine Script sang Python
RSI + EMA Cross + Stochastic RSI + MACD
Multi-timeframe: 15m, 1h, 4h, 1d
"""

import asyncio
import numpy as np
import pandas as pd
import ccxt.async_support as ccxt
from typing import Dict, Any

TIMEFRAMES = ["15m", "1h", "4h", "1d"]
TF_LABELS  = {"15m": "15 Phút", "1h": "1 Giờ", "4h": "4 Giờ", "1d": "1 Ngày"}


# ╔══════════════════════════════════════════════════════════╗
# ║                   INDICATOR FUNCTIONS                   ║
# ╚══════════════════════════════════════════════════════════╝

def calc_rsi(close: pd.Series, period: int) -> pd.Series:
    delta = close.diff()
    gain  = delta.clip(lower=0)
    loss  = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs  = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)


def calc_ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def calc_stoch_rsi(rsi: pd.Series, stoch_len: int, smooth_k: int, smooth_d: int):
    rsi_high = rsi.rolling(stoch_len).max()
    rsi_low  = rsi.rolling(stoch_len).min()
    rng = rsi_high - rsi_low
    raw_k = np.where(rng != 0, (rsi - rsi_low) / rng * 100, 50.0)
    raw_k = pd.Series(raw_k, index=rsi.index)
    stoch_k = raw_k.rolling(smooth_k).mean()
    stoch_d = stoch_k.rolling(smooth_d).mean()
    return stoch_k.fillna(50), stoch_d.fillna(50)


def calc_macd(close: pd.Series, fast: int, slow: int, signal: int):
    ema_fast   = calc_ema(close, fast)
    ema_slow   = calc_ema(close, slow)
    macd_line  = ema_fast - ema_slow
    signal_line = calc_ema(macd_line, signal)
    histogram  = macd_line - signal_line
    return macd_line, signal_line, histogram


def crossover(a: pd.Series, b: pd.Series) -> pd.Series:
    """a crosses above b"""
    return (a > b) & (a.shift(1) <= b.shift(1))


def crossunder(a: pd.Series, b: pd.Series) -> pd.Series:
    """a crosses below b"""
    return (a < b) & (a.shift(1) >= b.shift(1))


def bars_since(condition: pd.Series, max_bars: int) -> pd.Series:
    """Returns True if condition was True within last max_bars bars"""
    result = pd.Series(False, index=condition.index)
    for i in range(max_bars + 1):
        result = result | condition.shift(i).fillna(False)
    return result


# ╔══════════════════════════════════════════════════════════╗
# ║                   SIGNAL LOGIC                          ║
# ╚══════════════════════════════════════════════════════════╝

def compute_signals(df: pd.DataFrame, params: dict) -> dict:
    """
    Port toàn bộ logic từ Pine Script sang Python.
    Trả về dict chứa giá trị chỉ báo + tín hiệu của bar cuối.
    """
    close = df["close"]

    # RSI
    rsi    = calc_rsi(close, params["rsi_len"])
    ema21  = calc_ema(rsi, params["ema_fast"])
    ema49  = calc_ema(rsi, params["ema_slow"])

    ema_cross_up   = crossover(ema21, ema49)
    ema_cross_down = crossunder(ema21, ema49)

    # Stochastic RSI
    stoch_k, stoch_d = calc_stoch_rsi(rsi, params["stoch_len"],
                                       params["smooth_k"], params["smooth_d"])
    stoch_cross_up   = crossover(stoch_k,  stoch_d)
    stoch_cross_down = crossunder(stoch_k, stoch_d)

    # MACD
    macd_line, signal_line, hist = calc_macd(
        close, params["macd_fast"], params["macd_slow"], params["macd_signal"]
    )
    macd_bullish = macd_line > signal_line
    macd_bearish = macd_line < signal_line

    # Lookback window
    lb = params["lookback_bars"]
    ema_up_recent   = bars_since(ema_cross_up,   lb)
    ema_down_recent = bars_since(ema_cross_down, lb)

    ob = params["ob_level"]
    os = params["os_level"]
    stoch_ob = params["stoch_ob"]
    stoch_os = params["stoch_os"]

    # Combined signal (default mode)
    combined_buy  = ema_up_recent   & stoch_cross_up   & (stoch_k < stoch_ob)
    combined_sell = ema_down_recent & stoch_cross_down & (stoch_k > stoch_os)

    # Score (last bar)
    i = -1  # last bar
    buy_score = sum([
        bool(ema_up_recent.iloc[i]),
        bool(stoch_cross_up.iloc[i]),
        bool(stoch_k.iloc[i] < 50),
        bool(rsi.iloc[i] < 50),
        bool(macd_bullish.iloc[i]),
    ])
    sell_score = sum([
        bool(ema_down_recent.iloc[i]),
        bool(stoch_cross_down.iloc[i]),
        bool(stoch_k.iloc[i] > 50),
        bool(rsi.iloc[i] > 50),
        bool(macd_bearish.iloc[i]),
    ])

    is_buy  = bool(combined_buy.iloc[i])
    is_sell = bool(combined_sell.iloc[i])

    # Zone
    rsi_val    = float(rsi.iloc[i])
    stoch_k_v  = float(stoch_k.iloc[i])
    stoch_d_v  = float(stoch_d.iloc[i])
    macd_v     = float(macd_line.iloc[i])
    signal_v   = float(signal_line.iloc[i])
    hist_v     = float(hist.iloc[i])
    ema21_v    = float(ema21.iloc[i])
    ema49_v    = float(ema49.iloc[i])
    close_v    = float(close.iloc[i])

    rsi_zone  = "QUÁ MUA" if rsi_val >= ob else "QUÁ BÁN" if rsi_val <= os else "TRUNG TÍNH"
    stoch_zone = "QUÁ MUA" if stoch_k_v >= stoch_ob else "QUÁ BÁN" if stoch_k_v <= stoch_os else "TRUNG TÍNH"
    ema_trend  = "TĂNG ▲" if ema21_v > ema49_v else "GIẢM ▼"
    macd_trend = "BULLISH ▲" if bool(macd_bullish.iloc[i]) else "BEARISH ▼"

    # EMA cross signal string
    if bool(ema_cross_up.iloc[i]):
        ema_signal = "▲ CROSS UP"
    elif bool(ema_cross_down.iloc[i]):
        ema_signal = "▼ CROSS DN"
    else:
        ema_signal = ema_trend

    if bool(stoch_cross_up.iloc[i]):
        stoch_signal = "▲ K>D"
    elif bool(stoch_cross_down.iloc[i]):
        stoch_signal = "▼ K<D"
    else:
        stoch_signal = "K > D" if stoch_k_v > stoch_d_v else "K < D"

    signal = "BUY" if is_buy else "SELL" if is_sell else "WAIT"
    score  = buy_score if is_buy else sell_score if is_sell else max(buy_score, sell_score)

    return {
        "signal":       signal,
        "score":        score,
        "close":        close_v,
        "rsi":          round(rsi_val, 1),
        "rsi_zone":     rsi_zone,
        "ema21":        round(ema21_v, 2),
        "ema49":        round(ema49_v, 2),
        "ema_trend":    ema_trend,
        "ema_signal":   ema_signal,
        "ema_gap":      round(abs(ema21_v - ema49_v), 2),
        "stoch_k":      round(stoch_k_v, 1),
        "stoch_d":      round(stoch_d_v, 1),
        "stoch_zone":   stoch_zone,
        "stoch_signal": stoch_signal,
        "macd_line":    round(macd_v, 4),
        "signal_line":  round(signal_v, 4),
        "histogram":    round(hist_v, 4),
        "macd_trend":   macd_trend,
        "buy_score":    buy_score,
        "sell_score":   sell_score,
        "window_active": bool(ema_up_recent.iloc[i] or ema_down_recent.iloc[i]),
    }


# ╔══════════════════════════════════════════════════════════╗
# ║               MULTI-TIMEFRAME ANALYZER                  ║
# ╚══════════════════════════════════════════════════════════╝

class MultiTimeframeAnalyzer:
    def __init__(self, params: dict):
        self.params   = params
        self.exchange = ccxt.binance({"enableRateLimit": True})

    async def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int = 200) -> pd.DataFrame:
        ohlcv = await self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        return df

    async def analyze_single(self, symbol: str, timeframe: str) -> dict:
        df  = await self.fetch_ohlcv(symbol, timeframe)
        sig = compute_signals(df, self.params)
        sig["timeframe"] = timeframe
        sig["symbol"]    = symbol
        return sig

    async def analyze_all_timeframes(self, symbol: str, timeframes: list = None) -> dict:
        tfs = timeframes or TIMEFRAMES
        try:
            tasks   = [self.analyze_single(symbol, tf) for tf in tfs]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            tf_results = {}
            for tf, r in zip(tfs, results):
                if isinstance(r, Exception):
                    tf_results[tf] = {"signal": "ERROR", "error": str(r)}
                else:
                    tf_results[tf] = r

            # ── Consensus logic ──
            valid      = [r for r in tf_results.values() if r.get("signal") != "ERROR"]
            total      = len(valid)
            buy_count  = sum(1 for r in valid if r.get("signal") == "BUY")
            sell_count = sum(1 for r in valid if r.get("signal") == "SELL")

            if total == 0:
                consensus_signal = "WAIT"; consensus_strength = "—"
            elif buy_count == total:
                consensus_signal = "BUY";  consensus_strength = "MẠNH 🔥"
            elif sell_count == total:
                consensus_signal = "SELL"; consensus_strength = "MẠNH 🔥"
            elif buy_count >= total - 1 and buy_count > 0:
                consensus_signal = "BUY";  consensus_strength = "TRUNG BÌNH"
            elif sell_count >= total - 1 and sell_count > 0:
                consensus_signal = "SELL"; consensus_strength = "TRUNG BÌNH"
            else:
                consensus_signal = "WAIT"; consensus_strength = "—"

            tf_results["consensus"] = {
                "signal":     consensus_signal,
                "strength":   consensus_strength,
                "buy_count":  buy_count,
                "sell_count": sell_count,
                "score":      buy_count if "BUY" in consensus_signal else sell_count,
            }
        finally:
            await self.exchange.close()

        return tf_results
