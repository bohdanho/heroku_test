import os
import logging
from queue import Queue
from threading import Thread
import requests
from flask import Flask, request
from telegram import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton, Bot, Update
from telegram.ext import CommandHandler, MessageHandler, Filters, Dispatcher
import psycopg2

app = Flask(__name__)

TELEGRAM_TOKEN = "1481681024:AAExedkDJ6Z1xkYVLIiszZsB-vOKKBjXlh4"  # Telegram token
switch_array = []  # Special array for search methods (назва, виконавець, текст) [{"switch": "Назва методу пошуку", "chat_id": chat_id}, ...]

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)


# /start
def start(update, context):
    update.message.reply_text('Тебе вітає СБ!')
    help(update, context)


# /about
def about(update, context):
    update.message.reply_text('Це бот для пошуку українських пісень. Якщо маєш якість коментарі, то пиши @bohdanho')


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


# Пошук пісні з першої клавіатури за різними методами
def music_search(update):
    music_search_keyboard = [['За назвою'], ['За виконавцем'], ['За текстом'], ['Назад до пошуку']]
    update.message.reply_text("Вибери за чим проводити пошук: ",
                              reply_markup=ReplyKeyboardMarkup(music_search_keyboard, one_time_keyboard=True))


# Категорії з першої клавіатури
def categories(update):
    parsed_categories = get_parsed_categories()
    categories_keyboard = []
    for item in parsed_categories:
        categories_keyboard.append([item])
    categories_keyboard.append(['Назад до пошуку'])
    update.message.reply_text("Вибери категорію: ",
                              reply_markup=ReplyKeyboardMarkup(categories_keyboard, one_time_keyboard=True))


# Non-command message
def echo(update, context):
    global switch_array
    parsed_categories = get_parsed_categories()  # Парсимо категорії для перевірки чи не є повідомлення із клаввіатури з категоріями
    if update.message.text == "В головне меню":
        # Про всяк випадок чистимо параметри пошуку юзера з switch_array, якщо він вирішив не шукати пісню і повернутись
        for item in switch_array:
            if item["chat_id"] == update.message["chat"]["id"]:
                del item
                break
        delete_2_messages(update)
        help(update, context)
    # Методи пошуку чи категорії
    elif update.message.text == "Пошук пісні":
        delete_2_messages(update)
        music_search(update)
    elif update.message.text == "Категорії":
        delete_2_messages(update)
        categories(update)
    # Поверталки
    elif update.message.text == 'Назад до пошуку':
        delete_4_messages(update)
        spiv(update, context)
    elif update.message.text == 'Назад до категорій':
        delete_2_messages(update)
        categories(update)
    elif update.message.text == 'Назад до методів пошуку':
        # Про всяк випадок чистимо параметри пошуку юзера з switch_array, якщо він вирішив не шукати пісню і повернутись
        for item in switch_array:
            if item["chat_id"] == update.message["chat"]["id"]:
                del item
                break
        delete_2_messages(update)
        music_search(update)
    # Пошук за категоріями
    elif update.message.text in parsed_categories:
        delete_2_messages(update)
        parsed_songs = get_songs_for_category(update.message.text)
        send_songs(update, parsed_songs)
        update.message.reply_text("Що далі? :)",
                                  reply_markup=ReplyKeyboardMarkup([["Назад до категорій"], ["В головне меню"]],
                                                                   one_time_keyboard=True))
        del parsed_songs
    # Різні методи пошуку
    elif update.message.text == 'За назвою':
        delete_2_messages(update)
        update.message.reply_text("Введи назву пісні: ",
                                  reply_markup=ReplyKeyboardMarkup([["Назад до методів пошуку"], ["В головне меню"]], one_time_keyboard=True))
        switch_array.append({
            "switch": 'Назва',
            "chat_id": update.message["chat"]["id"]
        })
    elif update.message.text == 'За виконавцем':
        delete_2_messages(update)
        update.message.reply_text("Введи ім'я виконавця: ",
                                  reply_markup=ReplyKeyboardMarkup([["Назад до методів пошуку"], ["В головне меню"]],
                                                                 one_time_keyboard=True))
        switch_array.append({
            "switch": "Виконавець",
            "chat_id": update.message["chat"]["id"]
        })
    elif update.message.text == 'За текстом':
        delete_2_messages(update)
        update.message.reply_text("Введи частину тексту: ",
                                  reply_markup=ReplyKeyboardMarkup([["Назад до методів пошуку"], ["В головне меню"]],
                                                                   one_time_keyboard=True))
        switch_array.append({
            "switch": "Текст",
            "chat_id": update.message["chat"]["id"]
        })
    elif (item["chat_id"] == update.message["chat"]["id"] for item in switch_array):
        for item in switch_array:
            if item["chat_id"] == update.message["chat"]["id"]:
                parsed_songs = []
                # Searching for songs in user-selected way with correlation to position in Songs table in DB
                if item["switch"] == "Назва":
                    parsed_songs = get_songs_for_search(update.message.text, 1)
                elif item["switch"] == "Виконавець":
                    parsed_songs = get_songs_for_search(update.message.text, 2)
                elif item["switch"] == "Текст":
                    parsed_songs = get_songs_for_search(update.message.text, 4)
                send_songs(update, parsed_songs)
                update.message.reply_text("Що далі? :)",
                                          reply_markup=ReplyKeyboardMarkup(
                                              [["Назад до методів пошуку"], ["В головне меню"]],
                                              one_time_keyboard=True))
                del item, parsed_songs  # Deleting used data to avoid overfilling the RAM
                break
    else:  # Answer on every other message
        print(update)
        update.message.reply_text("Дякую, що написав, " + update['message']['chat']['first_name'] + ", ми обов'язково подумаємо над цим")
    del parsed_categories  # Deleting used data to avoid overfilling the RAM


