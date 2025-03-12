import telebot
import requests
import re
from telebot.types import InlineQueryResultArticle, InputTextMessageContent, ReplyKeyboardMarkup, KeyboardButton
from collections import defaultdict

# Настройки
API_TOKEN = '7147872197:AAFvz-_Q4sZ14npKR3_sgUQgYxYPUH81Hkk'
GEMINI_API_KEY = 'AIzaSyAj3Hn-iYmU3fi_vhMmar5iayJGPEK9sxg'

# Хранение состояний
chat_histories = defaultdict(list)  # История сообщений
chat_models = defaultdict(lambda: "gemini-2.0-flash")  # Текущая модель для каждого чата
MODELS = ["gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.0"]  # Доступные модели

# Инициализация бота
bot = telebot.TeleBot(API_TOKEN)

WELCOME_MESSAGE = "🤖 *Привет! Я AI-бот с интеграцией Gemini* 🚀\nИспользуй кнопки для управления"

def get_gemini_url(model: str) -> str:
    """Формирует URL для запроса к Gemini API"""
    return f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"

def generate_gemini_response(contents: list, model: str) -> str:
    """Синхронный запрос к Gemini API с указанием модели"""
    try:
        response = requests.post(
            get_gemini_url(model),
            json={"contents": contents},
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        
        if response.status_code != 200:
            return f"⚠️ Ошибка API ({response.status_code}): {response.text}"
            
        data = response.json()
        return data['candidates'][0]['content']['parts'][0]['text']
        
    except Exception as e:
        return f"❌ Ошибка: {str(e)}"

def format_response(text: str) -> str:
    """Преобразует Markdown в HTML для Telegram"""
    text = re.sub(r'```(.*?)```', r'<pre>\1</pre>', text, flags=re.DOTALL)
    text = re.sub(r'`(.*?)`', r'<code>\1</code>', text)
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
    return text

def get_main_keyboard():
    """Основная клавиатура с кнопками"""
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        KeyboardButton("🧹 Очистить историю"),
        KeyboardButton("🔄 Сменить модель")
    )
    return markup

def get_model_keyboard():
    """Клавиатура выбора модели"""
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    buttons = [KeyboardButton(model) for model in MODELS]
    markup.add(*buttons)
    markup.add(KeyboardButton("◀️ Назад"))
    return markup

# Обработчик обычных сообщений
@bot.message_handler(func=lambda msg: True)
def handle_message(message):
    chat_id = message.chat.id
    user_message = message.text
    current_model = chat_models[chat_id]
    
    # Обработка команд через текстовые кнопки
    if user_message == "청소ить историю":
        return clear_history(message)
    elif user_message == "🔄 Сменить модель":
        return switch_model(message)
    elif user_message in MODELS:
        return select_model(message)
    elif user_message == "◀️ Назад":
        bot.send_message(chat_id, "Главное меню", reply_markup=get_main_keyboard())
        return
    
    # Обновляем историю
    chat_histories[chat_id].append({"role": "user", "parts": [{"text": user_message}]})
    if len(chat_histories[chat_id]) > 10:
        chat_histories[chat_id] = chat_histories[chat_id][-10:]
    
    bot.send_chat_action(chat_id, 'typing')
    response = generate_gemini_response(chat_histories[chat_id], current_model)
    
    # Добавляем ответ бота в историю
    chat_histories[chat_id].append({"role": "model", "parts": [{"text": response}]})
    
    formatted_response = format_response(response)
    if len(formatted_response) > 4096:
        formatted_response = formatted_response[:4090] + "..."
    
    bot.send_message(
        chat_id,
        formatted_response,
        parse_mode='HTML',
        reply_markup=get_main_keyboard()
    )

# Обработчик inline-запросов
@bot.inline_handler(lambda query: True)
def handle_inline(inline_query):
    try:
        response = generate_gemini_response(
            [{"role": "user", "parts": [{"text": inline_query.query}]}],
            "gemini-2.0-flash"
        )
        
        formatted_response = format_response(response)
        result = InlineQueryResultArticle(
            id='1',
            title="Ответ от Gemini",
            description=response[:100] + "..." if len(response) > 100 else response,
            input_message_content=InputTextMessageContent(formatted_response, parse_mode='HTML')
        )
        
        bot.answer_inline_query(inline_query.id, [result], cache_time=10)
    except Exception as e:
        bot.answer_inline_query(
            inline_query.id,
            [InlineQueryResultArticle(
                id='error',
                title="Ошибка",
                input_message_content=InputTextMessageContent(f"⚠️ {str(e)}")
            )]
        )

# Очистка истории
def clear_history(message):
    chat_id = message.chat.id
    chat_histories[chat_id].clear()
    bot.send_message(
        chat_id,
        "✅ История чата очищена",
        reply_markup=get_main_keyboard()
    )

# Смена модели - шаг 1
def switch_model(message):
    chat_id = message.chat.id
    bot.send_message(
        chat_id,
        "Выберите версию модели:",
        reply_markup=get_model_keyboard()
    )

# Смена модели - шаг 2
def select_model(message):
    chat_id = message.chat.id
    new_model = message.text
    
    if new_model in MODELS:
        chat_models[chat_id] = new_model
        bot.send_message(
            chat_id,
            f"✅ Модель изменена на {new_model}",
            reply_markup=get_main_keyboard()
        )
    else:
        bot.send_message(
            chat_id,
            "❌ Неверная модель",
            reply_markup=get_model_keyboard()
        )

# Команда /start
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.send_message(
        message.chat.id,
        WELCOME_MESSAGE,
        parse_mode='MARKDOWN',
        reply_markup=get_main_keyboard()
    )

if __name__ == '__main__':
    bot.polling(none_stop=True)
