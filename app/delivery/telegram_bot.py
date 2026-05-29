import time
from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import or_
from telegram import Bot, BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatAction, ParseMode
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from app.briefing.composer import COMPANY_GROUPS, close_open_tags
from app.config import settings

log = structlog.get_logger()

_COMMANDS = [
    BotCommand("start", "Introduction and how to use Briefcast"),
    BotCommand("help", "Show how to use this bot"),
]

_TELEGRAM_MAX_CHARS = 4096

# Display label and emoji per company key — used for drill-down buttons and headers
_COMPANY_DISPLAY: dict[str, tuple[str, str]] = {
    "google": ("🔵", "Google"),
    "openai": ("⚫", "OpenAI"),
    "anthropic": ("🟠", "Anthropic"),
    "meta": ("🔶", "Meta AI"),
    "huggingface": ("🟡", "HuggingFace"),
    "arxiv": ("🟥", "arXiv"),
    "mistral": ("🔹", "Mistral"),
    "cohere": ("🔹", "Cohere"),
    "microsoft": ("🟦", "Microsoft"),
    "nvidia": ("🟩", "NVIDIA"),
    "xai": ("🔹", "xAI"),
}


def _build_drill_keyboard(source_keys: list[str]) -> InlineKeyboardMarkup | None:
    """Build an inline keyboard with one button per company in the briefing."""
    if not source_keys:
        return None
    buttons = []
    for k in source_keys:
        emoji, label = _COMPANY_DISPLAY.get(k, ("🔹", k.title()))
        buttons.append(InlineKeyboardButton(f"{emoji} {label}", callback_data=f"drill:{k}"))
    rows = [buttons[i : i + 3] for i in range(0, len(buttons), 3)]
    return InlineKeyboardMarkup(rows)


def _trim_to_last_article(text: str) -> str:
    """Cut at the last double-newline before the Telegram limit, then strip any orphaned
    company header that has no article body (no read link) below it."""
    if len(text) <= _TELEGRAM_MAX_CHARS:
        return text

    boundary = text.rfind("\n\n", 0, _TELEGRAM_MAX_CHARS)
    trimmed = text[:boundary].rstrip() if boundary != -1 else text[:_TELEGRAM_MAX_CHARS]

    # If the last section has no 🔗 link it's a bare company header — remove it too
    prev = trimmed.rfind("\n\n")
    last_section = trimmed[prev:] if prev != -1 else trimmed
    if "🔗" not in last_section:
        trimmed = trimmed[:prev].rstrip() if prev != -1 else ""

    return close_open_tags(trimmed)


async def send_briefing(text: str, source_keys: list[str] | None = None) -> None:
    """Send the daily briefing with optional drill-down buttons per company.

    If TELEGRAM_BRIEFING_THREAD_ID is set (Forum Topics supergroup), the briefing
    is posted into that topic thread instead of the main chat.
    """
    original_len = len(text)
    text = _trim_to_last_article(text)
    if len(text) < original_len:
        log.warning("telegram.briefing_truncated", original_len=original_len, trimmed_len=len(text))
    keyboard = _build_drill_keyboard(source_keys or [])
    if keyboard:
        text = text + "\n\n<i>Tap a source to see all their articles today ↓</i>"
    async with Bot(token=settings.telegram_bot_token) as bot:
        await bot.send_message(
            chat_id=settings.telegram_chat_id,
            text=text,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
            reply_markup=keyboard,
            message_thread_id=settings.telegram_briefing_thread_id,  # None = main chat
        )
    log.info("telegram.briefing_sent", thread_id=settings.telegram_briefing_thread_id)


async def send_alert(text: str) -> None:
    """Send a plain-text ops alert (circuit breaker trips, ingestion failures).

    If TELEGRAM_ALERT_THREAD_ID is set (Forum Topics supergroup), alerts go to
    that dedicated topic instead of the main chat.
    """
    async with Bot(token=settings.telegram_bot_token) as bot:
        await bot.send_message(
            chat_id=settings.telegram_chat_id,
            text=f"⚠️ {text}",
            parse_mode="HTML",
            message_thread_id=settings.telegram_alert_thread_id,  # None = main chat
        )
    log.info("telegram.alert_sent", thread_id=settings.telegram_alert_thread_id)


