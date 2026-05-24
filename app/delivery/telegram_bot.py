from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import or_
from telegram import Bot, BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from app.briefing.composer import COMPANY_GROUPS, close_open_tags
from app.config import settings

log = structlog.get_logger()

_COMMANDS = [
    BotCommand("ask", "Search corpus only (no web fallback)"),
    BotCommand("chat", "Direct AI chat — no search"),
    BotCommand("help", "Show available commands"),
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


async def _cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return
    text = (
        "<b>Briefcast — your personal AI intelligence bot</b>\n\n"
        "Just <b>type any question</b> — no command needed.\n\n"
        "🔍 <b>Auto-routing:</b>\n"
        "  • Found in corpus → answer with citations from your ingested articles\n"
        "  • Not in corpus → live web search fallback (⚡ marked)\n\n"
        "<b>Explicit commands:</b>\n"
        "/ask <i>question</i> — force corpus-only search (no web fallback)\n"
        "/chat <i>message</i> — direct AI chat, no search at all\n"
        "/help — show this message"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def _cmd_ask(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /ask <query> — corpus-only RAG (no web search fallback)."""
    if update.message is None:
        return

    query = " ".join(context.args or []).strip()
    if not query:
        await update.message.reply_text("Usage: /ask <i>your question</i>", parse_mode=ParseMode.HTML)
        return

    await _run_rag(update, query, corpus_only=True)


async def _cmd_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /chat <message> — direct LLM, no retrieval."""
    if update.message is None:
        return

    query = " ".join(context.args or []).strip()
    if not query:
        await update.message.reply_text("Usage: /chat <i>your message</i>", parse_mode=ParseMode.HTML)
        return

    await _run_chat(update, query)


async def _on_plain_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Plain messages (no command) → RAG with web search fallback enabled."""
    if update.message is None or not update.message.text:
        return
    await _run_rag(update, update.message.text.strip(), corpus_only=False)


async def _run_rag(update: Update, query: str, corpus_only: bool = False) -> None:
    from app.rag.responder import respond  # noqa: PLC0415

    log.info("telegram.rag_query", length=len(query), corpus_only=corpus_only)
    try:
        answer = await respond(query, corpus_only=corpus_only)
    except Exception as exc:
        log.error("telegram.rag_error", error=str(exc))
        answer = "Sorry, something went wrong with the corpus query."

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

    lines = [f"{emoji} <b>{label} — Today's Deep Dive</b>\n"]
    for a in articles:
        lines.append(f"🔷 <b>{a.title}</b>")
        if a.summary:
            snippet = a.summary[:350] + ("…" if len(a.summary) > 350 else "")
            lines.append(snippet)
        read_label = "Read Paper" if "arxiv" in (a.source_name or "").lower() else "Read Post"
        lines.append(f'🔗 <a href="{a.url}">{read_label}</a>')
        lines.append("")

    reply = "\n".join(lines).strip()
    if len(reply) > _TELEGRAM_MAX_CHARS:
        reply = reply[: _TELEGRAM_MAX_CHARS - 50] + "\n\n<i>…truncated</i>"

    await cq.message.reply_text(reply, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
    log.info("telegram.drill_sent", company=company_key, articles=len(articles))


async def _run_chat(update: Update, query: str) -> None:
    from app.rag.chat_responder import chat  # noqa: PLC0415

    log.info("telegram.chat_query", length=len(query))
    try:
        answer = await chat(query)
    except Exception as exc:
        log.error("telegram.chat_error", error=str(exc))
        answer = "Sorry, something went wrong with the chat request."

    await update.message.reply_text(answer, parse_mode=ParseMode.HTML)


def build_application() -> Application:
    """Build and return the PTB Application with all handlers registered."""
    app = Application.builder().token(settings.telegram_bot_token).build()
    app.add_handler(CommandHandler("help", _cmd_help))
    app.add_handler(CommandHandler("ask", _cmd_ask))
    app.add_handler(CommandHandler("chat", _cmd_chat))
    app.add_handler(CallbackQueryHandler(_on_drill_callback, pattern=r"^drill:"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _on_plain_message))
    return app


async def register_commands() -> None:
    """Register bot command list with Telegram (shows in the / menu in the app)."""
    async with Bot(token=settings.telegram_bot_token) as bot:
        await bot.set_my_commands(_COMMANDS)
    log.info("telegram.commands_registered")
