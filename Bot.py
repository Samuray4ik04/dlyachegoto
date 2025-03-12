import telebot
import requests
import re
import os
import logging
import json
from telebot.types import InlineQueryResultArticle, InputTextMessageContent, ReplyKeyboardMarkup, KeyboardButton
from collections import defaultdict
from functools import wraps

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Get sensitive data from environment variables (more secure than hardcoding)
API_TOKEN = os.getenv('TELEGRAM_API_TOKEN', '7147872197:AAFvz-_Q4sZ14npKR3_sgUQgYxYPUH81Hkk')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', 'AIzaSyAj3Hn-iYmU3fi_vhMmar5iayJGPEK9sxg')
SAMBANOVA_API_KEY = os.getenv('d9e5445b-869d-4c25-adc4-b9c0b380e176', 'd9e5445b-869d-4c25-adc4-b9c0b380e176')  # ТУТ ВСТАВЛЯЕТЕ СВОЙ API КЛЮЧИК

# API Endpoints
SAMBANOVA_API_URL = "https://api.sambanova.ai/v1/chat/completions"

# Constants
MAX_HISTORY_LENGTH = 10
REQUEST_TIMEOUT = 15
MAX_MESSAGE_LENGTH = 4000

# Available models
MODELS = {
    # Gemini models
    "gemini-2.0-flash": "Gemini 2.0 Flash (быстрый)",
    "gemini-1.5-pro": "Gemini 1.5 Pro (продвинутый)",
    "gemini-1.0": "Gemini 1.0 (базовый)",
    # SambaNova models
    "DeepSeek-R1": "DeepSeek-R1 (SambaNova)"
}

# Messages
WELCOME_MESSAGE = """
🤖 *Привет! Я AI-бот с интеграцией нескольких моделей* 🚀

Я могу помочь ответить на вопросы, написать текст или код.
Используйте кнопки ниже для управления ботом:
- 🧹 Очистить историю - сбросить контекст беседы
- 🔄 Сменить модель - выбрать другую модель AI

Доступны модели:
- Gemini (Google)
- DeepSeek-R1 (SambaNova)

Также можно использовать меня в inline-режиме в любом чате: @your_bot_name запрос
"""

ERROR_MESSAGE = "❌ Произошла ошибка при обработке запроса. Пожалуйста, попробуйте позже."
API_ERROR_MESSAGE = "⚠️ Ошибка API: {error}"
HISTORY_CLEARED_MESSAGE = "✅ История чата очищена. Начинаем новый разговор."
MODEL_CHANGED_MESSAGE = "✅ Модель изменена на {model_name}"
MODEL_SELECTION_MESSAGE = "Выберите версию модели AI:"
BACK_TO_MAIN_MESSAGE = "Вернулись в главное меню"

