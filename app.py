import os
import logging
from queue import Queue
from threading import Thread, Timer
import requests
from flask import Flask, request
from telegram import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton, Bot, Update
from telegram.ext import CommandHandler, MessageHandler, Filters, Dispatcher
import pygsheets
import json
import time


class User:
    def __init__(self, chat_id, username, text):
        self.chat_id = chat_id
        self.username = username
        self.text = text
        self.switch = None
        self.searching = False
        self.last_msg = None

    def change_text(self):
        if self.text:
            self.text = False
        else:
            self.text = True


class GSheetsManager:
    def __init__(self):
        self.client = pygsheets.authorize(service_account_env_var='GOOGLE_API')
        self.sheet = self.client.open('Spivanik_songs').sheet1
        self.data = self.sheet.get_all_records(empty_value='', head=1, majdim='ROWS', numericise_data=True)
        self.timeout = 10.0
        Timer(self.timeout, self.update_data).start()

    def update_data(self):
        self.data = self.sheet.get_all_records(empty_value='', head=1, majdim='ROWS', numericise_data=True)
        Timer(self.timeout, self.update_data).start()

    def get_parsed_categories(self):
        parsed_categories = []
        for row in self.data:
            for category in row['Категорії'].split(';'):
                if category not in parsed_categories:
                    parsed_categories.append(category)
        return parsed_categories

    def get_songs_for_category(self, category):
        songs = []
        for row in self.data:
            if category in row['Категорії']:
                songs.append(row)
        print(songs)
        return songs

    def get_songs_for_search(self, key, position):
        songs = []
        for row in self.data:
            try:
                if key.lower() in row[position].lower():
                    songs.append(row)
            except AttributeError:  # Якщо раптом нема тексту у пісні, то не вийде пошукати
                print("Нема тексту")
        return songs


app = Flask(__name__)

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]  # Telegram token
users = []

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)


# /start
def start(update, context):
    update.message.reply_text('Тебе вітає СБ!💙💛')
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
    user.searching = False
    if user.text:
        reply_text = "У тебе ввімкнуте отримання текстів"
        reply_keyboard = [['Вимкнути'],
                          ['Назад']]
    else:
        reply_text = "У тебе вимкнуте отримання текстів"
        reply_keyboard = [['Ввімкнути'],
                          ['Назад']]
    msg_id = update.message.reply_text(reply_text, reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True))["message_id"]
    user.last_msg = msg_id


# /spiv
def spiv(update, context):
    reply_keyboard = [['Пошук пісні', 'Категорії'],
                      ['В головне меню']]
    msg_id = update.message.reply_text("Вибери метод пошуку: ", reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True))["message_id"]
    chat_id = update.message["chat"]["id"]
    user = find_user(chat_id)
    user.searching = False
    user.last_msg = msg_id


# Пошук пісні з першої клавіатури за різними методами
def music_search(update, user):
    music_search_keyboard = [['За назвою'], ['За виконавцем'], ['За текстом'], ['Назад до пошуку']]
    msg_id = update.message.reply_text("Вибери за чим проводити пошук: ",
                              reply_markup=ReplyKeyboardMarkup(music_search_keyboard, one_time_keyboard=True))["message_id"]
    user.last_msg = msg_id


# Категорії з першої клавіатури
def categories(update, user):
    parsed_categories = gsheets_manager.get_parsed_categories()
    categories_keyboard = []
    for item in parsed_categories:
        categories_keyboard.append([item])
    categories_keyboard.append(['Назад до пошуку'])
    msg_id = update.message.reply_text("Вибери категорію: ",
                              reply_markup=ReplyKeyboardMarkup(categories_keyboard, one_time_keyboard=True))["message_id"]
    user.last_msg = msg_id


