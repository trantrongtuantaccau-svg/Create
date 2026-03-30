"""
Trading Signal Bot v2 — Telegram
Scan toàn bộ thị trường Binance
Đồng thuận 1h / 4h / 1d
"""

import os
import asyncio
import logging
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters, ContextTypes
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from src.analyzer import MultiTimeframeAnalyzer
from src.scanner  import scan_market
from src.formatter import (
    format_signal_message, format_consensus_message,
    format_scan_summary, format_scan_page
)
from src.state import BotState

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ── Global ──
state     = BotState()
scheduler = AsyncIOScheduler(timezone="Asia/Ho_Chi_Minh")

# Cache kết quả scan gần nhất để phân trang nhanh
_scan_cache: dict = {}
_scan_time:  str  = ""


# ╔══════════════════════════════════════════════════════════╗
# ║               HELPER                                    ║
# ╚══════════════════════════════════════════════════════════╝

def main_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🌍 Scan thị trường",    callback_data="scan_all"),
         InlineKeyboardButton("🟢 Danh sách BUY",      callback_data="page_BUY_0")],
        [InlineKeyboardButton("🔴 Danh sách SELL",     callback_data="page_SELL_0"),
         InlineKeyboardButton("📊 Phân tích coin",     callback_data="prompt_analyze")],
        [InlineKeyboardButton("📋 Watchlist",          callback_data="watchlist"),
         InlineKeyboardButton("🔔 Bật/Tắt Alert",     callback_data="toggle_alert")],
        [InlineKeyboardButton("⚙️ Tham số",            callback_data="settings"),
         InlineKeyboardButton("❓ Hướng dẫn",          callback_data="help")],
    ])


