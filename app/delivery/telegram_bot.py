import structlog
from telegram import Bot, Update
from telegram.constants import ParseMode
from telegram.ext import Application, ContextTypes, MessageHandler, filters

from app.config import settings

log = structlog.get_logger()


async def send_briefing(text: str) -> None:
    """Send the daily briefing to the configured personal chat (HTML parse mode)."""
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


async def _on_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle an incoming Telegram message — RAG query-back entry point."""
    if update.message is None or not update.message.text:
        return

    query = update.message.text.strip()
    log.info("telegram.query_received", length=len(query))

    # RAG responder wired in once responder.py is implemented
    from app.rag.responder import respond  # noqa: PLC0415 — deferred to avoid circular at startup

    try:
        answer = await respond(query)
    except NotImplementedError:
        answer = "Query-back is not yet available."
    except Exception as exc:
        log.error("telegram.query_error", error=str(exc))
        answer = "Sorry, something went wrong processing your query."

    await update.message.reply_text(answer, parse_mode=ParseMode.HTML)


def build_application() -> Application:
    """Build and return the PTB Application with message handler registered."""
    app = Application.builder().token(settings.telegram_bot_token).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _on_message))
    return app
