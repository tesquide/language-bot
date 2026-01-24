import logging
import json
import os
import random
import asyncio
from datetime import datetime, timedelta, time as dt_time
from deep_translator import GoogleTranslator
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

DATA_FILE = 'user_data.json'

# Завантаження даних
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

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
            'level': 'B1',
            'stats': {'total_reviews': 0, 'correct': 0, 'streak': 0},
            'languages': ['en'],  # мови для вивчення
            'read_texts': [],  # ID прочитаних текстів
            'reminders': {'enabled': False, 'time': '20:00'},
            'game_stats': {'correct': 0, 'total': 0}
        }
        save_data(user_data)

# Головне меню (кнопки знизу)
def get_main_menu():
    keyboard = [
        [KeyboardButton("📖 Текст"), KeyboardButton("🔄 Перекласти")],
        [KeyboardButton("📚 Повторити"), KeyboardButton("➕ Додати слово")],
        [KeyboardButton("🎮 Гра"), KeyboardButton("📊 Статистика")],
        [KeyboardButton("⚙️ Налаштування"), KeyboardButton("❓ Допомога")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# Генерація тексту через Claude API
async def generate_text_with_ai(level, topic=None):
    """Генерує унікальний текст для вказаного рівня через Claude API"""
    
    level_descriptions = {
        'A1': 'beginner level (very simple vocabulary, present tense, short sentences)',
        'A2': 'elementary level (simple past and future, basic vocabulary, everyday topics)',
        'B1': 'intermediate level (variety of tenses, more complex sentences, opinions)',
        'B2': 'upper-intermediate level (complex grammar, idiomatic expressions, abstract topics)',
        'C1': 'advanced level (sophisticated vocabulary, nuanced arguments, academic style)'
    }
    
    topics_pool = [
        'technology and innovation', 'environmental issues', 'travel experiences',
        'food and culture', 'education and learning', 'health and fitness',
        'relationships and friendship', 'work and career', 'hobbies and interests',
        'science discoveries', 'art and creativity', 'social media impact',
        'city vs countryside life', 'historical events', 'future predictions'
    ]
    
    if not topic:
        topic = random.choice(topics_pool)
    
    prompt = f"""Generate a unique, interesting text in English for {level_descriptions[level]}.
Topic: {topic}
Length: 150-200 words for levels A1-A2, 200-300 words for B1-B2, 300-400 words for C1.
Make it engaging and educational. Include cultural context where relevant.
Write ONLY the text, no title, no explanations."""

    try:
        response = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={"Content-Type": "application/json"},
                json={
                    "model": "claude-sonnet-4-20250514",
                    "max_tokens": 1000,
                    "messages": [{"role": "user", "content": prompt}]
                },
                timeout=30
            )
        )
        
        if response.status_code == 200:
            data = response.json()
            text = data['content'][0]['text']
            return text, topic
    except Exception as e:
        logger.error(f"AI generation error: {e}")
    
    # Fallback до заздалегідь написаних текстів
    fallback_texts = {
        'A1': "Hello! My name is Anna. I am a student. I live in Kyiv. I like reading books and listening to music. Every day I go to school. I have many friends. We play together after school. My favorite subject is English. I want to learn more languages. On weekends, I visit my grandmother. She lives near a beautiful park. We walk there and talk about many things. I am happy to learn new words every day.",
        'A2': "Last weekend, I visited my grandmother in the countryside. She lives in a small village surrounded by beautiful nature. We walked in the forest and picked mushrooms. In the evening, we cooked dinner together. She told me interesting stories about her childhood. The village was very peaceful and quiet. I really enjoyed spending time with her and plan to visit again soon. It was nice to take a break from the busy city life.",
        'B1': "Climate change is one of the most pressing issues facing our planet today. Scientists warn that rising temperatures are causing polar ice caps to melt, leading to rising sea levels and extreme weather events. Many countries are trying to reduce carbon emissions by investing in renewable energy sources like solar and wind power. However, more needs to be done if we want to protect our environment for future generations. Individual actions, such as reducing plastic use and choosing sustainable products, also make a difference.",
        'B2': "The concept of artificial intelligence has evolved dramatically over the past few decades. What once seemed like science fiction is now an integral part of our daily lives. From virtual assistants on our phones to sophisticated algorithms that recommend products and content, AI has transformed how we interact with technology. However, this rapid advancement raises important ethical questions about privacy, job displacement, and the potential for bias in automated decision-making systems. As we continue to develop more powerful AI tools, it is crucial that we carefully consider their implications for society.",
        'C1': "The philosophical debate surrounding free will versus determinism has captivated thinkers for centuries. On one hand, our subjective experience suggests that we make genuine choices and bear moral responsibility for our actions. On the other hand, advances in neuroscience reveal that many of our decisions may be predetermined by factors beyond our conscious control, including genetics, upbringing, and environmental influences. This paradox has profound implications not only for how we understand human behavior but also for our legal and ethical frameworks. Some contemporary philosophers argue for compatibilism, suggesting that free will and determinism need not be mutually exclusive concepts."
    }
    
    return fallback_texts.get(level, fallback_texts['B1']), topic

