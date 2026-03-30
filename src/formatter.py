"""
Formatter — Định dạng tin nhắn Telegram
"""

from datetime import datetime

TF_LABELS = {"15m": "15 Phút", "1h": "1 Giờ", "4h": "4 Giờ", "1d": "1 Ngày"}

SIGNAL_EMOJI = {
    "BUY":   "🟢",
    "BUY?":  "🟡",
    "SELL":  "🔴",
    "SELL?": "🟡",
    "WAIT":  "⚪",
    "ERROR": "❌",
}

ZONE_EMOJI = {
    "QUÁ MUA":    "🔴",
    "QUÁ BÁN":    "🟢",
    "TRUNG TÍNH": "⚪",
}


def signal_bar(signal: str, score: int, max_score: int = 5) -> str:
    filled = min(score, max_score)
    bar = "█" * filled + "░" * (max_score - filled)
    return f"`[{bar}]` {score}/{max_score}"


def format_signal_message(symbol: str, timeframe: str, data: dict) -> str:
    if data.get("signal") == "ERROR":
        return f"❌ *{symbol} [{TF_LABELS.get(timeframe, timeframe)}]* — Lỗi: {data.get('error', 'Unknown')}"

    sig   = data.get("signal", "WAIT")
    emoji = SIGNAL_EMOJI.get(sig, "⚪")
    score = data.get("score", 0)
    now   = datetime.now().strftime("%H:%M:%S")

    lines = [
        f"{emoji} *{symbol}* | {TF_LABELS.get(timeframe, timeframe)} | `{now}`",
        f"━━━━━━━━━━━━━━━━━━━━━━",
        f"💰 Giá: `{data.get('close', 0):,.4f}`",
        f"",
        f"📊 *RSI* = `{data.get('rsi', 0)}` — {ZONE_EMOJI.get(data.get('rsi_zone',''), '⚪')} {data.get('rsi_zone', '')}",
        f"📈 *EMA* {data.get('ema_signal', '')} | Gap: `{data.get('ema_gap', 0)}`",
        f"   EMA21=`{data.get('ema21',0)}` | EMA49=`{data.get('ema49',0)}`",
        f"",
        f"📉 *Stoch* K=`{data.get('stoch_k',0)}` D=`{data.get('stoch_d',0)}`",
        f"   {ZONE_EMOJI.get(data.get('stoch_zone',''), '⚪')} {data.get('stoch_zone','')} | {data.get('stoch_signal','')}",
        f"",
        f"⚡ *MACD* {data.get('macd_trend','')}",
        f"   Line=`{data.get('macd_line',0)}` Sig=`{data.get('signal_line',0)}`",
        f"   Hist=`{data.get('histogram',0)}`",
        f"",
        f"🎯 *Điểm mạnh:* {signal_bar(sig, score)}",
        f"{'✅ Window còn hiệu lực' if data.get('window_active') else '⏸ Window hết hạn'}",
        f"━━━━━━━━━━━━━━━━━━━━━━",
        f"{'🟢 *TÍN HIỆU MUA* 🟢' if sig == 'BUY' else '🔴 *TÍN HIỆU BÁN* 🔴' if sig == 'SELL' else '⚪ *Chờ tín hiệu...*'}",
    ]
    return "\n".join(lines)


def format_consensus_message(symbol: str, data: dict) -> str:
    consensus  = data.get("consensus", {})
    c_signal   = consensus.get("signal", "WAIT")
    c_strength = consensus.get("strength", "—")
    buy_count  = consensus.get("buy_count", 0)
    sell_count = consensus.get("sell_count", 0)

    now   = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    price = data.get("1h", {}).get("close", 0) or data.get("4h", {}).get("close", 0)

    lines = [
        f"🔍 *PHÂN TÍCH ĐA KHUNG THỜI GIAN*",
        f"💎 *{symbol}* | `{now}`",
        f"💰 Giá hiện tại: `{price:,.4f}`",
        f"━━━━━━━━━━━━━━━━━━━━━━",
        f"",
    ]

    for tf in ["1h", "4h", "1d"]:
        r = data.get(tf, {})
        if not r:
            continue
        sig    = r.get("signal", "WAIT")
        emoji  = SIGNAL_EMOJI.get(sig, "⚪")
        rsi    = r.get("rsi", 0)
        sk     = r.get("stoch_k", 0)
        ema_s  = r.get("ema_signal", "")
        macd_t = "▲" if "BULL" in r.get("macd_trend", "") else "▼"
        score  = r.get("score", 0)
        label  = TF_LABELS.get(tf, tf)

        lines.append(
            f"{emoji} *{label}* ({tf}) — *{sig}* `{score}/5`\n"
            f"   RSI:`{rsi}` | K:`{sk}` | EMA:{ema_s} | MACD:{macd_t}"
        )
        lines.append("")

    lines += [
        f"━━━━━━━━━━━━━━━━━━━━━━",
        f"📊 *ĐỒNG THUẬN (1h/4h/1d):*",
        f"   BUY: `{buy_count}/3` TF | SELL: `{sell_count}/3` TF",
        f"",
    ]

    if "BUY" in c_signal:
        lines += [
            f"{'🟢' * buy_count}{'⚪' * (3 - buy_count)}",
            f"🟢 *TÍN HIỆU {c_signal}* — Sức mạnh: *{c_strength}*",
        ]
    elif "SELL" in c_signal:
        lines += [
            f"{'🔴' * sell_count}{'⚪' * (3 - sell_count)}",
            f"🔴 *TÍN HIỆU {c_signal}* — Sức mạnh: *{c_strength}*",
        ]
    else:
        lines += [
            f"⚪⚪⚪",
            f"⚪ *CHỜ TÍN HIỆU RÕ HƠN...*",
        ]

    lines += ["", f"⚠️ _Chỉ hỗ trợ phân tích, không phải lời khuyên đầu tư._"]
    return "\n".join(lines)


