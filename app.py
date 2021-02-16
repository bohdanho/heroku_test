import os
import logging
from queue import Queue
from threading import Thread
import requests
from flask import Flask, request
from telegram import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton, Bot, Update
from telegram.ext import CommandHandler, MessageHandler, Filters, Dispatcher
import psycopg2


class User:
    def __init__(self, chat_id, username, text):
        self.chat_id = chat_id
        self.username = username
        self.text = text
        self.switch = None
        self.last_msg = None

    def change_text(self):
        if self.text:
            self.text = False
        else:
            self.text = True

    def change_switch(self, switch):
        self.switch = switch

    def change_last_msg(self, msg_id):
        self.last_msg = msg_id


app = Flask(__name__)

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]  # Telegram token
switch_array = []  # Special array for search methods (назва, виконавець, текст) [{"switch": "Назва методу пошуку", "chat_id": chat_id}, ...]
messages_to_be_deleted = []  # Записуємо сюди останні повідомлення від бота до кожного chat_id [{"chat_id": chat_id, "last_msg_id": msg_id}, ...]
users = []

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)


# /start
def start(update, context):
    update.message.reply_text('Тебе вітає СБ!')
    chat = update.message["chat"]
    check_if_user_in_users(chat)
    help(update, context)
    del chat


# /about
def about(update, context):
    update.message.reply_text('Це бот для пошуку українських пісень. Якщо маєш якість коментарі, то пиши @bohdanho')


# /help
def help(update, context):
    update.message.reply_text('Вибирай потрібну команду:\n'
                              '/help - Список доступних команд\n'
                              '/about - Дізнатись більше про СБ\n'
                              '/settings - Змінити налаштування\n'
                              '/spiv - Пошук пісень')


# /settings
def settings(update, context):
    chat_id = update.message["chat"]["id"]
    user = find_user(chat_id)
    if user.text:
        reply_text = "У тебе ввімкнуте отримання текстів"
        reply_keyboard = [['Вимкнути'],
                          ['Назад']]
    else:
        reply_text = "У тебе вимкнуте отримання текстів"
        reply_keyboard = [['Ввімкнути'],
                          ['Назад']]
    msg_id = update.message.reply_text(reply_text, reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True))["message_id"]
    update_msg_to_be_deleted(chat_id, msg_id)


# /spiv
def spiv(update, context):
    reply_keyboard = [['Пошук пісні', 'Категорії'],
                      ['В головне меню']]
    msg_id = update.message.reply_text("Вибери метод пошуку: ", reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True))["message_id"]
    chat_id = update.message["chat"]["id"]
    update_msg_to_be_deleted(chat_id, msg_id)


# Пошук пісні з першої клавіатури за різними методами
def music_search(update):
    music_search_keyboard = [['За назвою'], ['За виконавцем'], ['За текстом'], ['Назад до пошуку']]
    msg_id = update.message.reply_text("Вибери за чим проводити пошук: ",
                              reply_markup=ReplyKeyboardMarkup(music_search_keyboard, one_time_keyboard=True))["message_id"]
    chat_id = update.message["chat"]["id"]
    update_msg_to_be_deleted(chat_id, msg_id)


# Категорії з першої клавіатури
def categories(update):
    parsed_categories = get_parsed_categories()
    categories_keyboard = []
    for item in parsed_categories:
        categories_keyboard.append([item])
    categories_keyboard.append(['Назад до пошуку'])
    msg_id = update.message.reply_text("Вибери категорію: ",
                              reply_markup=ReplyKeyboardMarkup(categories_keyboard, one_time_keyboard=True))["message_id"]
    chat_id = update.message["chat"]["id"]
    update_msg_to_be_deleted(chat_id, msg_id)


