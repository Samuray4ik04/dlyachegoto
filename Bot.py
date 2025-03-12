import telebot
import requests
import re
from telebot.types import InlineQueryResultArticle, InputTextMessageContent

# Настройки
API_TOKEN = '7147872197:AAFvz-_Q4sZ14npKR3_sgUQgYxYPUH81Hkk'
GEMINI_API_KEY = 'AIzaSyAj3Hn-iYmU3fi_vhMmar5iayJGPEK9sxg'
GEMINI_API_URL = f'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}'

# Инициализация бота
bot = telebot.TeleBot(API_TOKEN)

WELCOME_MESSAGE = "🤖 *Привет! Я AI-бот с интеграцией Gemini* 🚀"

def generate_gemini_response(prompt: str) -> str:
    """Синхронный запрос к Gemini API"""
    try:
        response = requests.post(
            GEMINI_API_URL,
            json={"contents": [{"parts": [{"text": prompt}]}]},
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        
        if response.status_code != 200:
            return "⚠️ Ошибка при обращении к API Gemini"
            
        data = response.json()
        return data['candidates'][0]['content']['parts'][0]['text']
        
    except Exception as e:
        return f"❌ Ошибка обработки ответа: {str(e)}"

def format_response(text: str) -> str:
    """Преобразует Markdown в HTML для Telegram"""
    text = re.sub(r'```(.*?)```', r'<pre>\1</pre>', text, flags=re.DOTALL)
    text = re.sub(r'`(.*?)`', r'<code>\1</code>', text)
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
    return text

# Обработчик обычных сообщений
@bot.message_handler(func=lambda msg: True)
def handle_message(message):
    bot.send_chat_action(message.chat.id, 'typing')
    response = generate_gemini_response(message.text)
    formatted_response = format_response(response)
    
    if len(formatted_response) > 4096:
        formatted_response = formatted_response[:4090] + "..."
        
    bot.send_message(
        message.chat.id,
        formatted_response,
        parse_mode='HTML',
        reply_to_message_id=message.message_id
    )

# Обработчик inline-запросов
@bot.inline_handler(lambda query: True)
def handle_inline(inline_query):
    try:
        # Генерация ответа
        response = generate_gemini_response(inline_query.query)
        formatted_response = format_response(response)
        
        # Создание результата
        result = InlineQueryResultArticle(
            id='1',
            title="Ответ от Gemini",
            description=response[:100] + "..." if len(response) > 100 else response,
            input_message_content=InputTextMessageContent(
                formatted_response,
                parse_mode='HTML'
            )
        )
        
        # Отправка ответа
        bot.answer_inline_query(
            inline_query.id,
            [result],
            cache_time=10
        )
        
    except Exception as e:
        error_result = InlineQueryResultArticle(
            id='error',
            title="Ошибка",
            description="Не удалось получить ответ",
            input_message_content=InputTextMessageContent("⚠️ Ошибка обработки запроса")
        )
        bot.answer_inline_query(inline_query.id, [error_result])

# Команда /start
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.send_message(
        message.chat.id,
        WELCOME_MESSAGE,
        parse_mode='MARKDOWN'
    )

if __name__ == '__main__':
    bot.polling(none_stop=True)