# Отримання прикладів через AI
async def get_examples_with_ai(word, target_lang='uk'):
    """Генерує приклади використання слова через Claude API"""
    
    prompt = f"""For the English word "{word}", provide 3 example sentences showing different uses.
Make examples practical and memorable. Format: just the sentences, one per line, no numbering."""

    try:
        import requests
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"Content-Type": "application/json"},
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 500,
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=15
        )
        
        if response.status_code == 200:
            data = response.json()
            examples_text = data['content'][0]['text']
            examples = [ex.strip() for ex in examples_text.split('\n') if ex.strip()]
            return examples[:3]
    except Exception as e:
        logger.error(f"AI examples error: {e}")
    
    # Fallback
    return [
        f"I use {word} every day.",
        f"Learning about {word} is interesting.",
        f"Can you explain {word} to me?"
    ]

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    init_user(user_id)
    
    welcome_text = """
🎓 **Вітаю у Language Learning Bot!**

Я допоможу вам вивчати мови інтерактивно:

📖 **Читайте тексти** - AI генерує унікальні тексти
🔄 **Перекладайте** - будь-які слова та фрази
📚 **Повторюйте** - інтервальні повторення
🎮 **Грайте** - вгадуйте слова
⏰ **Нагадування** - не забувайте практикувати!

Використовуйте меню знизу для навігації 👇
    """
    await update.message.reply_text(welcome_text, reply_markup=get_main_menu())

# Команда /help
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
📖 **Як користуватись:**

**📖 Текст** - Отримати новий текст для читання
**🔄 Перекласти** - Ввести слово для перекладу
**📚 Повторити** - Повторити збережені слова
**➕ Додати слово** - Додати слово вручну
**🎮 Гра** - Грати у вгадування слів
**📊 Статистика** - Переглянути прогрес
**⚙️ Налаштування** - Налаштувати рівень, мови, нагадування

