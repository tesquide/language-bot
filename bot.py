import logging
import json
import os
import random
from datetime import datetime, timedelta
from deep_translator import GoogleTranslator
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

# Налаштування логування
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

DATA_FILE = 'user_data.json'

# Завантаження даних
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

# Збереження даних
def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

user_data = load_data()

# Ініціалізація даних користувача
def init_user(user_id):
    user_id = str(user_id)
    if user_id not in user_data:
        user_data[user_id] = {
            'cards': [],
            'level': 'A2',  # рівень за замовчуванням
            'stats': {'total_reviews': 0, 'correct': 0}
        }
        save_data(user_data)

# Тексти для різних рівнів
LEVEL_TEXTS = {
    'A1': [
        "Hello! My name is Anna. I am a student. I live in Kyiv. I like reading books and listening to music. Every day I go to school. I have many friends. We play together after school. My favorite subject is English. I want to learn more languages.",
        "Today is Monday. The weather is nice. The sun is shining. I wake up at 7 o'clock. I eat breakfast with my family. Then I brush my teeth. I go to school at 8 o'clock. School is fun. I learn many new things every day."
    ],
    'A2': [
        "Last weekend, I visited my grandmother in the countryside. She lives in a small village surrounded by beautiful nature. We walked in the forest and picked mushrooms. In the evening, we cooked dinner together. She told me interesting stories about her childhood. I really enjoyed spending time with her and plan to visit again soon.",
        "I have been learning English for two years now. At first, it was difficult for me to understand grammar rules and pronounce new words correctly. However, I practiced every day by watching movies with subtitles and talking with my teacher. Now I can read simple books and have basic conversations. I am proud of my progress."
    ],
    'B1': [
        "Climate change is one of the most pressing issues facing our planet today. Scientists warn that rising temperatures are causing polar ice caps to melt, leading to rising sea levels and extreme weather events. Many countries are trying to reduce carbon emissions by investing in renewable energy sources like solar and wind power. However, more needs to be done if we want to protect our environment for future generations.",
        "Working remotely has become increasingly popular in recent years, especially after the pandemic. Many people appreciate the flexibility it offers, allowing them to balance work and personal life more effectively. However, remote work also has its challenges, such as feelings of isolation and difficulty separating work from home life. Companies are now looking for ways to support their remote employees better."
    ],
    'B2': [
        "The concept of artificial intelligence has evolved dramatically over the past few decades. What once seemed like science fiction is now an integral part of our daily lives. From virtual assistants on our phones to sophisticated algorithms that recommend products and content, AI has transformed how we interact with technology. However, this rapid advancement raises important ethical questions about privacy, job displacement, and the potential for bias in automated decision-making systems. As we continue to develop more powerful AI tools, it is crucial that we carefully consider their implications for society.",
        "Globalization has fundamentally altered the way businesses operate in the modern world. Companies can now source materials from one country, manufacture products in another, and sell them globally through digital platforms. While this has created unprecedented economic opportunities and allowed consumers access to a wider variety of goods, it has also led to concerns about labor exploitation, environmental degradation, and the erosion of local cultures. Finding a balance between economic growth and sustainability remains one of the greatest challenges of our time."
    ],
    'C1': [
        "The philosophical debate surrounding free will versus determinism has captivated thinkers for centuries. On one hand, our subjective experience suggests that we make genuine choices and bear moral responsibility for our actions. On the other hand, advances in neuroscience reveal that many of our decisions may be predetermined by factors beyond our conscious control, including genetics, upbringing, and environmental influences. This paradox has profound implications not only for how we understand human behavior but also for our legal and ethical frameworks. Some contemporary philosophers argue for compatibilism, suggesting that free will and determinism need not be mutually exclusive concepts.",
        "The emergence of social media has fundamentally transformed public discourse and interpersonal communication. These platforms have democratized access to information and given voice to marginalized communities, enabling social movements to organize with unprecedented speed and scale. However, they have also created echo chambers where people are primarily exposed to viewpoints that reinforce their existing beliefs, potentially exacerbating political polarization. Moreover, the business models underlying these platforms incentivize engagement over accuracy, sometimes promoting sensationalist or misleading content. Understanding and addressing these dynamics is essential for preserving the health of democratic societies in the digital age."
    ]
}

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    init_user(user_id)
    
    welcome_text = """
🎓 **Вітаю у Language Learning Bot!**

Що я вмію:
📚 Flashcards з інтервальним повторенням
🔄 Переклад будь-яких слів (Google Translate)
📖 Генерувати тексти для вашого рівня
✍️ Зберігати нові слова з текстів

**Команди:**
/add - Додати нове слово вручну
/review - Повторити збережені слова
/translate слово - Перекласти будь-яке слово
/text - Отримати текст для читання
/level - Вибрати свій рівень англійської
/stats - Переглянути статистику
/help - Детальна допомога
    """
    await update.message.reply_text(welcome_text)

