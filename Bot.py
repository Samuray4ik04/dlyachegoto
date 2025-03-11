import telebot
import requests

# Замените на ваш токен
TOKEN = "7147872197:AAFvz-_Q4sZ14npKR3_sgUQgYxYPUH81Hkk"
bot = telebot.TeleBot(TOKEN)

API_URL = "https://api.waifu.pics/nsfw/waifu"

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "Привет! Напиши /waifu, чтобы получить картинку аниме-девушки.")

@bot.message_handler(commands=['waifu'])
def send_waifu(message):
    try:
        response = requests.get(API_URL)
        if response.status_code == 200:
            image_url = response.json().get("url")
            bot.send_photo(message.chat.id, image_url, caption="Вот твоя вайфу! ❤️")
        else:
            bot.reply_to(message, "Не удалось получить картинку 😢 Попробуй позже.")
    except Exception as e:
        bot.reply_to(message, f"Произошла ошибка: {e}")

# Запуск бота
print("Бот запущен...")
bot.polling(none_stop=True)