# Non-command message
def echo(update, context):
    global switch_array
    chat_id = update.message["chat"]["id"]
    user = find_user(chat_id)
    parsed_categories = get_parsed_categories()  # Парсимо категорії для перевірки чи не є повідомлення із клавіатури з категоріями
    # Зміна налаштувань
    if update.message.text == "Вимкнути" or update.message.text == "Ввімкнути":
        user.change_text()
        delete_2_messages(update)
    if update.message.text == "В головне меню":
        # Про всяк випадок чистимо параметри пошуку юзера з switch_array, якщо він вирішив не шукати пісню і повернутись
        for item in switch_array:
            if item["chat_id"] == chat_id:
                del item
                break
        delete_2_messages(update)
    # Методи пошуку чи категорії
    elif update.message.text == "Пошук пісні":
        delete_2_messages(update)
        music_search(update)
    elif update.message.text == "Категорії":
        delete_2_messages(update)
        categories(update)
    # Поверталки
    elif update.message.text == 'Назад':
        delete_2_messages(update)
    elif update.message.text == 'Назад до пошуку':
        delete_2_messages(update)
        spiv(update, context)
    elif update.message.text == 'Назад до категорій':
        delete_2_messages(update)
        categories(update)
    elif update.message.text == 'Назад до методів пошуку':
        # Про всяк випадок чистимо параметри пошуку юзера з switch_array, якщо він вирішив не шукати пісню і повернутись
        for item in switch_array:
            if item["chat_id"] == chat_id:
                del item
                break
        delete_2_messages(update)
        music_search(update)
    # Пошук за категоріями
    elif update.message.text in parsed_categories:
        delete_2_messages(update)
        parsed_songs = get_songs_for_category(update.message.text)
        send_songs(update, parsed_songs, user.text)
        msg_id = update.message.reply_text("Що далі? :)",
                                  reply_markup=ReplyKeyboardMarkup([["Назад до категорій"], ["В головне меню"]],
                                                                   one_time_keyboard=True))["message_id"]
        update_msg_to_be_deleted(chat_id, msg_id)
        del parsed_songs
    # Різні методи пошуку
    elif update.message.text == 'За назвою':
        delete_2_messages(update)
        msg_id = update.message.reply_text("Введи назву пісні: ",
                                  reply_markup=ReplyKeyboardMarkup([["Назад до методів пошуку"], ["В головне меню"]], one_time_keyboard=True))["message_id"]
        update_msg_to_be_deleted(chat_id, msg_id)
        switch_array.append({
            "switch": 'Назва',
            "chat_id": chat_id
        })
    elif update.message.text == 'За виконавцем':
        delete_2_messages(update)
        msg_id = update.message.reply_text("Введи ім'я виконавця: ",
                                  reply_markup=ReplyKeyboardMarkup([["Назад до методів пошуку"], ["В головне меню"]],
                                                                 one_time_keyboard=True))["message_id"]
        update_msg_to_be_deleted(chat_id, msg_id)
        switch_array.append({
            "switch": "Виконавець",
            "chat_id": chat_id
        })
    elif update.message.text == 'За текстом':
        delete_2_messages(update)
        msg_id = update.message.reply_text("Введи частину тексту: ",
                                  reply_markup=ReplyKeyboardMarkup([["Назад до методів пошуку"], ["В головне меню"]],
                                                                   one_time_keyboard=True))["message_id"]
        update_msg_to_be_deleted(chat_id, msg_id)
        switch_array.append({
            "switch": "Текст",
            "chat_id": chat_id
        })
    elif (item["chat_id"] == chat_id for item in switch_array):
        for item in switch_array:
            if item["chat_id"] == chat_id:
                parsed_songs = []
                # Searching for songs in user-selected way with correlation to position in Songs table in DB
                if item["switch"] == "Назва":
                    parsed_songs = get_songs_for_search(update.message.text, 1)
                elif item["switch"] == "Виконавець":
                    parsed_songs = get_songs_for_search(update.message.text, 2)
                elif item["switch"] == "Текст":
                    parsed_songs = get_songs_for_search(update.message.text, 4)
                send_songs(update, parsed_songs, user.text)
                msg_id = update.message.reply_text("Що далі? :)",
                                          reply_markup=ReplyKeyboardMarkup(
                                              [["Назад до методів пошуку"], ["В головне меню"]],
                                              one_time_keyboard=True))["message_id"]
                update_msg_to_be_deleted(chat_id, msg_id)
                del item, parsed_songs  # Deleting used data to avoid overfilling the RAM
                break
    else:  # Answer on every other message
        print(update)
        update.message.reply_text("Дякую, що написав, " + update['message']['chat']['first_name'] + ", ми обов'язково подумаємо над цим")
    del parsed_categories  # Deleting used data to avoid overfilling the RAM


