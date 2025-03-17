import telebot
from google import genai

# API ключи (НЕ размещайте их в публичном доступе)
TELEGRAM_BOT_API_KEY = "7147872197:AAFvz-_Q4sZ14npKR3_sgUQgYxYPUH81Hkk"
GENAI_API_KEY = "AIzaSyAj3Hn-iYmU3fi_vhMmar5iayJGPEK9sxg"

# Инициализируем бота и клиента GenAI
bot = telebot.TeleBot(TELEGRAM_BOT_API_KEY)
client = genai.Client(api_key=GENAI_API_KEY)

# Обработчик команд /start и /help
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    welcome_text = (
        "Привет! Я чат-бот с ИИ.\n"
        "Напиши мне любое сообщение, и я постараюсь сгенерировать для тебя ответ."
    )
    bot.send_message(message.chat.id, welcome_text)

# Основной обработчик текстовых сообщений
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_input = message.text
    try:
        # Отправляем запрос к GenAI для генерации ответа
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=user_input,
        )
        # Отправляем ответ пользователю
        bot.send_message(message.chat.id, response.text)
    except Exception as e:
        error_message = f"Произошла ошибка при обработке запроса: {str(e)}"
        bot.send_message(message.chat.id, error_message)

if __name__ == '__main__':
    print("Бот запущен...")
    bot.polling(none_stop=True)
