from flask import Flask, request
import logging
from telegram import Update, Bot, ReplyKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, Dispatcher
from threading import Thread
import os
from queue import Queue

app = Flask(__name__)
TELEGRAM_TOKEN = "1481681024:AAExedkDJ6Z1xkYVLIiszZsB-vOKKBjXlh4"
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

logger = logging.getLogger(__name__)


def start(update, context):
    print("Started!")
    update.message.reply_text('Тебе вітає СБ')
    help(update, context)


# /about
def about(update, context):
    update.message.reply_text('Якщо треба допомога, то пиши мені в пп')


# /help
def help(update, context):
    update.message.reply_text('Вибирай потрібну команду:\n'
                              '/help - Список доступних команд\n'
                              '/about - Дізнатись більше про СБ\n'
                              '/spiv - Пошук пісень')


# /spiv
def spiv(update, context):
    reply_keyboard = [['Пошук пісні', 'Категорії'],
                      ['В головне меню']]
    update.message.reply_text("Вибери метод пошуку: ", reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True))


def echo(update, context):
    print(update)
    update.message.reply_text("Greeting, " + update['message']['chat']['first_name'])


def error(update, context):
    """Log Errors caused by Updates."""
    logger.warning('Update "%s" caused error "%s"', update, context.error)


def main():
    # Boot up the bot with const TELEGRAM_TOKEN
    # Different commands
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("about", about))
    dp.add_handler(CommandHandler("help", help))
    dp.add_handler(CommandHandler("spiv", spiv))
    # On message
    dp.add_handler(MessageHandler(Filters.text, echo))

    # log all errors
    dp.add_error_handler(error)

    thread = Thread(target=dp.start, name='dp')
    thread.start()


@app.route(f"/{TELEGRAM_TOKEN}", methods=['GET', 'POST'])
def webhook():
    if request.method == "POST":
        # retrieve the message in JSON and then transform it to Telegram object
        update = Update.de_json(request.get_json(force=True), bot=bot)
        print(update)
        logger.info("Update received! " + update.message.text)

        update_queue.put(update)
        dp.process_update(update)
        return "OK"
    else:
        return "BAD"


if __name__ == "__main__":
    PORT = int(os.environ.get('PORT', '8443'))
    bot = Bot(TELEGRAM_TOKEN)
    update_queue = Queue()
    dp = Dispatcher(bot, update_queue)
    main()
    bot.setWebhook(f"https://testflasksbbot.herokuapp.com/{TELEGRAM_TOKEN}")
    app.run(host="0.0.0.0", port=int(os.environ.get('PORT', 5000)), threaded=True)
