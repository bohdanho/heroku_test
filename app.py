from flask import Flask, request
import logging
from telegram import Update, Bot
from telegram.ext import Updater
import os

app = Flask(__name__)
TELEGRAM_TOKEN = "1481681024:AAExedkDJ6Z1xkYVLIiszZsB-vOKKBjXlh4"
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

logger = logging.getLogger(__name__)

@app.route(f"/{TELEGRAM_TOKEN}", methods=['GET', 'POST'])
def webhook():
    if request.method == "POST":
        # retrieve the message in JSON and then transform it to Telegram object
        update = Update.de_json(request.get_json(force=True))
        print(update)
        logger.info("Update received! " + update.message.text)
        dp.process_update(update)
        return "OK"
    else:
        return "BAD"

    


if __name__ == "__main__":
    PORT = int(os.environ.get('PORT', '8443'))
    updater = Updater(TELEGRAM_TOKEN)
    updater.start_webhook(listen="0.0.0.0",
                          port=PORT,
                          url_path=TELEGRAM_TOKEN)
    updater.bot.setWebhook(f"https://testflasksbbot.herokuapp.com/{TELEGRAM_TOKEN}")
    dp = updater.dispatcher
    app.run(host="0.0.0.0", port=int(os.environ.get('PORT', 5000)), threaded=True)