async def _cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return
    text = (
        "👋 <b>Welcome to Briefcast</b>\n\n"
        "I deliver a daily AI intelligence briefing every morning at <b>09:00 IST</b>, "
        "pulling from Google AI, Google Research, DeepMind, OpenAI, Hugging Face, and more.\n\n"
        "🔍 <b>Ask me anything</b> — just type a question like:\n"
        "  <i>What did Google announce about Gemini this week?</i>\n"
        "  <i>Any new research on RAG systems?</i>\n\n"
        "I'll search the last 14 days of ingested news. If nothing matches, "
        "I'll fall back to a live web search automatically (marked ⚡).\n\n"
        "That's it — no commands needed beyond this. Just ask."
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def _cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return
    text = (
        "<b>Briefcast — quick reference</b>\n\n"
        "<b>Query</b>  just type any question\n"
        "<b>Corpus</b>  last 14 days of ingested AI news\n"
        "<b>Fallback</b>  live web search if corpus misses (⚡)\n"
        "<b>Briefing</b>  daily at 09:00 IST\n"
        "<b>Drill-down</b>  tap source buttons after briefing\n\n"
        "/start — full intro"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def _on_plain_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """All messages → corpus first, Tavily web search fallback on miss."""
    if update.message is None or not update.message.text:
        return
    await _run_rag(update, context, update.message.text.strip())


async def _run_rag(update: Update, context: ContextTypes.DEFAULT_TYPE, query: str) -> None:
    import asyncio  # noqa: PLC0415

    from app.rag.responder import respond  # noqa: PLC0415

    chat_id = update.effective_chat.id

    async def _keep_typing() -> None:
        # Telegram typing indicator expires after 5s — refresh every 4s until cancelled.
        while True:
            await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
            await asyncio.sleep(4)

    log.info("telegram.rag_query", length=len(query))
    typing_task = asyncio.create_task(_keep_typing())
    t0 = time.monotonic()
    try:
        answer = await respond(query)
    except Exception as exc:
        log.error("telegram.rag_error", error=str(exc))
        answer = "Sorry, something went wrong. Please try again."
    finally:
        typing_task.cancel()

    elapsed = time.monotonic() - t0
    answer = f"{answer}\n\n<i>⏱ {elapsed:.1f}s</i>"
    await update.message.reply_text(answer, parse_mode=ParseMode.HTML, disable_web_page_preview=True)


async def _on_drill_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle drill-down button taps — show all articles from that company in the last 36h."""
    from app.db import SessionLocal  # noqa: PLC0415
    from app.models.article import Article  # noqa: PLC0415

    cq = update.callback_query
    await cq.answer()

    company_key = cq.data.split(":", 1)[1] if cq.data and ":" in cq.data else ""
    emoji, label = _COMPANY_DISPLAY.get(company_key, ("🔹", company_key.title()))
    patterns = COMPANY_GROUPS.get(company_key, [company_key])

    cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=36)
    db = SessionLocal()
    try:
        articles = (
            db.query(Article)
            .filter(
                Article.deleted_at.is_(None),
                Article.published_at >= cutoff,
                or_(*[Article.source_name.ilike(f"%{p}%") for p in patterns]),
            )
            .order_by(Article.score.desc().nullslast())
            .limit(8)
            .all()
        )
    finally:
        db.close()

    if not articles:
        await cq.message.reply_text(
            f"No articles from {label} in the last 36 hours.",
            parse_mode=ParseMode.HTML,
        )
        return

    lines = [f"{emoji} <b>{label} — Today's Deep Dive</b>  <code>{len(articles)} articles</code>\n"]
    for a in articles:
        read_label = "Read Paper" if "arxiv" in (a.source_name or "").lower() else "Read Post"
        snippet = ""
        if a.summary:
            raw = a.summary[:300] + ("…" if len(a.summary) > 300 else "")
            snippet = f"• <i>{raw}</i>\n\n"
        card = (
            f"🔷 <b>{a.title}</b>\n"
            f"{snippet}"
            f'🔗 <a href="{a.url}">{read_label}</a>'
        )
        lines.append(f"<blockquote>{card}</blockquote>")
        lines.append("")

    reply = "\n".join(lines).strip()
    if len(reply) > _TELEGRAM_MAX_CHARS:
        reply = reply[: _TELEGRAM_MAX_CHARS - 50] + "\n\n<i>…truncated</i>"

    await cq.message.reply_text(reply, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
    log.info("telegram.drill_sent", company=company_key, articles=len(articles))


def build_application() -> Application:
    """Build and return the PTB Application with all handlers registered."""
    app = Application.builder().token(settings.telegram_bot_token).build()
    app.add_handler(CommandHandler("start", _cmd_start))
    app.add_handler(CommandHandler("help", _cmd_help))
    app.add_handler(CallbackQueryHandler(_on_drill_callback, pattern=r"^drill:"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _on_plain_message))
    return app


async def register_commands() -> None:
    """Register bot command list with Telegram (shows in the / menu in the app)."""
    async with Bot(token=settings.telegram_bot_token) as bot:
        await bot.set_my_commands(_COMMANDS)
    log.info("telegram.commands_registered")