# Команда /help
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
📖 **Детальна інструкція:**

**1️⃣ Встановіть свій рівень:**
/level - Виберіть рівень: A1, A2, B1, B2, C1

**2️⃣ Читайте тексти:**
/text - Отримайте текст для вашого рівня
Натисніть на невідомі слова для перекладу

**3️⃣ Додавайте слова:**
• /translate слово - перекласти і додати в картки
• /add - додати слово вручну
• Після перекладу натисніть "Додати в картки"

**4️⃣ Повторюйте:**
/review - Система покаже слова для повторення
Оціните, наскільки добре пам'ятаєте

**5️⃣ Відслідковуйте прогрес:**
/stats - Ваша статистика вивчення

💡 **Порада:** Пишіть боту будь-яке слово або фразу, і він автоматично перекладе!
    """
    await update.message.reply_text(help_text)

# Команда /level
async def level_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("A1 - Початковий", callback_data="level_A1")],
        [InlineKeyboardButton("A2 - Елементарний", callback_data="level_A2")],
        [InlineKeyboardButton("B1 - Середній", callback_data="level_B1")],
        [InlineKeyboardButton("B2 - Вище середнього", callback_data="level_B2")],
        [InlineKeyboardButton("C1 - Просунутий", callback_data="level_C1")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    user_id = str(update.effective_user.id)
    current_level = user_data[user_id].get('level', 'A2')
    
    await update.message.reply_text(
        f"Ваш поточний рівень: **{current_level}**\n\nВиберіть свій рівень англійської:",
        reply_markup=reply_markup
    )

# Команда /text
async def text_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    init_user(user_id)
    
    level = user_data[user_id].get('level', 'A2')
    texts = LEVEL_TEXTS[level]
    text = random.choice(texts)
    
    message = f"📖 **Текст для рівня {level}:**\n\n{text}\n\n"
    message += "💡 Натисніть /translate слово - щоб перекласти незнайоме слово\n"
    message += "Або просто напишіть слово боту!"
    
    await update.message.reply_text(message)

# Команда /add
async def add_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введіть слово українською:")
    context.user_data['waiting_for'] = 'ukrainian_word'

# Функція перекладу через Google Translate
def translate_word(text, from_lang='auto', to_lang='uk'):
    try:
        translator = GoogleTranslator(source=from_lang, target=to_lang)
        translation = translator.translate(text)
        return translation
    except Exception as e:
        logger.error(f"Translation error: {e}")
        return None

# Команда /translate
async def translate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Використання: /translate слово\nПриклад: /translate inspiration")
        return
    
    word = ' '.join(context.args)
    await process_translation(update, word, context)

# Обробка перекладу
async def process_translation(update, word, context, is_callback=False):
    user_id = str(update.effective_user.id if not is_callback else update.callback_query.from_user.id)
    init_user(user_id)
    
    # Визначаємо мову (якщо кирилиця - перекладаємо на англійську, інакше - на українську)
    is_cyrillic = any('\u0400' <= char <= '\u04FF' for char in word)
    
    if is_cyrillic:
        translation = translate_word(word, from_lang='uk', to_lang='en')
        from_word, to_word = word, translation
        from_flag, to_flag = "🇺🇦", "🇬🇧"
    else:
        translation = translate_word(word, from_lang='en', to_lang='uk')
        from_word, to_word = word, translation
        from_flag, to_flag = "🇬🇧", "🇺🇦"
    
    if translation:
        response = f"{from_flag} **{from_word}** → {to_flag} **{to_word}**"
        
        keyboard = [[InlineKeyboardButton("➕ Додати в картки", callback_data=f"add_to_cards:{from_word}:{to_word}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if is_callback:
            await update.callback_query.edit_message_text(response, reply_markup=reply_markup)
        else:
            await update.message.reply_text(response, reply_markup=reply_markup)
    else:
        error_msg = f"Не вдалося перекласти '{word}'. Спробуйте ще раз."
        if is_callback:
            await update.callback_query.edit_message_text(error_msg)
        else:
            await update.message.reply_text(error_msg)

# Обробка текстових повідомлень
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    init_user(user_id)
    
    text = update.message.text
    
    if context.user_data.get('waiting_for') == 'ukrainian_word':
        context.user_data['temp_ua'] = text
        context.user_data['waiting_for'] = 'english_word'
        await update.message.reply_text("Тепер введіть переклад англійською:")
    
    elif context.user_data.get('waiting_for') == 'english_word':
        ua_word = context.user_data.get('temp_ua')
        en_word = text
        
        card = {
            'ukrainian': ua_word,
            'english': en_word,
            'added_date': datetime.now().isoformat(),
            'next_review': datetime.now().isoformat(),
            'interval': 1
        }
        
        user_data[user_id]['cards'].append(card)
        save_data(user_data)
        
        context.user_data.clear()
        await update.message.reply_text(f"✅ Додано картку:\n🇺🇦 {ua_word} → 🇬🇧 {en_word}")
    
    elif context.user_data.get('reading_mode'):
        # Якщо в режимі читання - перекладаємо слово
        await process_translation(update, text, context)
    
    else:
        # Автоматичний переклад будь-якого тексту
        await process_translation(update, text, context)

# Команда /review
async def review(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    init_user(user_id)
    
    cards = user_data[user_id]['cards']
    
    if not cards:
        await update.message.reply_text("У вас ще немає карток. Додайте через /add або /translate")
        return
    
    now = datetime.now()
    due_cards = [i for i, card in enumerate(cards) if datetime.fromisoformat(card['next_review']) <= now]
    
    if not due_cards:
        next_review = min(cards, key=lambda x: x['next_review'])
        next_time = datetime.fromisoformat(next_review['next_review'])
        time_diff = next_time - now
        hours = int(time_diff.total_seconds() / 3600)
        await update.message.reply_text(f"🎉 Всі картки повторено!\n\nНаступне повторення через ~{hours} годин.")
        return
    
    context.user_data['reviewing'] = True
    context.user_data['current_card_index'] = due_cards[0]
    context.user_data['due_cards'] = due_cards
    
    card = cards[due_cards[0]]
    
    keyboard = [[InlineKeyboardButton("Показати відповідь", callback_data="show_answer")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"📚 Картка {1}/{len(due_cards)}\n\n🇺🇦 **{card['ukrainian']}**\n\nЯк це англійською?",
        reply_markup=reply_markup
    )

# Команда /stats
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    init_user(user_id)
    
    data = user_data[user_id]
    total_cards = len(data['cards'])
    total_reviews = data['stats']['total_reviews']
    correct = data['stats']['correct']
    level = data.get('level', 'A2')
    
    accuracy = (correct / total_reviews * 100) if total_reviews > 0 else 0
    
    stats_text = f"""
