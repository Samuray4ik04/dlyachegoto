import os
import telebot
from google.generativeai import genai

# Настройка API ключей
TELEGRAM_API_KEY = "7147872197:AAFvz-_Q4sZ14npKR3_sgUQgYxYPUH81Hkk"
GOOGLE_API_KEY = "AIzaSyAj3Hn-iYmU3fi_vhMmar5iayJGPEK9sxg"

# Инициализация Telegram бота
bot = telebot.TeleBot(TELEGRAM_API_KEY)

# Инициализация Google Gemini API
genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel('gemini-2.0-flash')

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "Привет! Я бот с интеграцией Google Gemini AI. Задайте мне вопрос, и я постараюсь ответить.")

@bot.message_handler(commands=['help'])
def send_help(message):
    help_text = """
    Команды бота:
    /start - Начать взаимодействие с ботом
    /help - Показать эту справку
    
    Просто напишите свой вопрос, и я отвечу с помощью Google Gemini AI.
    """
    bot.reply_to(message, help_text)

@bot.message_handler(func=lambda message: True)
def respond_to_message(message):
    user_message = message.text
    try:
        # Отправка "печатает..." статуса
        bot.send_chat_action(message.chat.id, 'typing')
        
        # Получение ответа от Google Gemini
        response = model.generate_content(user_message)
        
        # Отправка ответа пользователю
        if response.text:
            # Если ответ слишком длинный, разбиваем его на части
            if len(response.text) > 4000:
                chunks = [response.text[i:i+4000] for i in range(0, len(response.text), 4000)]
                for chunk in chunks:
                    bot.send_message(message.chat.id, chunk)
            else:
                bot.send_message(message.chat.id, response.text)
        else:
            bot.reply_to(message, "Извините, не удалось сгенерировать ответ.")
    
    except Exception as e:
        bot.reply_to(message, f"Произошла ошибка: {str(e)}")

if __name__ == "__main__":
    print("Бот запущен...")
    bot.polling(none_stop=True)