class AIBot:
    def __init__(self, token, gemini_key, sambanova_key):
        """Initialize the bot with API tokens and state storage"""
        self.bot = telebot.TeleBot(token)
        self.gemini_api_key = gemini_key
        self.sambanova_api_key = sambanova_key
        self.chat_histories = defaultdict(list)
        self.chat_models = defaultdict(lambda: "gemini-2.0-flash")
        self.setup_handlers()
    
    def setup_handlers(self):
        """Set up all message handlers"""
        # Command handlers
        self.bot.message_handler(commands=['start', 'help'])(self.send_welcome)
        
        # Button handlers
        self.bot.message_handler(func=lambda msg: msg.text == "🧹 Очистить историю")(self.clear_history)
        self.bot.message_handler(func=lambda msg: msg.text == "🔄 Сменить модель")(self.switch_model)
        self.bot.message_handler(func=lambda msg: msg.text in MODELS)(self.select_model)
        self.bot.message_handler(func=lambda msg: msg.text == "◀️ Назад")(self.back_to_main)
        
        # Inline query handler
        self.bot.inline_handler(lambda query: True)(self.handle_inline)
        
        # Default message handler (catches all other messages)
        self.bot.message_handler(func=lambda msg: True)(self.handle_message)
    
    def error_handler(func):
        """Decorator for error handling in methods"""
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            try:
                return func(self, *args, **kwargs)
            except Exception as e:
                logger.error(f"Error in {func.__name__}: {str(e)}", exc_info=True)
                # If we have a message object, send error message
                if args and hasattr(args[0], 'chat'):
                    self.bot.send_message(
                        args[0].chat.id,
                        ERROR_MESSAGE,
                        reply_markup=self.get_main_keyboard()
                    )
        return wrapper
    
    def get_gemini_url(self, model):
        """Forms URL for Gemini API request"""
        return f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.gemini_api_key}"
    
    def generate_gemini_response(self, contents, model):
        """Send synchronous request to Gemini API with specified model"""
        try:
            response = requests.post(
                self.get_gemini_url(model),
                json={"contents": contents, "generationConfig": {"temperature": 0.7}},
                headers={'Content-Type': 'application/json'},
                timeout=REQUEST_TIMEOUT
            )
            
            response.raise_for_status()
            data = response.json()
            
            # Check if response has the expected structure
            if 'candidates' not in data or not data['candidates']:
                logger.warning(f"Unexpected API response: {data}")
                return "⚠️ Получен некорректный ответ от API"
                
            # Handle content filtering cases
            if 'content' not in data['candidates'][0]:
                if 'finishReason' in data['candidates'][0] and data['candidates'][0]['finishReason'] == 'SAFETY':
                    return "⚠️ Запрос был отклонен системой безопасности Gemini"
                return "⚠️ Не удалось получить ответ от модели"
                
            return data['candidates'][0]['content']['parts'][0]['text']
            
        except requests.exceptions.HTTPError as e:
            return API_ERROR_MESSAGE.format(error=f"{e.response.status_code}: {e.response.text}")
        except requests.exceptions.Timeout:
            return "⚠️ Превышено время ожидания ответа от API"
        except Exception as e:
            logger.error(f"Error in generate_gemini_response: {str(e)}", exc_info=True)
            return f"❌ Ошибка при обработке запроса: {str(e)}"
    
    def convert_history_to_sambanova_format(self, history):
        """Convert chat history to SambaNova API format"""
        # Start with system message
        messages = [{"role": "system", "content": "You are a helpful assistant"}]
        
        # Add conversation history
        for item in history:
            role = "user" if item["role"] == "user" else "assistant"
            content = item["parts"][0]["text"]
            messages.append({"role": role, "content": content})
        
        return messages
    
    def generate_sambanova_response(self, history):
        """Send request to SambaNova API with DeepSeek-R1 model"""
        try:
            # Convert history to SambaNova format
            messages = self.convert_history_to_sambanova_format(history)
            
            # Prepare request body
            payload = {
                "model": "DeepSeek-R1",
                "messages": messages,
                "temperature": 0.1,
                "top_p": 0.1
            }
            
            # Prepare headers
            headers = {
                "Authorization": f"Bearer {self.sambanova_api_key}",
                "Content-Type": "application/json"
            }
            
            # Send request
            response = requests.post(
                SAMBANOVA_API_URL,
                json=payload,
                headers=headers,
                timeout=REQUEST_TIMEOUT
            )
            
            response.raise_for_status()
            data = response.json()
            
            # Extract response
            if 'choices' in data and len(data['choices']) > 0:
                return data['choices'][0]['message']['content']
            else:
                logger.warning(f"Unexpected SambaNova API response: {data}")
                return "⚠️ Получен некорректный ответ от API SambaNova"
                
        except requests.exceptions.HTTPError as e:
            return API_ERROR_MESSAGE.format(error=f"{e.response.status_code}: {e.response.text}")
        except requests.exceptions.Timeout:
            return "⚠️ Превышено время ожидания ответа от API SambaNova"
        except Exception as e:
            logger.error(f"Error in generate_sambanova_response: {str(e)}", exc_info=True)
            return f"❌ Ошибка при обработке запроса SambaNova: {str(e)}"
    
    def generate_ai_response(self, history, model):
        """Generate response using appropriate API based on selected model"""
        # Check which API to use based on model name
        if model.startswith("gemini"):
            return self.generate_gemini_response(history, model)
        elif model == "DeepSeek-R1":
            return self.generate_sambanova_response(history)
        else:
            return f"⚠️ Неподдерживаемая модель: {model}"
    
    def format_response(self, text):
        """Convert markdown to HTML for Telegram messages"""
        # Replace code blocks
        text = re.sub(r'```(\w*)\n(.*?)```', r'<pre><code>\2</code></pre>', text, flags=re.DOTALL)
        # Replace inline code
        text = re.sub(r'`(.*?)`', r'<code>\1</code>', text)
        # Replace bold text
        text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
        # Replace italic text
        text = re.sub(r'\*(.*?)\*', r'<i>\1</i>', text)
        return text
    
    def get_main_keyboard(self):
        """Main keyboard with control buttons"""
        markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        markup.add(
            KeyboardButton("🧹 Очистить историю"),
            KeyboardButton("🔄 Сменить модель")
        )
        return markup
    
    def get_model_keyboard(self):
        """Keyboard for model selection"""
        markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
        buttons = [KeyboardButton(model) for model in MODELS]
        markup.add(*buttons)
        markup.add(KeyboardButton("◀️ Назад"))
        return markup
    
    @error_handler
    def send_welcome(self, message):
        """Handle /start command"""
        self.bot.send_message(
            message.chat.id,
            WELCOME_MESSAGE,
            parse_mode='MARKDOWN',
            reply_markup=self.get_main_keyboard()
        )
    
    @error_handler
    def clear_history(self, message):
        """Clear chat history"""
        chat_id = message.chat.id
        self.chat_histories[chat_id].clear()
        self.bot.send_message(
            chat_id,
            HISTORY_CLEARED_MESSAGE,
            reply_markup=self.get_main_keyboard()
        )
    
    @error_handler
    def switch_model(self, message):
        """Show model selection keyboard"""
        chat_id = message.chat.id
        model_options = "\n".join([f"• {key}: {desc}" for key, desc in MODELS.items()])
        self.bot.send_message(
            chat_id,
            f"{MODEL_SELECTION_MESSAGE}\n\n{model_options}",
            reply_markup=self.get_model_keyboard()
        )
    
    @error_handler
    def select_model(self, message):
        """Handle model selection"""
        chat_id = message.chat.id
        new_model = message.text
        
        if new_model in MODELS:
            self.chat_models[chat_id] = new_model
            model_name = MODELS[new_model]
            self.bot.send_message(
                chat_id,
                MODEL_CHANGED_MESSAGE.format(model_name=model_name),
                reply_markup=self.get_main_keyboard()
            )
        else:
            self.bot.send_message(
                chat_id,
                "❌ Неверная модель",
                reply_markup=self.get_model_keyboard()
            )
    
    @error_handler
    def back_to_main(self, message):
        """Return to main menu"""
        self.bot.send_message(
            message.chat.id,
            BACK_TO_MAIN_MESSAGE,
            reply_markup=self.get_main_keyboard()
        )
    
    @error_handler
    def handle_message(self, message):
        """Process user messages and get AI responses"""
        chat_id = message.chat.id
        user_message = message.text
        current_model = self.chat_models[chat_id]
        
        # Process message based on user's input
        if user_message.startswith('/'):
            # Ignore unrecognized commands
            return
        
        # Update chat history
        self.chat_histories[chat_id].append({"role": "user", "parts": [{"text": user_message}]})
        
        # Limit history length
        if len(self.chat_histories[chat_id]) > MAX_HISTORY_LENGTH:
            self.chat_histories[chat_id] = self.chat_histories[chat_id][-MAX_HISTORY_LENGTH:]
        
        # Show typing indicator
        self.bot.send_chat_action(chat_id, 'typing')
        
        # Get response from selected AI model
        response = self.generate_ai_response(self.chat_histories[chat_id], current_model)
        
        # Add bot's response to history
        self.chat_histories[chat_id].append({"role": "model", "parts": [{"text": response}]})
        
        # Format response for Telegram
        formatted_response = self.format_response(response)
        
        # Split message if it's too long
        if len(formatted_response) > MAX_MESSAGE_LENGTH:
            chunks = [formatted_response[i:i+MAX_MESSAGE_LENGTH] 
                     for i in range(0, len(formatted_response), MAX_MESSAGE_LENGTH)]
            
            for i, chunk in enumerate(chunks):
                # Only add keyboard to the last chunk
                reply_markup = self.get_main_keyboard() if i == len(chunks) - 1 else None
                
                self.bot.send_message(
                    chat_id,
                    chunk if i < len(chunks) - 1 else chunk + "\n\n[Сообщение было разделено из-за ограничений Telegram]",
                    parse_mode='HTML',
                    reply_markup=reply_markup
                )
        else:
            self.bot.send_message(
                chat_id,
                formatted_response,
                parse_mode='HTML',
                reply_markup=self.get_main_keyboard()
            )
    
    @error_handler
    def handle_inline(self, inline_query):
        """Process inline queries"""
        if not inline_query.query:
            return
            
        try:
            # For inline queries, always use the fastest model
            default_model = "gemini-2.0-flash"
            
            # Create simple history for inline query
            history = [{"role": "user", "parts": [{"text": inline_query.query}]}]
            
            # Get response
            response = self.generate_ai_response(history, default_model)
            
            formatted_response = self.format_response(response)
            
            # Truncate response for description
            short_description = response[:100] + "..." if len(response) > 100 else response
            short_description = re.sub(r'\s+', ' ', short_description)  # Remove excess whitespace
            
            result = InlineQueryResultArticle(
                id='1',
                title="Ответ от AI",
                description=short_description,
                input_message_content=InputTextMessageContent(
                    formatted_response, 
                    parse_mode='HTML'
                )
            )
            
            self.bot.answer_inline_query(inline_query.id, [result], cache_time=60)
        except Exception as e:
            logger.error(f"Error in inline query: {str(e)}", exc_info=True)
            self.bot.answer_inline_query(
                inline_query.id,
                [InlineQueryResultArticle(
                    id='error',
                    title="Ошибка",
                    description="Не удалось обработать запрос",
                    input_message_content=InputTextMessageContent(ERROR_MESSAGE)
                )]
            )
    
    def run(self):
        """Start the bot"""
        logger.info("Starting the bot...")
        self.bot.infinity_polling(timeout=60, long_polling_timeout=60)


if __name__ == '__main__':
    try:
        # Validate API tokens
        if not API_TOKEN or API_TOKEN == '7147872197:AAFvz-_Q4sZ14npKR3_sgUQgYxYPUH81Hkk':
            logger.warning("Using default Telegram API token. Consider setting up environment variables.")
        
        if not GEMINI_API_KEY or GEMINI_API_KEY == 'AIzaSyAj3Hn-iYmU3fi_vhMmar5iayJGPEK9sxg':
            logger.warning("Using default Gemini API key. Consider setting up environment variables.")
            
        if not SAMBANOVA_API_KEY or SAMBANOVA_API_KEY == 'вот тута':
            logger.warning("Using default SambaNova API key. Consider setting up environment variables.")
        
        # Create and run the bot
        ai_bot = AIBot(API_TOKEN, GEMINI_API_KEY, SAMBANOVA_API_KEY)
        ai_bot.run()
    except Exception as e:
        logger.critical(f"Failed to start the bot: {str(e)}", exc_info=True)