📊 **Ваша статистика:**

🎯 Рівень: {level}
📚 Всього карток: {total_cards}
✅ Повторень: {total_reviews}
🎯 Правильних відповідей: {correct}
📈 Точність: {accuracy:.1f}%
    """
    
    await update.message.reply_text(stats_text)

# Обробка кнопок
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = str(update.effective_user.id)
    init_user(user_id)
    
    data = query.data
    
    if data.startswith("level_"):
        level = data.split("_")[1]
        user_data[user_id]['level'] = level
        save_data(user_data)
        await query.edit_message_text(f"✅ Встановлено рівень: **{level}**\n\nТепер використовуйте /text для отримання текстів")
    
    elif data == "show_answer":
        card_index = context.user_data.get('current_card_index')
        card = user_data[user_id]['cards'][card_index]
        
        keyboard = [
            [InlineKeyboardButton("😊 Легко (7 днів)", callback_data="difficulty_easy")],
            [InlineKeyboardButton("🤔 Середньо (3 дні)", callback_data="difficulty_medium")],
            [InlineKeyboardButton("😓 Важко (1 день)", callback_data="difficulty_hard")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"🇺🇦 **{card['ukrainian']}**\n\n🇬🇧 **{card['english']}**\n\nНаскільки добре ви це запам'ятали?",
            reply_markup=reply_markup
        )
    
    elif data.startswith("difficulty_"):
        difficulty = data.split("_")[1]
        card_index = context.user_data.get('current_card_index')
        
        intervals = {'easy': 7, 'medium': 3, 'hard': 1}
        interval = intervals[difficulty]
        
        user_data[user_id]['cards'][card_index]['next_review'] = (datetime.now() + timedelta(days=interval)).isoformat()
        user_data[user_id]['cards'][card_index]['interval'] = interval
        
        user_data[user_id]['stats']['total_reviews'] += 1
        if difficulty in ['easy', 'medium']:
            user_data[user_id]['stats']['correct'] += 1
        
        save_data(user_data)
        
        due_cards = context.user_data['due_cards']
        current_pos = due_cards.index(card_index)
        
        if current_pos + 1 < len(due_cards):
            next_index = due_cards[current_pos + 1]
            context.user_data['current_card_index'] = next_index
            card = user_data[user_id]['cards'][next_index]
            
            keyboard = [[InlineKeyboardButton("Показати відповідь", callback_data="show_answer")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                f"📚 Картка {current_pos + 2}/{len(due_cards)}\n\n🇺🇦 **{card['ukrainian']}**\n\nЯк це англійською?",
                reply_markup=reply_markup
            )
        else:
            context.user_data.clear()
            await query.edit_message_text("🎉 Вітаю! Ви повторили всі картки!")
    
    elif data.startswith("add_to_cards:"):
        parts = data.split(":", 2)
        
        # Визначаємо, яке слово українське, а яке англійське
        word1 = parts[1]
        word2 = parts[2]
        
        is_word1_cyrillic = any('\u0400' <= char <= '\u04FF' for char in word1)
        
        if is_word1_cyrillic:
            ua_word, en_word = word1, word2
        else:
            ua_word, en_word = word2, word1
        
        card = {
            'ukrainian': ua_word,
            'english': en_word,
            'added_date': datetime.now().isoformat(),
            'next_review': datetime.now().isoformat(),
            'interval': 1
        }
        
        user_data[user_id]['cards'].append(card)
        save_data(user_data)
        
        await query.edit_message_text(f"✅ Додано в картки:\n🇺🇦 {ua_word} → 🇬🇧 {en_word}")

# Головна функція
def main():
    TOKEN = "ВАШ_ТОКЕН_ТУТ"
    
    application = Application.builder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("level", level_command))
    application.add_handler(CommandHandler("text", text_command))
    application.add_handler(CommandHandler("add", add_card))
    application.add_handler(CommandHandler("review", review))
    application.add_handler(CommandHandler("translate", translate_command))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("🤖 Бот запущено!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
