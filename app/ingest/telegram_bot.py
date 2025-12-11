"""
SBNC Photo Gallery System - Telegram Bot Integration
Receive photos via Telegram bot for processing.

Setup:
1. Create bot via @BotFather on Telegram
2. Get the bot token
3. Set TELEGRAM_BOT_TOKEN in .env
4. Run the bot or configure webhook

Usage:
Members send photos to @SBNCPhotosBot on Telegram.
Bot receives photos, saves to queue, and confirms receipt.
"""

import os
import uuid
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

from app.config import (
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_BOT_USERNAME,
    TELEGRAM_WEBHOOK_SECRET,
    PHOTO_STORAGE_ROOT,
    SUPPORTED_IMAGE_EXTENSIONS,
    SubmissionSource
)
from app.database import get_db
from app.ingest.queue_manager import QueueManager

logger = logging.getLogger(__name__)

# Lazy import to avoid requiring python-telegram-bot if not used
telegram = None
Application = None


def _ensure_telegram_imported():
    """Import telegram library on first use."""
    global telegram, Application
    if telegram is None:
        try:
            import telegram as tg
            from telegram.ext import Application as App
            telegram = tg
            Application = App
        except ImportError:
            raise ImportError(
                "python-telegram-bot not installed. "
                "Run: pip install python-telegram-bot"
            )


class TelegramPhotoBot:
    """
    Telegram bot for receiving photo submissions.

    Can run in two modes:
    1. Polling mode - for development/testing
    2. Webhook mode - for production (more efficient)
    """

    def __init__(self):
        _ensure_telegram_imported()

        if not TELEGRAM_BOT_TOKEN:
            raise ValueError("TELEGRAM_BOT_TOKEN not configured")

        self.token = TELEGRAM_BOT_TOKEN
        self.bot_username = TELEGRAM_BOT_USERNAME
        self.queue_manager = QueueManager()
        self.application = None

        # Track user sessions for event association
        self.user_sessions: Dict[int, Dict[str, Any]] = {}

    async def start_command(self, update, context):
        """Handle /start command - welcome new users."""
        user = update.effective_user
        welcome_message = f"""
Welcome to the SBNC Photo Gallery Bot, {user.first_name}!

Send me photos from SBNC events and I'll add them to our gallery.

**How to submit photos:**
1. Just send photos directly to this chat
2. You can send multiple photos at once
3. Add a caption to describe the event (optional)

**Commands:**
/help - Show this help message
/status - Check your recent submissions

Photos are reviewed before being published to the gallery.
        """
        await update.message.reply_text(welcome_message, parse_mode='Markdown')

        # Log new user
        logger.info(f"New Telegram user: {user.id} ({user.username or user.first_name})")

    async def help_command(self, update, context):
        """Handle /help command."""
        help_text = """
**SBNC Photo Gallery Bot**

**Sending Photos:**
- Send photos directly to this chat
- Include captions to help identify the event
- Batch sending is supported

**Tips:**
- Higher resolution photos are better
- Include event name in caption if possible
- Photos are reviewed before publishing

**Commands:**
/start - Welcome message
/help - This help text
/status - Your submission status

Questions? Contact photos@sbnewcomers.org
        """
        await update.message.reply_text(help_text, parse_mode='Markdown')

    async def status_command(self, update, context):
        """Handle /status command - show user's recent submissions."""
        user = update.effective_user
        telegram_id = str(user.id)

        # Get recent submissions from this user
        with get_db() as conn:
            recent = conn.execute('''
                SELECT COUNT(*) as count, MAX(submitted_at) as latest
                FROM ingest_queue
                WHERE source = ? AND source_id LIKE ?
            ''', (SubmissionSource.TELEGRAM, f'tg:{telegram_id}:%')).fetchone()

        if recent and recent['count'] > 0:
            status_text = f"""
**Your Submission Status**

Total photos submitted: {recent['count']}
Last submission: {recent['latest'][:16] if recent['latest'] else 'Unknown'}

Photos are processed and reviewed before appearing in the gallery.
            """
        else:
            status_text = """
**Your Submission Status**

You haven't submitted any photos yet.
Send photos to this chat to contribute to the SBNC gallery!
            """

        await update.message.reply_text(status_text, parse_mode='Markdown')

    async def handle_photo(self, update, context):
        """Handle incoming photos."""
        user = update.effective_user
        message = update.message

        # Get the highest resolution photo
        photo = message.photo[-1]  # Last item is highest resolution

        try:
            # Download the photo
            file = await context.bot.get_file(photo.file_id)

            # Generate unique filename
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            unique_id = str(uuid.uuid4())[:8]
            filename = f"tg_{user.id}_{timestamp}_{unique_id}.jpg"

            # Save to ingest queue directory
            queue_dir = PHOTO_STORAGE_ROOT / 'ingest_queue'
            queue_dir.mkdir(parents=True, exist_ok=True)
            filepath = queue_dir / filename

            await file.download_to_drive(str(filepath))

            # Get caption if provided
            caption = message.caption or ''

            # Queue for processing
            queue_id = self.queue_manager.add_to_queue(
                filepath=str(filepath),
                source=SubmissionSource.TELEGRAM,
                source_id=f"tg:{user.id}:{message.message_id}",
                submitter_name=user.full_name or user.username or f"Telegram User {user.id}",
                submitter_id=str(user.id),
                metadata={
                    'telegram_user_id': user.id,
                    'telegram_username': user.username,
                    'caption': caption,
                    'file_id': photo.file_id,
                    'width': photo.width,
                    'height': photo.height
                }
            )

            # Send confirmation
            await message.reply_text(
                f"Got it! Photo queued for review. (ID: {queue_id[:8]})"
            )

            logger.info(f"Telegram photo queued: {filename} from user {user.id}")

        except Exception as e:
            logger.error(f"Error processing Telegram photo: {e}")
            await message.reply_text(
                "Sorry, there was an error processing your photo. Please try again."
            )

    async def handle_document(self, update, context):
        """Handle photos sent as documents (uncompressed)."""
        user = update.effective_user
        message = update.message
        document = message.document

        # Check if it's an image
        if document.mime_type and document.mime_type.startswith('image/'):
            try:
                # Download the document
                file = await context.bot.get_file(document.file_id)

                # Get original filename extension or default to jpg
                ext = Path(document.file_name).suffix.lower() if document.file_name else '.jpg'
                if ext not in SUPPORTED_IMAGE_EXTENSIONS:
                    ext = '.jpg'

                # Generate unique filename
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                unique_id = str(uuid.uuid4())[:8]
                filename = f"tg_{user.id}_{timestamp}_{unique_id}{ext}"

                # Save to ingest queue directory
                queue_dir = PHOTO_STORAGE_ROOT / 'ingest_queue'
                queue_dir.mkdir(parents=True, exist_ok=True)
                filepath = queue_dir / filename

                await file.download_to_drive(str(filepath))

                # Get caption if provided
                caption = message.caption or ''

                # Queue for processing
                queue_id = self.queue_manager.add_to_queue(
                    filepath=str(filepath),
                    source=SubmissionSource.TELEGRAM,
                    source_id=f"tg:{user.id}:{message.message_id}",
                    submitter_name=user.full_name or user.username or f"Telegram User {user.id}",
                    submitter_id=str(user.id),
                    metadata={
                        'telegram_user_id': user.id,
                        'telegram_username': user.username,
                        'caption': caption,
                        'file_id': document.file_id,
                        'original_filename': document.file_name
                    }
                )

                await message.reply_text(
                    f"Got it! Full-resolution photo queued for review. (ID: {queue_id[:8]})"
                )

                logger.info(f"Telegram document photo queued: {filename} from user {user.id}")

            except Exception as e:
                logger.error(f"Error processing Telegram document: {e}")
                await message.reply_text(
                    "Sorry, there was an error processing your photo. Please try again."
                )
        else:
            await message.reply_text(
                "I can only accept image files. Please send photos!"
            )

    def build_application(self):
        """Build the Telegram application with handlers."""
        from telegram.ext import CommandHandler, MessageHandler, filters

        self.application = Application.builder().token(self.token).build()

        # Command handlers
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("status", self.status_command))

        # Photo handlers
        self.application.add_handler(MessageHandler(filters.PHOTO, self.handle_photo))
        self.application.add_handler(MessageHandler(filters.Document.ALL, self.handle_document))

        return self.application

    def run_polling(self):
        """Run bot in polling mode (for development)."""
        app = self.build_application()
        logger.info(f"Starting Telegram bot @{self.bot_username} in polling mode...")
        app.run_polling()

    def get_webhook_handler(self):
        """
        Get a webhook handler for production use.

        Returns a function that can be called with webhook updates.
        Use with Flask/FastAPI to handle POST requests from Telegram.
        """
        app = self.build_application()
        return app