💡 Або просто напишіть будь-яке слово для перекладу!
    """
    await update.message.reply_text(help_text, reply_markup=get_main_menu())

# Налаштування
async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🎯 Рівень", callback_data="settings_level")],
        [InlineKeyboardButton("🌍 Мови", callback_data="settings_languages")],
        [InlineKeyboardButton("⏰ Нагадування", callback_data="settings_reminders")],
        [InlineKeyboardButton("🔙 Назад", callback_data="settings_back")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text("⚙️ **Налаштування:**", reply_markup=reply_markup)

# Команда для отримання тексту
async def text_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    init_user(user_id)
    
    await update.message.reply_text("⏳ Генерую унікальний текст для вас...")
    
    level = user_data[user_id].get('level', 'B1')
    
    # Генеруємо текст через AI
    text, topic = await generate_text_with_ai(level)
    
    # Зберігаємо ID тексту щоб не повторювати
    text_id = hash(text)
    if 'read_texts' not in user_data[user_id]:
        user_data[user_id]['read_texts'] = []
    user_data[user_id]['read_texts'].append(text_id)
    save_data(user_data)
    
    message = f"📖 **Текст для рівня {level}**\n"
    message += f"📌 Тема: {topic}\n\n"
    message += f"{text}\n\n"
    message += "💡 Натисніть незнайоме слово або напишіть його боту для перекладу!"
    
    await update.message.reply_text(message, reply_markup=get_main_menu())

# Переклад
def translate_word(text, from_lang='auto', to_lang='uk'):
    try:
        translator = GoogleTranslator(source=from_lang, target=to_lang)
        translation = translator.translate(text)
        return translation
    except Exception as e:
        logger.error(f"Translation error: {e}")
        return None

async def translate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введіть слово або фразу для перекладу:", reply_markup=get_main_menu())
    context.user_data['waiting_for_translation'] = True

async def process_translation(update, word, context, message=None):
    user_id = str(update.effective_user.id if not message else update.message.from_user.id)
    init_user(user_id)
    
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
        response = f"{from_flag} **{from_word}**\n{to_flag} **{to_word}**\n\n"
        
        # Додаємо приклади через AI
        if not is_cyrillic:  # тільки для англійських слів
            examples = await get_examples_with_ai(from_word)
            response += "📝 **Приклади:**\n"
            for ex in examples:
                response += f"• {ex}\n"
        
        keyboard = [[InlineKeyboardButton("➕ Додати в картки", callback_data=f"add_to_cards:{from_word}:{to_word}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if message:
            await message.reply_text(response, reply_markup=reply_markup)
        else:
            await update.callback_query.message.reply_text(response, reply_markup=reply_markup)
    else:
        error_msg = f"Не вдалося перекласти '{word}'"
        if message:
            await message.reply_text(error_msg, reply_markup=get_main_menu())

# Гра
async def game_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    init_user(user_id)
    
    cards = user_data[user_id]['cards']
    
    if len(cards) < 4:
        await update.message.reply_text(
            "Вам потрібно мінімум 4 картки для гри!\nДодайте більше слів через /translate",
            reply_markup=get_main_menu()
        )
        return
    
    # Вибираємо випадкове слово
    correct_card = random.choice(cards)
    wrong_cards = random.sample([c for c in cards if c != correct_card], min(3, len(cards)-1))
    
    options = [correct_card] + wrong_cards
    random.shuffle(options)
    
    context.user_data['game_correct'] = correct_card['english']
    context.user_data['game_active'] = True
    
    keyboard = [[InlineKeyboardButton(opt['english'], callback_data=f"game_answer:{opt['english']}")] for opt in options]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"🎮 **Гра: Вгадай переклад**\n\n🇺🇦 {correct_card['ukrainian']}\n\nЯк це англійською?",
        reply_markup=reply_markup
    )

# Додавання слова
async def add_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введіть слово українською:", reply_markup=get_main_menu())
    context.user_data['waiting_for'] = 'ukrainian_word'

# Повторення
async def review(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    init_user(user_id)
    
    cards = user_data[user_id]['cards']
    
    if not cards:
        await update.message.reply_text(
            "У вас ще немає карток. Додайте через 🔄 Перекласти",
            reply_markup=get_main_menu()
        )
        return
    
    now = datetime.now()
    due_cards = [i for i, card in enumerate(cards) if datetime.fromisoformat(card['next_review']) <= now]
    
    if not due_cards:
        next_review = min(cards, key=lambda x: x['next_review'])
        next_time = datetime.fromisoformat(next_review['next_review'])
        time_diff = next_time - now
        hours = int(time_diff.total_seconds() / 3600)
        await update.message.reply_text(
            f"🎉 Всі картки повторено!\n\nНаступне повторення через ~{hours} год.",
            reply_markup=get_main_menu()
        )
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

# Статистика
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    init_user(user_id)
    
    data = user_data[user_id]
    total_cards = len(data['cards'])
    total_reviews = data['stats']['total_reviews']
    correct = data['stats']['correct']
    level = data.get('level', 'B1')
    streak = data['stats'].get('streak', 0)
    
    game_total = data.get('game_stats', {}).get('total', 0)
    game_correct = data.get('game_stats', {}).get('correct', 0)
    
    accuracy = (correct / total_reviews * 100) if total_reviews > 0 else 0
    game_accuracy = (game_correct / game_total * 100) if game_total > 0 else 0
    
    stats_text = f"""
