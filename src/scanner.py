"""
Market Scanner — Quét toàn bộ cặp USDT trên Binance
Tìm đồng thuận 1h / 4h / 1d
"""

import asyncio
import logging
import ccxt.async_support as ccxt
from typing import List, Dict, Any

from src.analyzer import compute_signals, calc_rsi, calc_ema, calc_stoch_rsi, calc_macd
import pandas as pd

logger = logging.getLogger(__name__)

TIMEFRAMES = ["1h", "4h", "1d"]
TF_LABELS  = {"1h": "1 Giờ", "4h": "4 Giờ", "1d": "1 Ngày"}

# Giới hạn concurrent requests để không bị rate-limit
CONCURRENCY  = 5
MIN_VOLUME   = 1_000_000   # Volume USDT tối thiểu 24h (lọc coin rác)
OHLCV_LIMIT  = 150         # Số nến lấy mỗi TF


# ╔══════════════════════════════════════════════════════════╗
# ║               FETCH HELPERS                             ║
# ╚══════════════════════════════════════════════════════════╝

async def fetch_usdt_symbols(exchange: ccxt.binance, min_volume: float = MIN_VOLUME) -> List[str]:
    """Lấy danh sách tất cả cặp *USDT đang active, lọc theo volume 24h."""
    await exchange.load_markets()
    tickers = await exchange.fetch_tickers()

    symbols = []
    for sym, ticker in tickers.items():
        if not sym.endswith("/USDT"):
            continue
        # Bỏ leverage tokens
        base = sym.split("/")[0]
        if any(x in base for x in ["UP", "DOWN", "BULL", "BEAR", "3L", "3S"]):
            continue
        vol = ticker.get("quoteVolume") or 0
        if vol >= min_volume:
            symbols.append(sym)

    symbols.sort()
    logger.info(f"[Scanner] Tìm thấy {len(symbols)} cặp USDT đủ điều kiện")
    return symbols


async def fetch_ohlcv_safe(exchange, symbol: str, timeframe: str, limit: int = OHLCV_LIMIT):
    try:
        ohlcv = await exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        if not ohlcv or len(ohlcv) < 50:
            return None
        df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        return df
    except Exception as e:
        logger.debug(f"fetch_ohlcv_safe {symbol} {timeframe}: {e}")
        return None


# ╔══════════════════════════════════════════════════════════╗
# ║             SINGLE SYMBOL ANALYSIS                      ║
# ╚══════════════════════════════════════════════════════════╝

async def analyze_symbol(exchange, symbol: str, params: dict) -> Dict[str, Any] | None:
    """
    Phân tích 1h / 4h / 1d cho một symbol.
    Trả về dict kết quả hoặc None nếu lỗi.
    """
    tasks = [fetch_ohlcv_safe(exchange, symbol, tf) for tf in TIMEFRAMES]
    dfs   = await asyncio.gather(*tasks)

    tf_results = {}
    for tf, df in zip(TIMEFRAMES, dfs):
        if df is None:
            return None  # bỏ qua nếu thiếu dữ liệu bất kỳ TF
        try:
            sig = compute_signals(df, params)
            tf_results[tf] = sig
        except Exception as e:
            logger.debug(f"compute_signals {symbol} {tf}: {e}")
            return None

    # ── Consensus 1h/4h/1d ──
    buy_count  = sum(1 for r in tf_results.values() if r["signal"] == "BUY")
    sell_count = sum(1 for r in tf_results.values() if r["signal"] == "SELL")

    if buy_count == 3:
        consensus = "BUY";   strength = "MẠNH 🔥"
    elif sell_count == 3:
        consensus = "SELL";  strength = "MẠNH 🔥"
    elif buy_count == 2:
        consensus = "BUY";   strength = "TRUNG BÌNH"
    elif sell_count == 2:
        consensus = "SELL";  strength = "TRUNG BÌNH"
    else:
        consensus = "WAIT";  strength = "YẾU"

    # Tính average score
    avg_score = round(
        sum(r.get("score", 0) for r in tf_results.values()) / len(tf_results), 1
    )

    close = tf_results["1h"].get("close", 0)

    return {
        "symbol":     symbol,
        "close":      close,
        "consensus":  consensus,
        "strength":   strength,
        "buy_count":  buy_count,
        "sell_count": sell_count,
        "avg_score":  avg_score,
        "tf":         tf_results,
    }


# ╔══════════════════════════════════════════════════════════╗
# ║               FULL MARKET SCAN                          ║
# ╚══════════════════════════════════════════════════════════╝

async def scan_market(
    params:     dict,
    min_volume: float = MIN_VOLUME,
    filter_signal: str = "ALL",          # "BUY", "SELL", "ALL"
    progress_cb = None,                  # async callback(done, total, symbol)
) -> Dict[str, List]:
    """
    Quét toàn thị trường Binance USDT.
    Trả về dict: {"BUY": [...], "SELL": [...], "WAIT": [...]}
    """
    exchange = ccxt.binance({"enableRateLimit": True})

    try:
        symbols = await fetch_usdt_symbols(exchange, min_volume)
        total   = len(symbols)
        results = {"BUY": [], "SELL": [], "WAIT": []}

        sem = asyncio.Semaphore(CONCURRENCY)

        async def process(sym, idx):
            async with sem:
                r = await analyze_symbol(exchange, sym, params)
                if progress_cb:
                    await progress_cb(idx + 1, total, sym)
                if r:
                    results[r["consensus"]].append(r)

        await asyncio.gather(*[process(s, i) for i, s in enumerate(symbols)])

        # Sort by avg_score desc
        for key in results:
            results[key].sort(key=lambda x: x["avg_score"], reverse=True)

        logger.info(
            f"[Scanner] Xong: BUY={len(results['BUY'])} "
            f"SELL={len(results['SELL'])} WAIT={len(results['WAIT'])}"
        )
        return results

    finally:
        await exchange.close()
