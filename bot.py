import os
import json
import logging
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler
)
from telegram.error import Conflict
from messages import messages
from scoring import evaluate_score

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Load questions
with open("questions.json", "r", encoding="utf-8") as f:
    questions = json.load(f)

# Conversation states
ASKING = 1

# Global user data storage (consider using Redis for production)
user_data = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Initialize user session and detect language"""
    try:
        user_data[update.effective_chat.id] = {
            "current": 0,
            "score": 0,
            "lang": "en"
        }

        # Detect Farsi
        if update.effective_user.language_code and "fa" in update.effective_user.language_code:
            user_data[update.effective_chat.id]["lang"] = "fa"
            await update.message.reply_text(messages["start_fa"])
        else:
            await update.message.reply_text(messages["start_en"])

        return await ask_question(update, context)
    except Exception as e:
        logger.error(f"Error in start handler: {e}")
        await update.message.reply_text("An error occurred. Please try again.")
        return ConversationHandler.END

async def ask_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ask the next question to the user"""
    try:
        data = user_data[update.effective_chat.id]
        q = questions[data["current"]]
        options = [[opt] for opt in q["options"]]

        await update.message.reply_text(
            f"Q{data['current'] + 1}: {q['question']}",
            reply_markup=ReplyKeyboardMarkup(options, one_time_keyboard=True)
        )
        return ASKING
    except Exception as e:
        logger.error(f"Error asking question: {e}")
        await update.message.reply_text("Error loading questions. Please try /start again.")
        return ConversationHandler.END

async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process user's answer and continue conversation"""
    try:
        chat_id = update.effective_chat.id
        data = user_data[chat_id]
        q = questions[data["current"]]

        if update.message.text.strip() == q["answer"]:
            data["score"] += 1

        data["current"] += 1

        if data["current"] < len(questions):
            return await ask_question(update, context)
        else:
            level, ielts = evaluate_score(data["score"])
            lang = data["lang"]
            msg = messages[f"result_{lang}"].format(level=level, ielts=ielts)
            await update.message.reply_text(msg, reply_markup=None)  # Remove keyboard
            return ConversationHandler.END
    except Exception as e:
        logger.error(f"Error handling answer: {e}")
        await update.message.reply_text("Error processing your answer. Please try /start again.")
        return ConversationHandler.END

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors in the bot"""
    logger.error(f'Update {update} caused error {context.error}')
    try:
        await update.message.reply_text("An error occurred. Please try again or /start over.")
    except:
        pass  # In case the error is not message-related

def create_application():
    """Initialize and configure the bot application"""
    token = os.getenv('BOT_TOKEN')
    if not token:
        logger.error("BOT_TOKEN environment variable not set!")
        raise ValueError("Missing BOT_TOKEN")
    
    application = ApplicationBuilder().token(token).build()
    
    # Conversation handler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            ASKING: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_answer)]
        },
        fallbacks=[]
    )
    
    application.add_handler(conv_handler)
    application.add_error_handler(error_handler)
    
    return application

def run_application(application):
    """Run the bot in appropriate mode based on environment"""
    webhook_url = os.getenv('WEBHOOK_URL')
    port = int(os.getenv('PORT', 5000))
    
    try:
        if webhook_url and 'RENDER' in os.environ:  # Production mode with webhook
            logger.info("Starting in webhook mode")
            application.run_webhook(
                listen="0.0.0.0",
                port=port,
                webhook_url=f"{webhook_url}/telegram",
                secret_token=os.getenv('WEBHOOK_SECRET')
            )
        else:  # Development mode with polling
            logger.info("Starting in polling mode")
            application.run_polling()
    except Conflict as e:
        logger.error(f"Bot conflict detected: {e}")
    except Exception as e:
        logger.error(f"Fatal error: {e}")

if __name__ == "__main__":
    app = create_application()
    run_application(app)
