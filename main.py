import os
import threading
import telebot
from Tools.scripts.objgraph import definitions
from pyexpat.errors import messages
import nltk
from nltk.corpus import wordnet as wn
import time
from main_token import TOKEN
import schedule

# создание wordnet
nltk.download("wordnet")

# Настройки бота
BOOKS_DIR = "books"
CHUNK_SIZE = 2000

# Проверяем, существует ли папка для книг
if not os.path.exists(BOOKS_DIR):
    # Если папка не существует, создаем её
    os.mkdir(BOOKS_DIR)
bot = telebot.TeleBot(TOKEN)

# Храним данные пользователей {user_id: {"current_book": файл,
#                       "position": позиция (кол-во символов)}}
user_data = {}
used = False

def is_start_reading(message):
    return message.text == "Начать чтение"

def is_restart_reading(message):
    return message.text == "Начать другую книгу"

def is_continue_reading(message):
    return message.text == "Продолжить чтение"

def is_define_word(message):
    return message.text == "Дать определение"

@bot.message_handler(commands=['start'])
def start(message):
    global used
    used = True
    #функция, которая обрабатывает команду /start
    user_data[message.from_user.id] = {"current_book": None, "position": 0}
    #создание или обновление данных пользователя

    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn1 = telebot.types.KeyboardButton("Начать чтение")
    btn2 = telebot.types.KeyboardButton("Начать другую книгу")
    markup.add(btn1, btn2)

    bot.send_message(
        message.chat.id,
        "Добро пожаловать в книжного бота! Я помогу вам читать книги по частям, а также находить определения неизвестных английских слов и подбирать к ним синонимы.\n\n"
        "Отправьте мне текстовый файл с книгой, чтобы начать чтение.",
        reply_markup=markup
    )

@bot.message_handler(content_types=['document'])
def handle_document(message):
    #Обработка загруженного файла
    if not message.document.file_name.endswith('.txt'):
        bot.reply_to(message, "Пожалуйста, отправьте файл в формате TXT.")
        return

    # Скачиваем файл
    file_info = bot.get_file(message.document.file_id)
    file_path = os.path.join(BOOKS_DIR, f"{message.from_user.id}_{message.document.file_name}")

    with open(file_path, 'wb') as f:
        f.write(bot.download_file(file_info.file_path))

    # Сохраняем информацию о книге
    user_data[message.from_user.id] = {
        "current_book": file_path,
        "position": 0
    }
    #После выбора книги бот предлагает начать чтение
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(telebot.types.KeyboardButton("Начать чтение"))

    bot.reply_to(
        message,
        f"Книга '{message.document.file_name}' успешно загружена! Нажмите 'Начать чтение'.",
        reply_markup=markup
    )

@bot.message_handler(func=is_start_reading)
def start_reading(message):
    #Начать чтение книги
    user_id = message.from_user.id
    if user_id not in user_data or not user_data[user_id]["current_book"]:
        bot.send_message(user_id, "У вас нет текущей книги. Пожалуйста, отправьте текстовый файл.")
        return

    send_next_chunk(user_id)

@bot.message_handler(func=is_restart_reading)
def restart_reading(message):
    #Начать читать другую книгу
    user_id = message.from_user.id
    user_data[user_id] = {"current_book": None, "position": 0}
    bot.send_message(user_id, "Готово! Теперь вы можете отправить новую книгу.")

@bot.message_handler(func=is_continue_reading)
def continue_reading(message):
    #Продолжить чтение книги
    send_next_chunk(message.from_user.id)

@bot.message_handler(func=is_define_word, content_types=["text"])
def define_word(message):
    #Дает определение
    msg = bot.send_message(message.from_user.id, "Пожалуйста, отправьте слово для его определения",
                           reply_markup=telebot.types.ReplyKeyboardMarkup(True))
    bot.register_next_step_handler(msg, give_definition)

def send_next_chunk(user_id):
    #Отправляет следующую часть книги
    if user_id not in user_data:
        return

    book_data = user_data[user_id]
    if not book_data["current_book"] or not os.path.exists(book_data["current_book"]):
        bot.send_message(user_id, "Книга не найдена. Пожалуйста, отправьте файл снова.")
        return

    with open(book_data["current_book"], 'r', encoding='utf-8') as f:
        f.seek(book_data["position"])
        text = f.read(CHUNK_SIZE)

        if not text:
            bot.send_message(user_id, "Вы дочитали книгу до конца!")
            user_data[user_id]["position"] = 0
            return

        user_data[user_id]["position"] = f.tell()
        bot.send_message(user_id, text)

        # Предлагаем продолжить
        markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
        btn1 = telebot.types.KeyboardButton("Продолжить чтение")
        btn2 = telebot.types.KeyboardButton("Начать другую книгу")
        btn3 = telebot.types.KeyboardButton("Дать определение")
        markup.add(btn1, btn2, btn3)
        bot.send_message(user_id, "Продолжить чтение или посмотреть определение слова?", reply_markup=markup)

def give_definition(message):
    word = message.text
    synsets = wn.synsets(word)
    if not synsets:
        bot.send_message(message.chat.id, "Извините, я не смогу дать определение этому слову")
        return
    definition = synsets[0].definition()
    synonyms_list = synsets[0].lemma_names()
    try:
        synonyms_list.remove(word)
    except ValueError:
        pass  # Слово не найдено в списке - ничего не делаем
    synonyms = ", ".join(synonyms_list).rstrip(",")
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn1 = telebot.types.KeyboardButton("Продолжить чтение")
    btn2 = telebot.types.KeyboardButton("Начать другую книгу")
    btn3 =telebot.types.KeyboardButton("Дать определение")
    markup.add(btn1, btn2, btn3)
    bot.send_message(message.chat.id, f"📖 {word}\n\nОпределение: {definition}\nСинонимы: {synonyms}", reply_markup=markup)

def reminder(message):
    global used
    if used is False:
        bot.send_message(message.chat.id, "Экологичное напоминание продолжить читать книгу:)")
    else:
        used = False

def run_threaded(func):
    new_thread = threading.Thread(target=func)
    new_thread.start()

schedule.every().day.at("20:00").do(run_threaded, reminder)

if __name__ == '__main__':
    print("Бот запущен...")
    bot.polling(none_stop=True)

while True:
    schedule.run_pending()
    time.sleep(1)