async def register_chat(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat:
        state.add_chat_id(update.effective_chat.id)


# ╔══════════════════════════════════════════════════════════╗
# ║               COMMANDS                                  ║
# ╚══════════════════════════════════════════════════════════╝

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    state.add_chat_id(update.effective_chat.id)
    await update.message.reply_text(
        "🤖 *Trading Signal Bot v2*\n\n"
        "Scan toàn thị trường Binance\n"
        "Đồng thuận: *1h · 4h · 1d*\n"
        "Logic: RSI + EMA Cross + Stoch RSI + MACD\n\n"
        "Chọn lệnh bên dưới hoặc gõ `/help`:",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard()
    )


async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = (
        "📖 *HƯỚNG DẪN*\n\n"
        "━━━ *Scan thị trường* ━━━\n"
        "`/scan` — Quét toàn bộ Binance USDT\n"
        "`/scan buy` — Chỉ lấy tín hiệu BUY\n"
        "`/scan sell` — Chỉ lấy tín hiệu SELL\n"
        "`/buy` — Danh sách BUY (phân trang)\n"
        "`/sell` — Danh sách SELL (phân trang)\n\n"
        "━━━ *Phân tích coin* ━━━\n"
        "`/detail BTCUSDT` — Chi tiết 1h/4h/1d\n"
        "`/signal BTCUSDT 4h` — 1 khung cụ thể\n\n"
        "━━━ *Watchlist* ━━━\n"
        "`/add SOLUSDT` · `/remove SOLUSDT`\n"
        "`/watchlist` — Xem danh sách\n\n"
        "━━━ *Alert tự động* ━━━\n"
        "`/alert on` · `/alert off`\n"
        "`/alert interval 30` — Tần suất (phút)\n"
        "`/volume 5000000` — Lọc volume tối thiểu\n\n"
        "━━━ *Tham số chỉ báo* ━━━\n"
        "`/params` — Xem tất cả\n"
        "`/setrsi 14` — Đổi RSI period\n\n"
        "💬 *Chat tự nhiên:* _\"BTC thế nào?\"_"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_scan(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Quét toàn bộ thị trường Binance, cache kết quả."""
    global _scan_cache, _scan_time

    filter_arg = ctx.args[0].upper() if ctx.args else "ALL"
    min_vol    = state.min_volume

    msg = await update.message.reply_text(
        f"⏳ *Đang scan thị trường Binance...*\n"
        f"Volume tối thiểu: `{min_vol:,.0f}` USDT\n"
        f"Khung: 1h / 4h / 1d\n\n"
        f"_Quá trình này mất 1-3 phút, xin chờ..._",
        parse_mode="Markdown"
    )

    done_count = 0
    total_count = 0

    async def progress(done, total, sym):
        nonlocal done_count, total_count
        done_count  = done
        total_count = total
        if done % 20 == 0 or done == total:
            pct = int(done / total * 100)
            bar = "█" * (pct // 10) + "░" * (10 - pct // 10)
            try:
                await msg.edit_text(
                    f"⏳ *Đang scan...* `{pct}%`\n"
                    f"`[{bar}]` {done}/{total} coin\n"
                    f"_Vừa xong: {sym}_",
                    parse_mode="Markdown"
                )
            except Exception:
                pass

    try:
        results      = await scan_market(state.params, min_vol, progress_cb=progress)
        _scan_cache  = results
        _scan_time   = datetime.now().strftime("%H:%M:%S %d/%m")
        text         = format_scan_summary(results)
        await msg.edit_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🟢 BUY đầy đủ",  callback_data="page_BUY_0"),
             InlineKeyboardButton("🔴 SELL đầy đủ", callback_data="page_SELL_0")],
            [InlineKeyboardButton("🔄 Scan lại",    callback_data="scan_all")],
        ]))
    except Exception as e:
        logger.error(f"scan error: {e}")
        await msg.edit_text(f"❌ Lỗi scan: {str(e)}")


async def cmd_buy(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not _scan_cache:
        await update.message.reply_text("⚠️ Chưa có dữ liệu. Chạy `/scan` trước.", parse_mode="Markdown")
        return
    text, total = format_scan_page(_scan_cache, "BUY", 0)
    keyboard = _page_keyboard("BUY", 0, total)
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)


async def cmd_sell(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not _scan_cache:
        await update.message.reply_text("⚠️ Chưa có dữ liệu. Chạy `/scan` trước.", parse_mode="Markdown")
        return
    text, total = format_scan_page(_scan_cache, "SELL", 0)
    keyboard = _page_keyboard("SELL", 0, total)
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)


def _page_keyboard(signal: str, page: int, total_pages: int) -> InlineKeyboardMarkup:
    buttons = []
    row = []
    if page > 0:
        row.append(InlineKeyboardButton("◀️ Trước", callback_data=f"page_{signal}_{page-1}"))
    if page < total_pages - 1:
        row.append(InlineKeyboardButton("▶️ Tiếp",  callback_data=f"page_{signal}_{page+1}"))
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton("🔄 Scan lại", callback_data="scan_all")])
    return InlineKeyboardMarkup(buttons)


async def cmd_detail(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    symbol = ctx.args[0].upper() if ctx.args else "BTCUSDT"
    if not symbol.endswith("USDT"):
        symbol += "USDT"

    msg = await update.message.reply_text(f"⏳ Đang phân tích *{symbol}* (1h/4h/1d)...", parse_mode="Markdown")
    try:
        analyzer = MultiTimeframeAnalyzer(state.params)
        result   = await analyzer.analyze_all_timeframes(symbol, timeframes=["1h", "4h", "1d"])
        text     = format_consensus_message(symbol, result)
        await msg.edit_text(text, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"detail error: {e}")
        await msg.edit_text(f"❌ Lỗi: {str(e)}")


async def cmd_signal(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if len(ctx.args) < 2:
        await update.message.reply_text("❌ Dùng: `/signal BTCUSDT 4h`", parse_mode="Markdown")
        return
    symbol = ctx.args[0].upper()
    tf     = ctx.args[1].lower()
    if not symbol.endswith("USDT"):
        symbol += "USDT"
    if tf not in ["1h", "4h", "1d", "15m"]:
        await update.message.reply_text("❌ Khung hợp lệ: 15m, 1h, 4h, 1d")
        return

    msg = await update.message.reply_text(f"⏳ Phân tích {symbol} {tf}...")
    try:
        analyzer = MultiTimeframeAnalyzer(state.params)
        sig      = await analyzer.analyze_single(symbol, tf)
        text     = format_signal_message(symbol, tf, sig)
        await msg.edit_text(text, parse_mode="Markdown")
    except Exception as e:
        await msg.edit_text(f"❌ Lỗi: {str(e)}")


async def cmd_add(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("❌ Dùng: `/add SOLUSDT`", parse_mode="Markdown")
        return
    sym = ctx.args[0].upper()
    if not sym.endswith("USDT"):
        sym += "USDT"
    state.add_symbol(sym)
    await update.message.reply_text(f"✅ Đã thêm *{sym}*!", parse_mode="Markdown")


async def cmd_remove(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("❌ Dùng: `/remove SOLUSDT`", parse_mode="Markdown")
        return
    sym = ctx.args[0].upper()
    if not sym.endswith("USDT"):
        sym += "USDT"
    state.remove_symbol(sym)
    await update.message.reply_text(f"✅ Đã xóa *{sym}*!", parse_mode="Markdown")


async def cmd_watchlist(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    syms = state.watchlist
    text = "📋 *WATCHLIST*\n\n" + ("\n".join(f"• {s}" for s in syms) if syms else "Trống")
    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_alert(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        s = "🟢 BẬT" if state.alert_enabled else "🔴 TẮT"
        await update.message.reply_text(f"🔔 Alert: {s} | Interval: {state.alert_interval} phút")
        return
    cmd = ctx.args[0].lower()
    if cmd == "on":
        state.alert_enabled = True
        await update.message.reply_text("✅ Đã *bật* alert tự động!", parse_mode="Markdown")
    elif cmd == "off":
        state.alert_enabled = False
        await update.message.reply_text("✅ Đã *tắt* alert!", parse_mode="Markdown")
    elif cmd == "interval" and len(ctx.args) > 1:
        try:
            mins = int(ctx.args[1])
            state.alert_interval = mins
            await update.message.reply_text(f"✅ Alert mỗi *{mins} phút*!", parse_mode="Markdown")
        except ValueError:
            await update.message.reply_text("❌ Số phút không hợp lệ")


async def cmd_volume(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text(f"📊 Volume filter hiện tại: `{state.min_volume:,.0f}` USDT/24h", parse_mode="Markdown")
        return
    try:
        vol = float(ctx.args[0])
        state.min_volume = vol
        await update.message.reply_text(f"✅ Volume tối thiểu: `{vol:,.0f}` USDT", parse_mode="Markdown")
    except ValueError:
        await update.message.reply_text("❌ Giá trị không hợp lệ")


async def cmd_params(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    p = state.params
    text = (
        "⚙️ *THAM SỐ HIỆN TẠI*\n\n"
        f"RSI Period: `{p['rsi_len']}`\n"
        f"EMA Fast/Slow: `{p['ema_fast']}/{p['ema_slow']}`\n"
        f"Stoch Length: `{p['stoch_len']}` K:`{p['smooth_k']}` D:`{p['smooth_d']}`\n"
        f"OB/OS: `{p['ob_level']}/{p['os_level']}`\n"
        f"Stoch OB/OS: `{p['stoch_ob']}/{p['stoch_os']}`\n"
        f"MACD: `{p['macd_fast']}/{p['macd_slow']}/{p['macd_signal']}`\n"
        f"Lookback: `{p['lookback_bars']}` bars\n"
        f"Volume filter: `{state.min_volume:,.0f}` USDT\n"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_setrsi(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("❌ Dùng: `/setrsi 14`", parse_mode="Markdown")
        return
    try:
        val = int(ctx.args[0])
        state.params["rsi_len"] = val
        await update.message.reply_text(f"✅ RSI Period = `{val}`", parse_mode="Markdown")
    except ValueError:
        await update.message.reply_text("❌ Giá trị không hợp lệ")


async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    cached = f"`{_scan_time}`" if _scan_time else "Chưa có"
    text = (
        f"🤖 *TRẠNG THÁI BOT*\n\n"
        f"🕐 `{now}`\n"
        f"📊 Cache scan: {cached}\n"
        f"   BUY: `{len(_scan_cache.get('BUY',[]))}` | SELL: `{len(_scan_cache.get('SELL',[]))}`\n"
        f"📋 Watchlist: `{len(state.watchlist)}` cặp\n"
        f"🔔 Alert: {'🟢 BẬT' if state.alert_enabled else '🔴 TẮT'} | `{state.alert_interval}` phút\n"
        f"📡 Exchange: Binance\n"
        f"✅ Hoạt động bình thường"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


# ╔══════════════════════════════════════════════════════════╗
# ║             CALLBACK QUERY HANDLER                      ║
# ╚══════════════════════════════════════════════════════════╝

async def handle_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    global _scan_cache, _scan_time
    query = update.callback_query
    await query.answer()
    data = query.data

    # ── Scan all ──
    if data == "scan_all":
        await query.edit_message_text("⏳ *Đang scan toàn thị trường...*\n_Mất 1-3 phút..._", parse_mode="Markdown")
        try:
            results     = await scan_market(state.params, state.min_volume)
            _scan_cache = results
            _scan_time  = datetime.now().strftime("%H:%M:%S %d/%m")
            text        = format_scan_summary(results)
            await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🟢 BUY đầy đủ",  callback_data="page_BUY_0"),
                 InlineKeyboardButton("🔴 SELL đầy đủ", callback_data="page_SELL_0")],
                [InlineKeyboardButton("🔄 Scan lại",    callback_data="scan_all")],
            ]))
        except Exception as e:
            await query.edit_message_text(f"❌ Lỗi scan: {str(e)}")

    # ── Paging ──
    elif data.startswith("page_"):
        parts  = data.split("_")
        signal = parts[1]     # BUY / SELL
        page   = int(parts[2])
        if not _scan_cache:
            await query.edit_message_text("⚠️ Chưa có dữ liệu. Dùng `/scan` trước.", parse_mode="Markdown")
            return
        text, total = format_scan_page(_scan_cache, signal, page)
        kb = _page_keyboard(signal, page, total)
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=kb)

    elif data == "watchlist":
        syms = state.watchlist
        text = "📋 *WATCHLIST*\n\n" + ("\n".join(f"• {s}" for s in syms) if syms else "Trống")
        await query.edit_message_text(text, parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Menu", callback_data="back_main")]]))

    elif data == "toggle_alert":
        state.alert_enabled = not state.alert_enabled
        s = "🟢 BẬT" if state.alert_enabled else "🔴 TẮT"
        await query.edit_message_text(f"🔔 Alert: {s}\n\nDùng `/start` để quay lại.", parse_mode="Markdown")

    elif data == "settings":
        p = state.params
        text = (
            f"⚙️ *THAM SỐ*\n\n"
            f"RSI:`{p['rsi_len']}` EMA:`{p['ema_fast']}/{p['ema_slow']}`\n"
            f"Stoch:`{p['stoch_len']}` OB/OS:`{p['ob_level']}/{p['os_level']}`\n"
            f"MACD:`{p['macd_fast']}/{p['macd_slow']}/{p['macd_signal']}`\n"
            f"Volume filter: `{state.min_volume:,.0f}` USDT\n\n"
            f"Dùng `/setrsi`, `/volume` để chỉnh."
        )
        await query.edit_message_text(text, parse_mode="Markdown")

    elif data == "help":
        text = (
            "📖 *HƯỚNG DẪN NHANH*\n\n"
            "`/scan` — Quét toàn thị trường\n"
            "`/buy` `/sell` — Danh sách phân trang\n"
            "`/detail BTCUSDT` — Chi tiết 1h/4h/1d\n"
            "`/alert on` — Bật tự động gửi\n"
            "`/volume 5000000` — Lọc volume"
        )
        await query.edit_message_text(text, parse_mode="Markdown")

    elif data == "prompt_analyze":
        await query.edit_message_text(
            "📊 Nhập lệnh phân tích:\n\n"
            "`/detail BTCUSDT` — 1h/4h/1d\n"
            "`/signal ETHUSDT 4h` — 1 khung",
            parse_mode="Markdown"
        )

    elif data == "back_main":
        await query.edit_message_text(
            "Dùng `/start` để mở menu chính.",
            parse_mode="Markdown"
        )


# ╔══════════════════════════════════════════════════════════╗
# ║            NATURAL LANGUAGE CHAT                        ║
# ╚══════════════════════════════════════════════════════════╝

async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    state.add_chat_id(update.effective_chat.id)
    text = update.message.text.lower()

    known = ["btc", "eth", "bnb", "sol", "xrp", "ada", "doge", "avax",
             "dot", "link", "matic", "atom", "uni", "ltc", "trx"]
    symbol = None
    for coin in known:
        if coin in text:
            symbol = coin.upper() + "USDT"
            break

    scan_kw    = ["scan", "quét", "toàn thị trường", "tất cả"]
    detail_kw  = ["phân tích", "analyze", "xem", "kiểm tra", "thế nào", "ra sao", "sao"]

    if any(k in text for k in scan_kw):
        await update.message.reply_text("⏳ Dùng `/scan` để quét toàn thị trường!", parse_mode="Markdown")

    elif symbol and any(k in text for k in detail_kw):
        msg = await update.message.reply_text(f"⏳ Đang phân tích *{symbol}*...", parse_mode="Markdown")
        try:
            analyzer = MultiTimeframeAnalyzer(state.params)
            result   = await analyzer.analyze_all_timeframes(symbol, timeframes=["1h", "4h", "1d"])
            reply    = format_consensus_message(symbol, result)
            await msg.edit_text(reply, parse_mode="Markdown")
        except Exception as e:
            await msg.edit_text(f"❌ Lỗi: {str(e)}")

    elif "buy" in text or "mua" in text:
        if _scan_cache:
            text_r, total = format_scan_page(_scan_cache, "BUY", 0)
            await update.message.reply_text(text_r, parse_mode="Markdown",
                                             reply_markup=_page_keyboard("BUY", 0, total))
        else:
            await update.message.reply_text("⚠️ Chạy `/scan` trước để có dữ liệu!", parse_mode="Markdown")

    elif "sell" in text or "bán" in text:
        if _scan_cache:
            text_r, total = format_scan_page(_scan_cache, "SELL", 0)
            await update.message.reply_text(text_r, parse_mode="Markdown",
                                             reply_markup=_page_keyboard("SELL", 0, total))
        else:
            await update.message.reply_text("⚠️ Chạy `/scan` trước để có dữ liệu!", parse_mode="Markdown")

    elif "help" in text or "giúp" in text or "hướng dẫn" in text:
        await cmd_help(update, ctx)

    else:
        await update.message.reply_text(
            "💡 Thử:\n"
            "• `/scan` — Quét toàn thị trường\n"
            "• `/detail BTCUSDT` — Phân tích BTC\n"
            "• _\"ETH thế nào?\"_ — Chat tự nhiên\n"
            "• `/help` — Xem đầy đủ",
            parse_mode="Markdown"
        )


# ╔══════════════════════════════════════════════════════════╗
# ║               AUTO ALERT SCHEDULER                      ║
# ╚══════════════════════════════════════════════════════════╝

async def auto_alert_job(app: Application):
    global _scan_cache, _scan_time
    if not state.alert_enabled:
        return
    chat_ids = state.alert_chat_ids
    if not chat_ids:
        return

    logger.info("[AutoAlert] Đang scan...")
    try:
        results     = await scan_market(state.params, state.min_volume)
        _scan_cache = results
        _scan_time  = datetime.now().strftime("%H:%M:%S %d/%m")

        buy_strong  = [r for r in results.get("BUY",  []) if r["buy_count"]  == 3]
        sell_strong = [r for r in results.get("SELL", []) if r["sell_count"] == 3]

        if buy_strong or sell_strong:
            text = format_scan_summary(results)
            for chat_id in chat_ids:
                await app.bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown")
            logger.info(f"[AutoAlert] Gửi tới {len(chat_ids)} chat")
    except Exception as e:
        logger.error(f"[AutoAlert] Lỗi: {e}")


# ╔══════════════════════════════════════════════════════════╗
# ║                       MAIN                              ║
# ╚══════════════════════════════════════════════════════════╝

def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("❌ Thiếu TELEGRAM_BOT_TOKEN!")

    app = Application.builder().token(token).build()

    # Commands
    app.add_handler(CommandHandler("start",     cmd_start))
    app.add_handler(CommandHandler("help",      cmd_help))
    app.add_handler(CommandHandler("scan",      cmd_scan))
    app.add_handler(CommandHandler("buy",       cmd_buy))
    app.add_handler(CommandHandler("sell",      cmd_sell))
    app.add_handler(CommandHandler("detail",    cmd_detail))
    app.add_handler(CommandHandler("signal",    cmd_signal))
    app.add_handler(CommandHandler("add",       cmd_add))
    app.add_handler(CommandHandler("remove",    cmd_remove))
    app.add_handler(CommandHandler("watchlist", cmd_watchlist))
    app.add_handler(CommandHandler("alert",     cmd_alert))
    app.add_handler(CommandHandler("volume",    cmd_volume))
    app.add_handler(CommandHandler("params",    cmd_params))
    app.add_handler(CommandHandler("setrsi",    cmd_setrsi))
    app.add_handler(CommandHandler("status",    cmd_status))

    # Callbacks & chat
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.ALL, register_chat), group=1)

    # Scheduler
    scheduler.add_job(
        lambda: asyncio.create_task(auto_alert_job(app)),
        "interval",
        minutes=state.alert_interval,
        id="auto_alert"
    )
    scheduler.start()

    logger.info("🤖 Bot v2 đang chạy...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
