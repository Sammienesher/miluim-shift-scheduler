#!/usr/bin/env python3
"""Shiftty — Miluim shift schedule Telegram bot.

Entry point. Starts the bot with polling.
"""
import sys
import os
import logging

# Ensure this directory is on the path so imports work
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from telegram.ext import Application, CommandHandler, MessageHandler, filters
from telegram import Update

from config import TOKEN, LOG_LEVEL
from handlers import start, handle_message

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
)


def main():
    """Run the Shiftty bot."""
    app = Application.builder().token(TOKEN).build()

    # Register handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger = logging.getLogger(__name__)
    logger.info("Shiftty bot starting...")

    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