# If error happens
def error(update, context):
    logger.warning('Update "%s" caused error "%s"', update, context.error)


def check_if_user_in_users(chat):
    global users
    chat_id = chat["id"]
    for user in users:
        if user.chat_id == chat_id:
            return 1
    users.append(User(chat_id, chat["username"], True))


def find_user(chat_id):
    global users
    for user in users:
        if user.chat_id == chat_id:
            return user



# Receive all categories our songs currently have
def get_parsed_categories():
    cursor.execute('SELECT * FROM public."Spivanik"')
    parsed_categories = []
    record = cursor.fetchall()
    for row in record:  # Searching for all categories in every row
        if row[3] and row[3] not in parsed_categories:  # Checking if we do not have this category in our array
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
def send_songs(update, parsed_songs, text=None):
    if parsed_songs:
        for song in parsed_songs:
            inline_keyboard = []
            message_string = f'"{song[1].upper()}"\nВиконавець: {song[2]}\nЖанр: {song[3]}\n'
            # Чекаємо на наявність кожної характеристики в рядку
            if song[4] and text:
                message_string += f"Текст:\n{song[4]}"
            if song[5] and "http" in song[5]:
                inline_keyboard.append([InlineKeyboardButton(text="Аккорди 🎼", url=song[5])])
            if song[6] and "http" in song[6]:
                inline_keyboard.append([InlineKeyboardButton(text="Таби 🎶", url=song[6])])
            if song[7] and "http" in song[7]:
                inline_keyboard.append([InlineKeyboardButton(text="Кліп 🎬", url=song[7])])
            update.message.reply_text(message_string,
                                      reply_markup=InlineKeyboardMarkup(inline_keyboard))
            del inline_keyboard, message_string  # Deleting used data to avoid overfilling the RAM
    else:
        update.message.reply_text("Нічого не знайдено :(")
    del parsed_songs  # Deleting used data to avoid overfilling the RAM


# Updating this array in order to delete appropriate messages in the future
def update_msg_to_be_deleted(chat_id, msg_id):
    global messages_to_be_deleted
    checker = False
    for msg in messages_to_be_deleted:
        if msg["chat_id"] == chat_id:
            msg["last_msg_id"] = msg_id
            checker = True
            break
    if not checker:
        messages_to_be_deleted.append({"chat_id": chat_id, "last_msg_id": msg_id})


# Delete previous 2 messages after returning to the previous stage via custom keyboard
def delete_2_messages(update):
    global messages_to_be_deleted
    chat_id = update["message"]["chat"]["id"]
    last_message_id = update["message"]["message_id"]
    try:
        bot_message_id = update["message"]["message_id"] - 1
        for msg in messages_to_be_deleted:
            if msg["chat_id"] == chat_id:
                bot_message_id = msg["last_msg_id"]
                del msg
                break
    except:
        bot_message_id = update["message"]["message_id"] - 1
    requests.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/deleteMessage?chat_id={chat_id}&message_id={last_message_id}")
    requests.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/deleteMessage?chat_id={chat_id}&message_id={bot_message_id}")


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
    dp.add_handler(CommandHandler("settings", settings))
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
    bot.setWebhook(f"https://testflasksbbot.herokuapp.com /{TELEGRAM_TOKEN}")  # Setting the WebHook for bot to receive updates
    try:
        #db_url = os.environ['DATABASE_URL']
        db_url = "postgres://jsflplcerunvml:7ea5c96a2749879d490d341809f09614f2121eaf4f29ed98f39dda6e1ddb4841@ec2-54-78-45-84.eu-west-1.compute.amazonaws.com:5432/d4eopvjlccalgh"
        connection = psycopg2.connect(db_url, sslmode='require')  # Connecting to Heroku PostgresSQL
        cursor = connection.cursor()  # Setting up the cursor
    except:
        bot.send_message(chat_id=548999439, text="Problems with DB")
    app.run(host="0.0.0.0", port=int(os.environ.get('PORT', 5000)), threaded=True)  # Launching the Flask app on appropriate IP and PORT