# Non-command message
def echo(update, context):
    chat_id = update.message["chat"]["id"]
    user = find_user(chat_id)
    parsed_categories = gsheets_manager.get_parsed_categories()  # Парсимо категорії для перевірки чи не є повідомлення із клавіатури з категоріями
    # Зміна налаштувань
    if update.message.text == "Вимкнути" or update.message.text == "Ввімкнути":
        user.change_text()
        delete_2_messages(update, user.last_msg)
    elif update.message.text == "В головне меню":
        # Про всяк випадок чистимо параметри пошуку юзера з switch_array, якщо він вирішив не шукати пісню і повернутись
        user.searching = False
        delete_2_messages(update, user.last_msg)
    # Методи пошуку чи категорії
    elif update.message.text == "Пошук пісні":
        delete_2_messages(update, user.last_msg)
        music_search(update, user)
    elif update.message.text == "Категорії":
        delete_2_messages(update, user.last_msg)
        categories(update, user)
    # Поверталки
    elif update.message.text == 'Назад':
        delete_2_messages(update, user.last_msg)
    elif update.message.text == 'Назад до пошуку':
        delete_2_messages(update, user.last_msg)
        spiv(update, context)
    elif update.message.text == 'Назад до категорій':
        delete_2_messages(update, user.last_msg)
        categories(update, user)
    elif update.message.text == 'Назад до методів пошуку':
        # Про всяк випадок чистимо параметри пошуку юзера з switch_array, якщо він вирішив не шукати пісню і повернутись
        user.searching = False
        delete_2_messages(update, user.last_msg)
        music_search(update, user)
    # Пошук за категоріями
    elif update.message.text in parsed_categories:
        delete_2_messages(update, user.last_msg)
        parsed_songs = gsheets_manager.get_songs_for_category(update.message.text)
        send_songs(update, parsed_songs, user.text)
        msg_id = update.message.reply_text("Що далі? :)",
                                  reply_markup=ReplyKeyboardMarkup([["Назад до категорій"], ["В головне меню"]],
                                                                   one_time_keyboard=True))["message_id"]
        user.last_msg = msg_id
        del parsed_songs
    # Різні методи пошуку
    elif update.message.text == 'За назвою':
        delete_2_messages(update, user.last_msg)
        msg_id = update.message.reply_text("Введи назву пісні: ",
                                  reply_markup=ReplyKeyboardMarkup([["Назад до методів пошуку"], ["В головне меню"]], one_time_keyboard=True))["message_id"]
        user.last_msg = msg_id
        user.switch = 'Назва'
        user.searching = True
    elif update.message.text == 'За виконавцем':
        delete_2_messages(update, user.last_msg)
        msg_id = update.message.reply_text("Введи ім'я виконавця: ",
                                  reply_markup=ReplyKeyboardMarkup([["Назад до методів пошуку"], ["В головне меню"]],
                                                                 one_time_keyboard=True))["message_id"]
        user.last_msg = msg_id
        user.switch = 'Виконавець'
        user.searching = True
    elif update.message.text == 'За текстом':
        delete_2_messages(update, user.last_msg)
        msg_id = update.message.reply_text("Введи частину тексту: ",
                                  reply_markup=ReplyKeyboardMarkup([["Назад до методів пошуку"], ["В головне меню"]],
                                                                   one_time_keyboard=True))["message_id"]
        user.last_msg = msg_id
        user.switch = 'Текст'
        user.searching = True
    elif user.searching:
        # Searching for songs in user-selected way with correlation to position in Songs table in DB
        parsed_songs = gsheets_manager.get_songs_for_search(update.message.text, user.switch)
        send_songs(update, parsed_songs, user.text)
        msg_id = update.message.reply_text("Що далі? :)", reply_markup=ReplyKeyboardMarkup(
                                      [["Назад до методів пошуку"], ["В головне меню"]],
                                      one_time_keyboard=True))["message_id"]
        user.last_msg = msg_id
        user.searching = False
        del parsed_songs  # Deleting used data to avoid overfilling the RAM
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


# Компонуємо та відправляємо повідомлення з піснями, які ми витягнули з ДБ, вставлямо весь наявний контент
def send_songs(update, parsed_songs, text=None):
    print(1, parsed_songs)
    if parsed_songs:
        for song in parsed_songs:
            print(2, song)
            inline_keyboard = []
            message_string = f'🏷 "{song["Назва"].upper()}"\n🎤 Виконавець: {song["Виконавець"]}\n💿 Жанр: {song["Категорії"]}\n'
            print(3, message_string)
            # Чекаємо на наявність кожної характеристики в рядку
            if song['Текст'] and text:
                message_string += f"📜 Текст:\n{song[4]}"
                print(4, message_string)
            if song['Акорди'] and "http" in song['Акорди']:
                inline_keyboard.append([InlineKeyboardButton(text="Акорди 🎼", url=song['Акорди'])])
                print(5, message_string)
            if song['Кліп'] and "http" in song['Кліп']:
                inline_keyboard.append([InlineKeyboardButton(text="Кліп 🎬", url=song['Кліп'])])
                print(6, message_string)
            if song['Таби'] and "http" in song['Таби']:
                print(7, message_string, song['Таби'])
                # inline_keyboard.append([InlineKeyboardButton(text="Таби 🎶", url=song['Таби'])])
                bot.send_photo(chat_id=update.message['chat']['id'], photo=song['Таби'], caption=message_string, reply_markup=InlineKeyboardMarkup(inline_keyboard))
            else:
                update.message.reply_text(message_string, reply_markup=InlineKeyboardMarkup(inline_keyboard))
            del inline_keyboard, message_string  # Deleting used data to avoid overfilling the RAM
    else:
        update.message.reply_text("Нічого не знайдено :(")
    del parsed_songs  # Deleting used data to avoid overfilling the RAM


# Delete previous 2 messages after returning to the previous stage via custom keyboard
def delete_2_messages(update, bot_message_id=None):
    chat_id = update["message"]["chat"]["id"]
    last_message_id = update["message"]["message_id"]
    if bot_message_id:
        pass
    else:
        bot_message_id = update["message"]["message_id"] - 1
    requests.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/deleteMessage?chat_id={chat_id}&message_id={last_message_id}")
    requests.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/deleteMessage?chat_id={chat_id}&message_id={bot_message_id}")


@app.route('/send_message', methods=['GET', 'POST'])
def send_message():
    if request.method == "POST":
        message = json.loads(request.get_json(force=True))
        for user in users:
            bot.send_message(chat_id=user.chat_id, text=message["message"])
            time.sleep(0.04)


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
    update_queue = Queue()     # Creating the Queue for the Dispatcher
    dp = Dispatcher(bot, update_queue)  # Creating the Dispatcher object
    launch_dispatcher()        # Preparing and launching the Dispatcher
    bot.deleteWebhook(drop_pending_updates=True)
    #bot.setWebhook(f"https://sbbotapp.herokuapp.com/{TELEGRAM_TOKEN}")  # Setting the WebHook for bot to receive updates
    bot.setWebhook(f"https://testflasksbbot.herokuapp.com/{TELEGRAM_TOKEN}")  # Setting the WebHook for bot to receive updates
    gsheets_manager = GSheetsManager()
    app.run(host="0.0.0.0", port=int(os.environ.get('PORT', 5000)), threaded=True)  # Launching the Flask app on appropriate IP and PORT