# If error happens
def error(update, context):
    logger.warning('Update "%s" caused error "%s"', update, context.error)


# Receive all categories our songs currently have
def get_parsed_categories():
    cursor.execute('SELECT * FROM public."Spivanik"')
    parsed_categories = []
    record = cursor.fetchall()
    for row in record:  # Searching for all categories in every row
        if row[3] not in parsed_categories:  # Checking if we do not have this category in our array
            parsed_categories.append(row[3])
    return parsed_categories


# Search for all songs of onr defined category
def get_songs_for_category(category):
    songs = []
    cursor.execute('SELECT * FROM public."Spivanik"')
    record = cursor.fetchall()
    for row in record:
        if row[3] == category:
            songs.append(row)
    return songs


# Music search in desired field. Passing the search key and the position in the SQL row/array
def get_songs_for_search(key, position):
    songs = []
    cursor.execute('SELECT * FROM public."Spivanik"')
    record = cursor.fetchall()
    for row in record:
        try:
            if key.lower() in row[position].lower():
                songs.append(row)
        except AttributeError:  # Якщо раптом нема тексту у пісні, то не вийде пошукати
            print("Нема тексту")
    return songs


# Компонуємо та відправляємо повідомлення з піснями, які ми витягнули з ДБ, вставлямо весь наявний контент
def send_songs(update, parsed_songs):
    if parsed_songs:
        for song in parsed_songs:
            inline_keyboard = []
            message_string = f'"{song[1].upper()}"\nВиконавець: {song[2]}\nЖанр: {song[3]}\n'
            # Чекаємо на наявність кожної характеристики в рядку
            if song[4]:
                message_string += f"Текст:\n{song[4]}"
            if song[5] and "http" in song[5]:
                inline_keyboard.append([InlineKeyboardButton(text="Аккорди", url=song[5])])
            if song[6] and "http" in song[6]:
                inline_keyboard.append([InlineKeyboardButton(text="Таби", url=song[6])])
            if song[7] and "http" in song[7]:
                inline_keyboard.append([InlineKeyboardButton(text="Кліп", url=song[7])])
            update.message.reply_text(message_string,
                                      reply_markup=InlineKeyboardMarkup(inline_keyboard))
            del inline_keyboard, message_string  # Deleting used data to avoid overfilling the RAM
    else:
        update.message.reply_text("Нічого не знайдено :(")
    del parsed_songs  # Deleting used data to avoid overfilling the RAM


# Delete previous 2 messages after returning to the previous stage via custom keyboard
def delete_2_messages(update):
    chat_id = update["message"]["chat"]["id"]
    last_message_id = update["message"]["message_id"]
    for i in range(2):
        requests.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/deleteMessage?chat_id={chat_id}&message_id={last_message_id-i}")


# Delete previous 4 messages after returning to the previous stage via custom keyboard
def delete_4_messages(update):
    chat_id = update["message"]["chat"]["id"]
    last_message_id = update["message"]["message_id"]
    for i in range(4):
        requests.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/deleteMessage?chat_id={chat_id}&message_id={last_message_id-i}")


# Receiving every update from telegram on webhook
@app.route(f'/{TELEGRAM_TOKEN}', methods=['GET', 'POST'])
def webhook():
    if request.method == "POST":
        # retrieve the message in JSON and then transform it to Telegram object
        update = Update.de_json(request.get_json(force=True), bot=bot)
        logger.info("Update received! " + update.message.text)
        update_queue.put(update)
        return "OK"
    else:
        return "BAD"


# Launching the Dispatcher
def launch_dispatcher():
    # Different command handlers
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("about", about))
    dp.add_handler(CommandHandler("help", help))
    dp.add_handler(CommandHandler("spiv", spiv))
    # On message
    dp.add_handler(MessageHandler(Filters.text, echo))
    # log all errors
    dp.add_error_handler(error)
    # start the dispatcher in different thread to process every update
    thread = Thread(target=dp.start, name='dp')
    thread.start()


# Starting the application
if __name__ == '__main__':
    bot = Bot(TELEGRAM_TOKEN)  # Creating the Bot object with TELEGRAM_TOKEN
    update_queue = Queue()     # Creating the queue for the Dispatcher
    dp = Dispatcher(bot, update_queue)  # Creating the Dispatcher object
    launch_dispatcher()        # Preparing and launching the Dispatcher
    bot.setWebhook(f"https://testflasksbbot.herokuapp.com/{TELEGRAM_TOKEN}")  # Setting the WebHook for bot to receive updates
    try:
        #db_url = os.environ['DATABASE_URL']
        db_url = "postgres://jsflplcerunvml:7ea5c96a2749879d490d341809f09614f2121eaf4f29ed98f39dda6e1ddb4841@ec2-54-78-45-84.eu-west-1.compute.amazonaws.com:5432/d4eopvjlccalgh"
        connection = psycopg2.connect(db_url, sslmode='require')  # Connecting to Heroku PostgresSQL
        cursor = connection.cursor()  # Setting up the cursor
    except:
        print(1)
        bot.send_message(chat_id=548999439, text="Problems with DB")
    app.run(host="0.0.0.0", port=int(os.environ.get('PORT', 5000)), threaded=True)  # Launching the FLask app on appropriate IP and PORT
