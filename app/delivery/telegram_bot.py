import structlog
from telegram import Bot, BotCommand, Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from app.config import settings

log = structlog.get_logger()

_COMMANDS = [
    BotCommand("ask", "Query your 14-day AI corpus (RAG)"),
    BotCommand("chat", "Chat directly with the AI (no corpus)"),
    BotCommand("help", "Show available commands"),
]


_TELEGRAM_MAX_CHARS = 4096
_TRUNCATION_NOTICE = "\n\n<i>…briefing truncated — see Railway logs for full output</i>"


async def send_briefing(text: str) -> None:
    """Send the daily briefing to the configured personal chat (HTML parse mode)."""
    if len(text) > _TELEGRAM_MAX_CHARS:
        cutoff = _TELEGRAM_MAX_CHARS - len(_TRUNCATION_NOTICE)
        text = text[:cutoff] + _TRUNCATION_NOTICE
        log.warning("telegram.briefing_truncated", original_len=len(text))
    async with Bot(token=settings.telegram_bot_token) as bot:
        await bot.send_message(
            chat_id=settings.telegram_chat_id,
            text=text,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )
    log.info("telegram.briefing_sent")


async def send_alert(text: str) -> None:
    """Send a plain-text ops alert (circuit breaker trips, ingestion failures)."""
    async with Bot(token=settings.telegram_bot_token) as bot:
        await bot.send_message(
            chat_id=settings.telegram_chat_id,
            text=f"⚠️ {text}",
        )
    log.info("telegram.alert_sent")


async def _cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return
    text = (
        "<b>Briefcast commands</b>\n\n"
        "/ask <i>your question</i> — search your 14-day AI corpus and answer with citations\n"
        "/chat <i>your message</i> — talk directly to the AI (no corpus lookup)\n\n"
        "Plain messages (no command) default to <b>/ask</b>."
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def _cmd_ask(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /ask <query> — RAG over the 14-day corpus."""
    if update.message is None:
        return

    query = " ".join(context.args or []).strip()
    if not query:
        await update.message.reply_text("Usage: /ask <i>your question</i>", parse_mode=ParseMode.HTML)
        return

    await _run_rag(update, query)


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
    """Plain messages (no command) default to RAG."""
    if update.message is None or not update.message.text:
        return
    await _run_rag(update, update.message.text.strip())


async def _run_rag(update: Update, query: str) -> None:
    from app.rag.responder import respond  # noqa: PLC0415

    log.info("telegram.rag_query", length=len(query))
    try:
        answer = await respond(query)
    except Exception as exc:
        log.error("telegram.rag_error", error=str(exc))
        answer = "Sorry, something went wrong with the corpus query."

    await update.message.reply_text(answer, parse_mode=ParseMode.HTML, disable_web_page_preview=True)


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
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _on_plain_message))
    return app


async def register_commands() -> None:
    """Register bot command list with Telegram (shows in the / menu in the app)."""
    async with Bot(token=settings.telegram_bot_token) as bot:
        await bot.set_my_commands(_COMMANDS)
    log.info("telegram.commands_registered")
