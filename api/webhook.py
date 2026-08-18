from flask import Flask, request, Response
import asyncio
import logging

from telegram import Update

from bot import create_application
from config import BOT_TOKEN

logger = logging.getLogger(__name__)

# Build the application with the same handlers used by polling mode
application = create_application()

# Ensure we have an event loop to initialize and run the application
try:
    loop = asyncio.get_event_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

# Initialize the application (registers command menu, etc.)
loop.run_until_complete(application.initialize())

app = Flask(__name__)

@app.route("/api/webhook", methods=["POST"])
def webhook():
    """Receive Telegram update JSON and dispatch to the bot application.

    This handler is intentionally synchronous to work with standard WSGI
    runners; it runs the application's update processing coroutine to completion.
    """
    try:
        data = request.get_json(force=True)
    except Exception as e:
        logger.error("Invalid JSON in webhook request: %s", e)
        return Response("Bad Request", status=400)

    try:
        update = Update.de_json(data, application.bot)
    except Exception as e:
        logger.error("Failed to parse Update: %s", e)
        return Response("Bad Request", status=400)

    # Process the update synchronously
    try:
        loop.run_until_complete(application.process_update(update))
    except Exception as e:
        logger.exception("Error processing update: %s", e)
        return Response("Internal Server Error", status=500)

    return Response("OK", status=200)

@app.route("/api/health", methods=["GET"])
def health():
    return Response("ok", status=200)