📊 **Ваша статистика:**

🎯 Рівень: {level}
📚 Всього карток: {total_cards}
🔥 Днів підряд: {streak}

**Повторення:**
✅ Всього: {total_reviews}
🎯 Правильних: {correct}
📈 Точність: {accuracy:.1f}%

**Ігри:**
🎮 Зіграно: {game_total}
✅ Правильно: {game_correct}
📈 Точність: {game_accuracy:.1f}%
    """
    
    await update.message.reply_text(stats_text, reply_markup=get_main_menu())

# Обробка текстових повідомлень
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    init_user(user_id)
    
    text = update.message.text
    
    # Меню кнопки
    if text == "📖 Текст":
        await text_command(update, context)
        return
    elif text == "🔄 Перекласти":
        await translate_command(update, context)
        return
    elif text == "📚 Повторити":
        await review(update, context)
        return
    elif text == "➕ Додати слово":
        await add_card(update, context)
        return
    elif text == "🎮 Гра":
        await game_command(update, context)
        return
    elif text == "📊 Статистика":
        await stats(update, context)
        return
    elif text == "⚙️ Налаштування":
        await settings_command(update, context)
        return
    elif text == "❓ Допомога":
        await help_command(update, context)
        return
    
    # Додавання слова
    if context.user_data.get('waiting_for') == 'ukrainian_word':
        context.user_data['temp_ua'] = text
        context.user_data['waiting_for'] = 'english_word'
        await update.message.reply_text("Тепер введіть переклад англійською:")
        return
    
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
        await update.message.reply_text(
            f"✅ Додано:\n🇺🇦 {ua_word} → 🇬🇧 {en_word}",
            reply_markup=get_main_menu()
        )
        return
    
    # Переклад слова
    if context.user_data.get('waiting_for_translation'):
        context.user_data['waiting_for_translation'] = False
        await process_translation(update, text, context, message=update.message)
        return
    
    # Автоматичний переклад
    await process_translation(update, text, context, message=update.message)

# Обробка кнопок
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = str(update.effective_user.id)
    init_user(user_id)
    
    data = query.data
    
    # Налаштування
    if data == "settings_level":
        keyboard = [
            [InlineKeyboardButton("A1 - Початковий", callback_data="level_A1")],
            [InlineKeyboardButton("A2 - Елементарний", callback_data="level_A2")],
            [InlineKeyboardButton("B1 - Середній", callback_data="level_B1")],
            [InlineKeyboardButton("B2 - Вище середнього", callback_data="level_B2")],
            [InlineKeyboardButton("C1 - Просунутий", callback_data="level_C1")],
            [InlineKeyboardButton("🔙 Назад", callback_data="settings_back")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("Виберіть рівень:", reply_markup=reply_markup)
    
    elif data.startswith("level_"):
        level = data.split("_")[1]
        user_data[user_id]['level'] = level
        save_data(user_data)
        await query.edit_message_text(f"✅ Встановлено рівень: **{level}**")
    
    elif data == "settings_languages":
        keyboard = [
            [InlineKeyboardButton("🇬🇧 Англійська", callback_data="lang_en")],
            [InlineKeyboardButton("🇩🇪 Німецька", callback_data="lang_de")],
            [InlineKeyboardButton("🇫🇷 Французька", callback_data="lang_fr")],
            [InlineKeyboardButton("🇪🇸 Іспанська", callback_data="lang_es")],
            [InlineKeyboardButton("🇮🇹 Італійська", callback_data="lang_it")],
            [InlineKeyboardButton("🇵🇱 Польська", callback_data="lang_pl")],
            [InlineKeyboardButton("🔙 Назад", callback_data="settings_back")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("Виберіть мови (можна кілька):", reply_markup=reply_markup)
    
    elif data.startswith("lang_"):
        lang = data.split("_")[1]
        if 'languages' not in user_data[user_id]:
            user_data[user_id]['languages'] = []
        
        if lang in user_data[user_id]['languages']:
            user_data[user_id]['languages'].remove(lang)
            status = "❌ Вимкнено"
        else:
            user_data[user_id]['languages'].append(lang)
            status = "✅ Увімкнено"
        
        save_data(user_data)
        await query.answer(f"{status}")
    
    elif data == "settings_reminders":
        keyboard = [
            [InlineKeyboardButton("✅ Увімкнути", callback_data="reminder_on")],
            [InlineKeyboardButton("❌ Вимкнути", callback_data="reminder_off")],
            [InlineKeyboardButton("⏰ Змінити час", callback_data="reminder_time")],
            [InlineKeyboardButton("🔙 Назад", callback_data="settings_back")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        enabled = user_data[user_id]['reminders']['enabled']
        time = user_data[user_id]['reminders']['time']
        status = "увімкнені" if enabled else "вимкнені"
        
        await query.edit_message_text(
            f"⏰ Нагадування {status}\nЧас: {time}",
            reply_markup=reply_markup
        )
    
    elif data == "reminder_on":
        user_data[user_id]['reminders']['enabled'] = True
        save_data(user_data)
        await query.edit_message_text("✅ Нагадування увімкнені!")
    
    elif data == "reminder_off":
        user_data[user_id]['reminders']['enabled'] = False
        save_data(user_data)
        await query.edit_message_text("❌ Нагадування вимкнені")
    
    elif data == "settings_back":
        await settings_command(update, context)
    
    # Гра
    elif data.startswith("game_answer:"):
        answer = data.split(":", 1)[1]
        correct = context.user_data.get('game_correct')
        
        if 'game_stats' not in user_data[user_id]:
            user_data[user_id]['game_stats'] = {'correct': 0, 'total': 0}
        
        user_data[user_id]['game_stats']['total'] += 1
        
        if answer == correct:
            user_data[user_id]['game_stats']['correct'] += 1
            save_data(user_data)
            await query.edit_message_text("🎉 Правильно!\n\nГрати ще раз: /game")
        else:
            save_data(user_data)
            await query.edit_message_text(f"❌ Неправильно. Правильна відповідь: **{correct}**\n\nГрати ще раз: /game")
        
        context.user_data.clear()
    
    # Повторення
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
            f"🇺🇦 **{card['ukrainian']}**\n\n🇬🇧 **{card['english']}**\n\nНаскільки добре запам'ятали?",
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
            await query.edit_message_text("🎉 Вітаю! Всі картки повторено!")
    
    # Додавання в картки
    elif data.startswith("add_to_cards:"):
        parts = data.split(":", 2)
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
        
        await query.edit_message_text(f"✅ Додано:\n🇺🇦 {ua_word} → 🇬🇧 {en_word}")

def main():
    TOKEN = os.getenv("TOKEN")
    
    application = Application.builder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("text", text_command))
    application.add_handler(CommandHandler("add", add_card))
    application.add_handler(CommandHandler("review", review))
    application.add_handler(CommandHandler("translate", translate_command))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CommandHandler("settings", settings_command))
    application.add_handler(CommandHandler("game", game_command))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("🤖 Бот запущено!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
