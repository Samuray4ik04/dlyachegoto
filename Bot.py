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
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY', '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')  # API key from https://openrouter.ai/settings/keys
TOGETHER_API_KEY = os.getenv('TOGETHER_API_KEY', 'fd3395959cc541410ef887a2fcca346686bf3306225ab4cc14c21880390beedc')  # API key inside brackets

# API Endpoints
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
TOGETHER_API_URL = "https://api.together.xyz/v1/chat/completions"

# Constants
MAX_HISTORY_LENGTH = 10
REQUEST_TIMEOUT = 30  # Increased timeout for models that may take longer
MAX_MESSAGE_LENGTH = 4000

# Available models
MODELS = {
    # Gemini models
    "gemini-2.0-flash": "Gemini 2.0 Flash (быстрый)",
    "gemini-1.5-pro": "Gemini 1.5 Pro (продвинутый)",
    "gemini-1.0": "Gemini 1.0 (базовый)",
    # OpenRouter models
    "deepseek-r1": "DeepSeek R1 (OpenRouter)",
    # Together AI models
    "Qwen2.5-72B": "Qwen 2.5 72B (Together AI)"
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
- DeepSeek R1 (OpenRouter)
- Qwen 2.5 72B (Together AI)

Также можно использовать меня в inline-режиме в любом чате: @your_bot_name запрос
"""

ERROR_MESSAGE = "❌ Произошла ошибка при обработке запроса. Пожалуйста, попробуйте позже."
API_ERROR_MESSAGE = "⚠️ Ошибка API: {error}"
HISTORY_CLEARED_MESSAGE = "✅ История чата очищена. Начинаем новый разговор."
MODEL_CHANGED_MESSAGE = "✅ Модель изменена на {model_name}"
MODEL_SELECTION_MESSAGE = "Выберите версию модели AI:"
BACK_TO_MAIN_MESSAGE = "Вернулись в главное меню"

class AIBot:
    def __init__(self, token, gemini_key, openrouter_key, together_key):
        """Initialize the bot with API tokens and state storage"""
        self.bot = telebot.TeleBot(token)
        self.gemini_api_key = gemini_key
        self.openrouter_api_key = openrouter_key
        self.together_api_key = together_key
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
    
    def process_content(self, content):
        """Remove thinking tags from content"""
        return content.replace('<think>', '').replace('</think>', '')
    
    def convert_history_to_openrouter_format(self, history):
        """Convert chat history to OpenRouter API format"""
        messages = []
        
        for item in history:
            role = "user" if item["role"] == "user" else "assistant"
            content = item["parts"][0]["text"]
            messages.append({"role": role, "content": content})
        
        # Add a system message at the beginning if there isn't one
        if not messages or messages[0]["role"] != "system":
            messages.insert(0, {"role": "system", "content": "You are a helpful assistant"})
        
        return messages
    
    def generate_openrouter_response(self, history):
        """Send request to OpenRouter API with DeepSeek-R1 model"""
        try:
            # Convert history to OpenRouter format
            messages = self.convert_history_to_openrouter_format(history)
            
            # Prepare request body
            payload = {
                "model": "deepseek/deepseek-r1",
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 1000
            }
            
            # Prepare headers
            headers = {
                "Authorization": f"Bearer {self.openrouter_api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://telegram-bot.com",  # Required by OpenRouter
                "X-Title": "Telegram AI Bot"  # Optional but good practice for OpenRouter
            }
            
            # Send request
            response = requests.post(
                OPENROUTER_API_URL,
                json=payload,
                headers=headers,
                timeout=REQUEST_TIMEOUT
            )
            
            response.raise_for_status()
            data = response.json()
            
            # Extract and process response
            if 'choices' in data and len(data['choices']) > 0:
                content = data['choices'][0]['message']['content']
                return self.process_content(content)
            else:
                logger.warning(f"Unexpected OpenRouter API response: {data}")
                return "⚠️ Получен некорректный ответ от API OpenRouter"
                
        except requests.exceptions.HTTPError as e:
            return API_ERROR_MESSAGE.format(error=f"{e.response.status_code}: {e.response.text}")
        except requests.exceptions.Timeout:
            return "⚠️ Превышено время ожидания ответа от API OpenRouter"
        except Exception as e:
            logger.error(f"Error in generate_openrouter_response: {str(e)}", exc_info=True)
            return f"❌ Ошибка при обработке запроса OpenRouter: {str(e)}"
    
    def convert_history_to_together_format(self, history):
        """Convert chat history to Together AI API format"""
        messages = []
        
        for item in history:
            role = "user" if item["role"] == "user" else "assistant"
            content = item["parts"][0]["text"]
            messages.append({"role": role, "content": content})
        
        # Add a system message at the beginning if there isn't one
        if not messages or messages[0]["role"] != "system":
            messages.insert(0, {"role": "system", "content": "You are a helpful assistant"})
        
        return messages

    def generate_together_response(self, history):
        """Send request to Together AI API"""
        try:
            # Convert history to Together format
            messages = self.convert_history_to_together_format(history)
            
            # Prepare request body
            payload = {
                "model": "Qwen/Qwen2.5-72B-Instruct-Turbo",
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 1000
            }
            
            # Prepare headers
            headers = {
                "Authorization": f"Bearer {self.together_api_key}",
                "Content-Type": "application/json"
            }
            
            # Send request
            response = requests.post(
                TOGETHER_API_URL,
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
                logger.warning(f"Unexpected Together AI API response: {data}")
                return "⚠️ Получен некорректный ответ от API Together AI"
                
        except requests.exceptions.HTTPError as e:
            return API_ERROR_MESSAGE.format(error=f"{e.response.status_code}: {e.response.text}")
        except requests.exceptions.Timeout:
            return "⚠️ Превышено время ожидания ответа от API Together AI"
        except Exception as e:
            logger.error(f"Error in generate_together_response: {str(e)}", exc_info=True)
            return f"❌ Ошибка при обработке запроса Together AI: {str(e)}"
    
    def generate_ai_response(self, history, model):
        """Generate response using appropriate API based on selected model"""
        # Check which API to use based on model name
        if model.startswith("gemini"):
            return self.generate_gemini_response(history, model)
        elif model == "deepseek-r1":
            return self.generate_openrouter_response(history)
        elif model == "Qwen2.5-72B":
            return self.generate_together_response(history)
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
            
        if not OPENROUTER_API_KEY or OPENROUTER_API_KEY == '':
            logger.warning("OpenRouter API key is not set. DeepSeek R1 model will not work.")
            
        if not TOGETHER_API_KEY or TOGETHER_API_KEY == '':
            logger.warning("Together AI API key is not set. Together AI models will not work.")
        
        # Create and run the bot
        ai_bot = AIBot(API_TOKEN, GEMINI_API_KEY, OPENROUTER_API_KEY, TOGETHER_API_KEY)
        ai_bot.run()
    except Exception as e:
        logger.critical(f"Failed to start the bot: {str(e)}", exc_info=True)
