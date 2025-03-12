import telebot
import requests
import re
from telebot.types import InlineQueryResultArticle, InputTextMessageContent, InlineKeyboardMarkup, InlineKeyboardButton
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

WELCOME_MESSAGE = "🤖 *Привет! Я AI-бот с интеграцией Gemini* 🚀"

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
    """Создает основную клавиатуру с кнопками"""
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("🧹 Очистить историю", callback_data="clear_history"),
        InlineKeyboardButton("🔄 Сменить модель", callback_data="switch_model")
    )
    return keyboard

def get_model_keyboard():
    """Создает клавиатуру выбора модели"""
    keyboard = InlineKeyboardMarkup(row_width=1)
    buttons = [InlineKeyboardButton(model, callback_data=f"model_{model}") for model in MODELS]
    keyboard.add(*buttons)
    return keyboard

# Обработчик обычных сообщений
@bot.message_handler(func=lambda msg: True)
def handle_message(message):
    chat_id = message.chat.id
    user_message = message.text
    current_model = chat_models[chat_id]
    
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
            "gemini-2.0-flash"  # По умолчанию для инлайн-запросов
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

# Обработчик callback-кнопок
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    chat_id = call.message.chat.id
    
    # Очистка истории
    if call.data == "clear_history":
        chat_histories[chat_id].clear()
        bot.answer_callback_query(call.id, "История очищена")
        bot.send_message(chat_id, "✅ История чата очищена", reply_markup=get_main_keyboard())
    
    # Смена модели
    elif call.data == "switch_model":
        bot.answer_callback_query(call.id)
        bot.send_message(
            chat_id,
            "Выберите версию модели:",
            reply_markup=get_model_keyboard()
        )
    
    # Выбор конкретной модели
    elif call.data.startswith("model_"):
        new_model = call.data.split("_")[1]
        if new_model in MODELS:
            chat_models[chat_id] = new_model
            bot.answer_callback_query(call.id, f"Модель изменена на {new_model}")
            bot.send_message(
                chat_id,
                f"✅ Текущая модель: {new_model}",
                reply_markup=get_main_keyboard()
            )
        else:
            bot.answer_callback_query(call.id, "Ошибка выбора модели")

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