# ╔══════════════════════════════════════════════════════════╗
# ║            SCAN RESULT FORMATTERS                       ║
# ╚══════════════════════════════════════════════════════════╝

def format_scan_summary(results: dict) -> str:
    """Tóm tắt kết quả scan toàn thị trường."""
    buy_list  = results.get("BUY",  [])
    sell_list = results.get("SELL", [])
    now       = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    strong_buy  = [r for r in buy_list  if r["buy_count"]  == 3]
    medium_buy  = [r for r in buy_list  if r["buy_count"]  == 2]
    strong_sell = [r for r in sell_list if r["sell_count"] == 3]
    medium_sell = [r for r in sell_list if r["sell_count"] == 2]

    lines = [
        f"🌍 *SCAN THỊ TRƯỜNG BINANCE*",
        f"⏱️ Khung: 1h / 4h / 1d | `{now}`",
        f"━━━━━━━━━━━━━━━━━━━━━━",
        f"🟢 BUY: `{len(buy_list)}` coin  🔴 SELL: `{len(sell_list)}` coin",
        f"",
    ]

    if strong_buy:
        lines.append(f"🔥 *BUY MẠNH — 3/3 TF đồng thuận:*")
        for r in strong_buy[:12]:
            sym   = r["symbol"].replace("/USDT", "")
            score = r["avg_score"]
            price = r["close"]
            lines.append(f"  🟢 `{sym:<8}` Score:`{score}/5` Giá:`{price:,.4f}`")
        lines.append("")

    if medium_buy:
        lines.append(f"📈 *BUY TRUNG BÌNH — 2/3 TF:*")
        for r in medium_buy[:8]:
            sym     = r["symbol"].replace("/USDT", "")
            tf_buy  = [tf for tf in ["1h","4h","1d"] if r["tf"].get(tf,{}).get("signal") == "BUY"]
            lines.append(f"  🟡 `{sym:<8}` TF: {' '.join(tf_buy)}")
        lines.append("")

    if strong_sell:
        lines.append(f"🔥 *SELL MẠNH — 3/3 TF đồng thuận:*")
        for r in strong_sell[:12]:
            sym   = r["symbol"].replace("/USDT", "")
            score = r["avg_score"]
            price = r["close"]
            lines.append(f"  🔴 `{sym:<8}` Score:`{score}/5` Giá:`{price:,.4f}`")
        lines.append("")

    if medium_sell:
        lines.append(f"📉 *SELL TRUNG BÌNH — 2/3 TF:*")
        for r in medium_sell[:8]:
            sym      = r["symbol"].replace("/USDT", "")
            tf_sell  = [tf for tf in ["1h","4h","1d"] if r["tf"].get(tf,{}).get("signal") == "SELL"]
            lines.append(f"  🟡 `{sym:<8}` TF: {' '.join(tf_sell)}")
        lines.append("")

    lines += [
        f"━━━━━━━━━━━━━━━━━━━━━━",
        f"💡 `/detail BTCUSDT` — xem chi tiết một coin",
        f"💡 `/buy` `/sell` — danh sách đầy đủ có phân trang",
        f"⚠️ _Không phải lời khuyên đầu tư._",
    ]
    return "\n".join(lines)


def format_scan_page(results: dict, signal: str, page: int = 0, page_size: int = 10) -> tuple:
    """Phân trang danh sách BUY hoặc SELL. Trả về (text, total_pages)."""
    items       = results.get(signal, [])
    total       = len(items)
    total_pages = max(1, (total + page_size - 1) // page_size)
    page        = max(0, min(page, total_pages - 1))
    chunk       = items[page * page_size : (page + 1) * page_size]
    now         = datetime.now().strftime("%H:%M:%S")
    emoji       = "🟢" if signal == "BUY" else "🔴"

    lines = [
        f"{emoji} *{signal} — Trang {page+1}/{total_pages}* (`{total}` coin) | `{now}`",
        f"━━━━━━━━━━━━━━━━━━━━━━",
    ]

    for r in chunk:
        sym   = r["symbol"].replace("/USDT", "")
        score = r["avg_score"]
        count = r["buy_count"] if signal == "BUY" else r["sell_count"]
        price = r["close"]
        tf_sigs = []
        for tf in ["1h", "4h", "1d"]:
            s = r["tf"].get(tf, {}).get("signal", "?")
            e = "🟢" if s == "BUY" else "🔴" if s == "SELL" else "⚪"
            tf_sigs.append(f"{e}{tf}")

        flag = "🔥" if count == 3 else "➡️"
        lines.append(
            f"{flag} `{sym}` {' '.join(tf_sigs)}\n"
            f"   Score:`{score}/5` | Giá:`{price:,.4f}`"
        )

    lines += ["", f"_/detail SYMBOL để xem chi tiết_"]
    return "\n".join(lines), total_pages