# Flask/FastAPI webhook endpoint helper
def create_webhook_blueprint():
    """
    Create a Flask blueprint for Telegram webhook.

    Usage in main app:
        from app.ingest.telegram_bot import create_webhook_blueprint
        app.register_blueprint(create_webhook_blueprint(), url_prefix='/telegram')
    """
    from flask import Blueprint, request, jsonify
    import asyncio

    telegram_bp = Blueprint('telegram', __name__)
    bot = None

    @telegram_bp.route('/webhook', methods=['POST'])
    def webhook():
        """Handle incoming Telegram webhook updates."""
        global bot

        # Verify webhook secret if configured
        if TELEGRAM_WEBHOOK_SECRET:
            secret = request.headers.get('X-Telegram-Bot-Api-Secret-Token')
            if secret != TELEGRAM_WEBHOOK_SECRET:
                return jsonify({'error': 'Unauthorized'}), 401

        # Initialize bot on first request
        if bot is None:
            try:
                bot = TelegramPhotoBot()
                bot.build_application()
            except Exception as e:
                logger.error(f"Failed to initialize Telegram bot: {e}")
                return jsonify({'error': 'Bot not configured'}), 500

        # Process update
        try:
            update = telegram.Update.de_json(request.get_json(), bot.application.bot)
            asyncio.run(bot.application.process_update(update))
            return jsonify({'ok': True})
        except Exception as e:
            logger.error(f"Error processing Telegram update: {e}")
            return jsonify({'error': str(e)}), 500

    @telegram_bp.route('/set_webhook', methods=['POST'])
    def set_webhook():
        """Set up the webhook URL with Telegram."""
        data = request.get_json() or {}
        webhook_url = data.get('url')

        if not webhook_url:
            return jsonify({'error': 'URL required'}), 400

        if not TELEGRAM_BOT_TOKEN:
            return jsonify({'error': 'Bot token not configured'}), 500

        import requests

        params = {
            'url': webhook_url,
        }
        if TELEGRAM_WEBHOOK_SECRET:
            params['secret_token'] = TELEGRAM_WEBHOOK_SECRET

        response = requests.post(
            f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setWebhook',
            json=params
        )

        return jsonify(response.json())

    return telegram_bp


# CLI entry point for running bot standalone
if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    bot = TelegramPhotoBot()
    bot.run_polling()
