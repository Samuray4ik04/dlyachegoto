import requests
import json
import telebot

# Настройки
TOGETHER_API_KEY = "tgp_v1_SdMNWA-0rbbWt68KTdXRNFnBwbzd6UFnx7BanF5gQ4s"
API_URL = "https://api.together.xyz/v1/chat/completions"
TELEGRAM_BOT_TOKEN = "7147872197:AAFvz-_Q4sZ14npKR3_sgUQgYxYPUH81Hkk"  # Замените на ваш токен

# Инициализация бота
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

# Хранилище истории сообщений для каждого пользователя
user_histories = {}

def get_response_stream(messages):
    headers = {
        "Authorization": f"Bearer {TOGETHER_API_KEY}",
        "Content-Type": "application/json"
    }
    
    data = {
        "model": "Qwen/Qwen2.5-72B-Instruct-Turbo",
        "messages": messages,
        "stream": True
    }
    
    response = requests.post(API_URL, headers=headers, data=json.dumps(data), stream=True)
    
    if response.status_code != 200:
        print(f"API Error: {response.status_code}")
        yield "Ошибка подключения к API. Попробуйте позже."
        return

    for line in response.iter_lines():
        if line:
            decoded_line = line.decode('utf-8')
            if decoded_line.startswith('data: '):
                json_data = decoded_line[6:]
                if json_data.strip() == '[DONE]':
                    break
                try:
                    chunk = json.loads(json_data)
                    delta = chunk['choices'][0].get('delta', {})
                    content = delta.get('content', '')
                    yield content
                except json.JSONDecodeError:
                    continue

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "Добро пожаловать! Я ваш AI-ассистент. Напишите что-нибудь, чтобы начать.")

@bot.message_handler(commands=['reset'])
def reset_history(message):
    user_id = message.chat.id
    if user_id in user_histories:
        del user_histories[user_id]
    bot.reply_to(message, "История диалога очищена.")

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_id = message.chat.id
    user_input = message.text
    
    # Инициализация истории для нового пользователя
    if user_id not in user_histories:
        user_histories[user_id] = []
    
    # Добавляем сообщение пользователя в историю
    user_histories[user_id].append({"role": "user", "content": user_input})
    
    # Формируем ответ
    try:
        full_response = []
        for chunk in get_response_stream(user_histories[user_id]):
            full_response.append(chunk)
        
        # Объединяем все части ответа
        assistant_response = ''.join(full_response).strip()
        
        # Добавляем ответ ассистента в историю
        user_histories[user_id].append({"role": "assistant", "content": assistant_response})
        
        # Отправляем ответ пользователю
        bot.reply_to(message, assistant_response)
    
    except Exception as e:
        error_msg = f"Произошла ошибка: {str(e)}"
        bot.reply_to(message, error_msg)
        print(error_msg)

if __name__ == "__main__":
    print("Запуск бота...")
    bot.polling(none_stop=True)
