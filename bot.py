import os
import json
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from messages import messages
from scoring import evaluate_score

with open("questions.json", "r", encoding="utf-8") as f:
    questions = json.load(f)

user_data = {}

ASKING = 1

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data[update.effective_chat.id] = {
        "current": 0,
        "score": 0,
        "lang": "en"
    }

    # Detect Farsi
    if "fa" in update.effective_user.language_code:
        user_data[update.effective_chat.id]["lang"] = "fa"
        await update.message.reply_text(messages["start_fa"])
    else:
        await update.message.reply_text(messages["start_en"])

    return await ask_question(update, context)

async def ask_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = user_data[update.effective_chat.id]
    q = questions[data["current"]]
    options = [[opt] for opt in q["options"]]

    await update.message.reply_text(
        f"Q{data['current'] + 1}: {q['question']}",
        reply_markup=ReplyKeyboardMarkup(options, one_time_keyboard=True)
    )
    return ASKING

async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    data = user_data[chat_id]
    q = questions[data["current"]]

    if update.message.text.strip() == q["answer"]:
        data["score"] += 1

    data["current"] += 1

    if data["current"] < 20:
        return await ask_question(update, context)
    else:
        level, ielts = evaluate_score(data["score"])
        lang = data["lang"]
        msg = messages[f"result_{lang}"].format(level=level, ielts=ielts)
        await update.message.reply_text(msg)
        return ConversationHandler.END

app = ApplicationBuilder().token(os.environ["8023160531:AAEHGg8_CAd0ceIceT6isGNH1Am8J2wJYNs"]).build()


conv_handler = ConversationHandler(
    entry_points=[CommandHandler("start", start)],
    states={ASKING: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_answer)]},
    fallbacks=[]
)

app.add_handler(conv_handler)

if __name__ == "__main__":
    app.run_polling()
