import logging
import json
import os
import random
import asyncio
import psycopg2
from psycopg2.extras import Json, RealDictCursor
from datetime import datetime, timedelta
from deep_translator import GoogleTranslator
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")

# Ініціалізація БД
def init_database():
    """Створює таблицю users якщо не існує"""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                data JSONB NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        cur.close()
        conn.close()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database init error: {e}")

# Завантаження даних користувача
def load_user_data(user_id):
    """Завантажує дані користувача з БД"""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute("SELECT data FROM users WHERE user_id = %s", (str(user_id),))
        result = cur.fetchone()
        
        cur.close()
        conn.close()
        
        if result:
            return result['data']
        return None
    except Exception as e:
        logger.error(f"Error loading user data: {e}")
        return None

# Збереження даних користувача
def save_user_data(user_id, data):
    """Зберігає дані користувача в БД"""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        
        cur.execute("""
            INSERT INTO users (user_id, data, updated_at)
            VALUES (%s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (user_id)
            DO UPDATE SET data = %s, updated_at = CURRENT_TIMESTAMP
        """, (str(user_id), Json(data), Json(data)))
        
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        logger.error(f"Error saving user data: {e}")

# Отримання всіх користувачів
def get_all_users():
    """Повертає всіх користувачів з БД"""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute("SELECT user_id, data FROM users")
        results = cur.fetchall()
        
        cur.close()
        conn.close()
        
        return {row['user_id']: row['data'] for row in results}
    except Exception as e:
        logger.error(f"Error getting all users: {e}")
        return {}

# Ініціалізація даних користувача
def init_user(user_id):
    user_id = str(user_id)
    data = load_user_data(user_id)
    
    if data is None:
        data = {
            'cards': [],
            'level': 'B1',
            'stats': {'total_reviews': 0, 'correct': 0, 'streak': 0},
            'target_language': 'en',
            'read_texts': [],
            'reminders': {'enabled': False, 'time': '20:00'},
            'game_stats': {'correct': 0, 'total': 0},
            'premium': False,
            'course': None,
            'course_progress': 0
        }
        save_user_data(user_id, data)
    
    return data

# Головне меню
def get_main_menu():
    keyboard = [
        [KeyboardButton("📖 Текст"), KeyboardButton("🔄 Перекласти")],
        [KeyboardButton("📚 Повторити"), KeyboardButton("📕 Словник")],
        [KeyboardButton("🎮 Ігри"), KeyboardButton("🎓 Курси")],
        [KeyboardButton("📊 Статистика"), KeyboardButton("⚙️ Налаштування")],
        [KeyboardButton("❓ Допомога")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# Тематичні словники
THEMATIC_VOCABULARIES = {
    '✈️ Подорожі': {
        'airport': 'аеропорт', 'flight': 'рейс', 'ticket': 'квиток', 'passport': 'паспорт',
        'luggage': 'багаж', 'hotel': 'готель', 'reservation': 'бронювання', 'tourist': 'турист',
        'guide': 'гід', 'map': 'карта', 'destination': 'пункт призначення', 'journey': 'подорож',
        'adventure': 'пригода', 'explore': 'досліджувати', 'vacation': 'відпустка', 'souvenir': 'сувенір',
        'beach': 'пляж', 'mountain': 'гора', 'city': 'місто', 'museum': 'музей',
        'restaurant': 'ресторан', 'taxi': 'таксі', 'train': 'поїзд', 'bus': 'автобус',
        'station': 'станція', 'arrival': 'прибуття', 'departure': 'відправлення', 'delay': 'затримка',
        'customs': 'митниця', 'visa': 'віза'
    },
    '🍔 Їжа': {
        'breakfast': 'сніданок', 'lunch': 'обід', 'dinner': 'вечеря', 'snack': 'перекус',
        'vegetable': 'овоч', 'fruit': 'фрукт', 'meat': 'м\'ясо', 'fish': 'риба',
        'bread': 'хліб', 'cheese': 'сир', 'milk': 'молоко', 'water': 'вода',
        'juice': 'сік', 'coffee': 'кава', 'tea': 'чай', 'sugar': 'цукор',
        'salt': 'сіль', 'pepper': 'перець', 'recipe': 'рецепт', 'dish': 'страва',
        'menu': 'меню', 'waiter': 'офіціант', 'bill': 'рахунок', 'delicious': 'смачний'
    },
    '💼 Бізнес': {
        'job': 'робота', 'career': 'кар\'єра', 'office': 'офіс', 'manager': 'менеджер',
        'employee': 'працівник', 'salary': 'зарплата', 'contract': 'контракт', 'meeting': 'зустріч',
        'project': 'проект', 'deadline': 'дедлайн', 'team': 'команда', 'colleague': 'колега',
        'boss': 'бос', 'client': 'клієнт', 'profit': 'прибуток', 'budget': 'бюджет'
    }
}

# База текстів (скорочена версія)
TEXTS_DATABASE = {
    'A1': [
        {"topic": "Daily routine", "text": "I wake up at 7 AM every day. I brush my teeth and wash my face. Then I eat breakfast with my family. I like to eat bread with jam and drink tea."},
        {"topic": "My family", "text": "I have a small family. There are four people: my mom, my dad, my sister, and me. My mom is a teacher. My dad is a doctor."}
    ],
    'B1': [
        {"topic": "Climate change", "text": "Climate change is one of the most pressing issues facing our planet today. Scientists warn that rising temperatures are causing polar ice caps to melt."}
    ]
}

# Курси
COURSES = {
    'beginner': {
        'name': '🌱 Початковий (A1→A2)',
        'duration': '3 місяці',
        'lessons': [
            {'title': 'Урок 1: Знайомство', 'words': 20, 'texts': 3},
            {'title': 'Урок 2: Сім\'я', 'words': 20, 'texts': 3}
        ]
    }
}

# Переклад
def translate_word(text, from_lang='auto', to_lang='uk'):
    try:
        translator = GoogleTranslator(source=from_lang, target=to_lang)
        return translator.translate(text)
    except Exception as e:
        logger.error(f"Translation error: {e}")
        return None

# Reverso приклади
def get_reverso_examples(word, source_lang='en', target_lang='uk'):
    try:
        import requests
        from bs4 import BeautifulSoup
        
        url = f"https://context.reverso.net/translation/{source_lang}-{target_lang}/{word}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=5)
        
        if response.status_code != 200:
            return []
        
        soup = BeautifulSoup(response.content, 'html.parser')
        examples = []
        
        for div in soup.find_all('div', class_='example')[:3]:
            source = div.find('div', class_='src')
            target = div.find('div', class_='trg')
            
            if source and target:
                examples.append({
                    'source': ' '.join(source.get_text(strip=True).split()),
                    'target': ' '.join(target.get_text(strip=True).split())
                })
        
        return examples
    except Exception as e:
        logger.error(f"Reverso error: {e}")
        return []

def get_flag(lang_code):
    flags = {'en': '🇬🇧', 'de': '🇩🇪', 'fr': '🇫🇷', 'es': '🇪🇸', 'it': '🇮🇹', 'pl': '🇵🇱'}
    return flags.get(lang_code, '🌍')

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    init_user(user_id)
    
    await update.message.reply_text("""
🎓 **Вітаю у Language Learning Bot!**

📖 **Тексти** - унікальні тексти для читання
🔄 **Переклад** - з реальними прикладами
📕 **Словник** - тематичні набори слів
📚 **Повторення** - інтервальна система
🎮 **Ігри** - скремблер та вгадування
🎓 **Курси** - структуровані програми

Використовуйте меню знизу 👇
    """, reply_markup=get_main_menu())

# Команда /help
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("""
📖 **Інструкція:**

**📖 Текст** - Читати текст
**🔄 Перекласти** - Перекласти слово
**📕 Словник** - Тематичні набори
**📚 Повторити** - Повторити слова
**🎮 Ігри** - Скремблер, вгадування
**🎓 Курси** - Програми навчання
**📊 Статистика** - Прогрес
**⚙️ Налаштування** - Рівень, мова

💡 Просто напишіть слово для перекладу!
    """, reply_markup=get_main_menu())

# Налаштування
async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    data = init_user(user_id)
    
    keyboard = [
        [InlineKeyboardButton(f"🎯 Рівень: {data['level']}", callback_data="settings_level")],
        [InlineKeyboardButton("🌍 Мова", callback_data="settings_language")],
        [InlineKeyboardButton("⏰ Нагадування", callback_data="settings_reminders")]
    ]
    
    await update.message.reply_text("⚙️ **Налаштування:**", reply_markup=InlineKeyboardMarkup(keyboard))

# Текст
async def text_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    data = init_user(user_id)
    
    level = data['level']
    texts = TEXTS_DATABASE.get(level, TEXTS_DATABASE['B1'])
    text_data = random.choice(texts)
    
    await update.message.reply_text(
        f"📖 **Рівень {level}**\n📌 {text_data['topic']}\n\n{text_data['text']}\n\n💡 Напишіть незнайоме слово!",
        reply_markup=get_main_menu()
    )

# Переклад
async def translate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введіть слово:", reply_markup=get_main_menu())
    context.user_data['waiting_for_translation'] = True

async def process_translation(update, word, context, message=None):
    user_id = str(update.effective_user.id if not message else update.message.from_user.id)
    data = init_user(user_id)
    
    target_lang = data['target_language']
    is_cyrillic = any('\u0400' <= char <= '\u04FF' for char in word)
    
    if is_cyrillic:
        translation = translate_word(word, from_lang='uk', to_lang=target_lang)
        from_word, to_word = word, translation
        from_flag, to_flag = "🇺🇦", get_flag(target_lang)
    else:
        translation = translate_word(word, from_lang=target_lang, to_lang='uk')
        from_word, to_word = word, translation
        from_flag, to_flag = get_flag(target_lang), "🇺🇦"
    
    if translation:
        response = f"{from_flag} **{from_word}**\n{to_flag} **{to_word}**"
        
        if len(from_word.split()) == 1 and not is_cyrillic:
            examples = get_reverso_examples(from_word, source_lang=target_lang, target_lang='uk')
            if examples:
                response += "\n\n📝 **Приклади:**"
                for i, ex in enumerate(examples, 1):
                    response += f"\n{i}. {ex['source']}\n   → {ex['target']}\n"
        
        keyboard = [[InlineKeyboardButton("➕ Додати в словник", callback_data=f"add_to_cards:{from_word}:{to_word}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if message:
            await message.reply_text(response, reply_markup=reply_markup)
        else:
            await update.callback_query.message.reply_text(response, reply_markup=reply_markup)

# Словник
async def dictionary_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    data = init_user(user_id)
    
    keyboard = [
        [InlineKeyboardButton("📋 Мої слова", callback_data="dict_my")],
        [InlineKeyboardButton("📚 Тематичні", callback_data="dict_thematic")]
    ]
    
    await update.message.reply_text(
        f"📕 **Словник**\n\nВаших слів: {len(data['cards'])}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# Ігри
async def games_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🎯 Вгадай переклад", callback_data="game_guess")],
        [InlineKeyboardButton("🔤 Скремблер", callback_data="game_scramble")]
    ]
    await update.message.reply_text("🎮 **Виберіть гру:**", reply_markup=InlineKeyboardMarkup(keyboard))

# Гра вгадування
async def game_guess_command(update: Update, context: ContextTypes.DEFAULT_TYPE, from_callback=False):
    user_id = str(update.effective_user.id if not from_callback else update.callback_query.from_user.id)
    data = init_user(user_id)
    
    if len(data['cards']) < 4:
        msg = "Потрібно мінімум 4 слова!"
        if from_callback:
            await update.callback_query.message.reply_text(msg)
        else:
            await update.message.reply_text(msg)
        return
    
    correct = random.choice(data['cards'])
    wrong = random.sample([c for c in data['cards'] if c != correct], 3)
    options = [correct] + wrong
    random.shuffle(options)
    
    context.user_data['game_correct'] = correct['english']
    
    keyboard = [[InlineKeyboardButton(opt['english'], callback_data=f"game_answer:{opt['english']}")] for opt in options]
    
    msg = f"🎮 **Вгадай**\n\n🇺🇦 {correct['ukrainian']}"
    
    if from_callback:
        await update.callback_query.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))

# Гра скремблер
async def game_scramble_command(update: Update, context: ContextTypes.DEFAULT_TYPE, from_callback=False):
    user_id = str(update.effective_user.id if not from_callback else update.callback_query.from_user.id)
    data = init_user(user_id)
    
    if not data['cards']:
        return
    
    card = random.choice(data['cards'])
    word = card['english']
    scrambled = ''.join(random.sample(word, len(word)))
    
    context.user_data['scramble_word'] = word.lower()
    context.user_data['scramble_translation'] = card['ukrainian']
    
    msg = f"🔤 **Скремблер**\n\nСкладіть слово: **{scrambled.upper()}**\n\n💡 Підказка: {card['ukrainian']}"
    
    if from_callback:
        await update.callback_query.message.reply_text(msg)
    else:
        await update.message.reply_text(msg)

# Статистика
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    data = init_user(user_id)
    
    await update.message.reply_text(f"""
📊 **Статистика**

🎯 Рівень: {data['level']}
📕 Слів: {len(data['cards'])}
✅ Повторень: {data['stats']['total_reviews']}
🎮 Ігор: {data['game_stats']['total']}
    """, reply_markup=get_main_menu())

# Повторення
async def review(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    data = init_user(user_id)
    
    if not data['cards']:
        await update.message.reply_text("Немає слів!", reply_markup=get_main_menu())
        return
    
    now = datetime.now()
    due = [i for i, c in enumerate(data['cards']) if datetime.fromisoformat(c['next_review']) <= now]
    
    if not due:
        await update.message.reply_text("🎉 Все повторено!", reply_markup=get_main_menu())
        return
    
    context.user_data['reviewing'] = True
    context.user_data['current_card_index'] = due[0]
    context.user_data['due_cards'] = due
    
    card = data['cards'][due[0]]
    
    await update.message.reply_text(
        f"📚 Картка 1/{len(due)}\n\n🇺🇦 **{card['ukrainian']}**",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Показати", callback_data="show_answer")]])
    )

# Обробка повідомлень
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    text = update.message.text
    
    # Меню
    if text == "📖 Текст":
        await text_command(update, context)
    elif text == "🔄 Перекласти":
        await translate_command(update, context)
    elif text == "📚 Повторити":
        await review(update, context)
    elif text == "📕 Словник":
        await dictionary_command(update, context)
    elif text == "🎮 Ігри":
        await games_menu(update, context)
    elif text == "📊 Статистика":
        await stats(update, context)
    elif text == "⚙️ Налаштування":
        await settings_command(update, context)
    elif text == "❓ Допомога":
        await help_command(update, context)
    # Скремблер
    elif context.user_data.get('scramble_word'):
        data = init_user(user_id)
        if text.lower() == context.user_data['scramble_word']:
            data['game_stats']['total'] += 1
            data['game_stats']['correct'] += 1
            save_user_data(user_id, data)
            context.user_data.clear()
            await update.message.reply_text("🎉 Правильно!")
        else:
            await update.message.reply_text("❌ Спробуйте ще")
    # Переклад
    elif context.user_data.get('waiting_for_translation'):
        context.user_data['waiting_for_translation'] = False
        await process_translation(update, text, context, message=update.message)
    else:
        await process_translation(update, text, context, message=update.message)

# Обробка кнопок
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = str(update.effective_user.id)
    data = init_user(user_id)
    
    # Ігри
    if query.data == "game_guess":
        await game_guess_command(update, context, True)
    elif query.data == "game_scramble":
        await game_scramble_command(update, context, True)
    elif query.data.startswith("game_answer:"):
        answer = query.data.split(":", 1)[1]
        correct = context.user_data.get('game_correct')
        
        data['game_stats']['total'] += 1
        if answer == correct:
            data['game_stats']['correct'] += 1
            await query.edit_message_text("🎉 Правильно!")
        else:
            await query.edit_message_text(f"❌ Правильно: {correct}")
        
        save_user_data(user_id, data)
    
    # Словник
    elif query.data == "dict_my":
        if data['cards']:
            msg = "📕 **Ваші слова:**\n\n"
            for c in data['cards'][:10]:
                msg += f"🇺🇦 {c['ukrainian']} → 🇬🇧 {c['english']}\n"
            await query.edit_message_text(msg)
        else:
            await query.edit_message_text("Словник порожній")
    
    elif query.data == "dict_thematic":
        keyboard = [[InlineKeyboardButton(t, callback_data=f"vocab_{t}")] for t in THEMATIC_VOCABULARIES.keys()]
        await query.edit_message_text("Виберіть тему:", reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif query.data.startswith("vocab_"):
        theme = query.data.replace("vocab_", "")
        words = THEMATIC_VOCABULARIES.get(theme, {})
        
        msg = f"**{theme}**\n\nСлів: {len(words)}\n\n"
        for i, (en, ua) in enumerate(list(words.items())[:5], 1):
            msg += f"{i}. {en} - {ua}\n"
        
        keyboard = [[InlineKeyboardButton("➕ Додати всі", callback_data=f"vocab_add_{theme}")]]
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif query.data.startswith("vocab_add_"):
        theme = query.data.replace("vocab_add_", "")
        words = THEMATIC_VOCABULARIES.get(theme, {})
        
        added = 0
        for en, ua in words.items():
            if not any(c['english'].lower() == en.lower() for c in data['cards']):
                data['cards'].append({
                    'ukrainian': ua,
                    'english': en,
                    'added_date': datetime.now().isoformat(),
                    'next_review': datetime.now().isoformat(),
                    'interval': 1
                })
                added += 1
        
        save_user_data(user_id, data)
        await query.edit_message_text(f"✅ Додано {added} слів!")
    
    # Додати слово
    elif query.data.startswith("add_to_cards:"):
        parts = query.data.split(":", 2)
        word1, word2 = parts[1], parts[2]
        
        is_cyr = any('\u0400' <= c <= '\u04FF' for c in word1)
        ua, en = (word1, word2) if is_cyr else (word2, word1)
        
        if not any(c['english'].lower() == en.lower() for c in data['cards']):
            data['cards'].append({
                'ukrainian': ua,
                'english': en,
                'added_date': datetime.now().isoformat(),
                'next_review': datetime.now().isoformat(),
                'interval': 1
            })
            save_user_data(user_id, data)
            await query.edit_message_text(f"✅ Додано: {ua} → {en}")
        else:
            await query.edit_message_text("Вже є в словнику!")
    
    # Повторення
    elif query.data == "show_answer":
        idx = context.user_data.get('current_card_index')
        card = data['cards'][idx]
        
        keyboard = [
            [InlineKeyboardButton("😊 Легко (7д)", callback_data="diff_easy")],
            [InlineKeyboardButton("🤔 Середньо (3д)", callback_data="diff_medium")],
            [InlineKeyboardButton("😓 Важко (1д)", callback_data="diff_hard")]
        ]
        
        await query.edit_message_text(
            f"🇺🇦 {card['ukrainian']}\n\n🇬🇧 {card['english']}\n\nНаскільки добре?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif query.data.startswith("diff_"):
        diff = query.data.split("_")[1]
        intervals = {'easy': 7, 'medium': 3, 'hard': 1}
        
        idx = context.user_data.get('current_card_index')
        data['cards'][idx]['next_review'] = (datetime.now() + timedelta(days=intervals[diff])).isoformat()
        data['stats']['total_reviews'] += 1
        
        if diff in ['easy', 'medium']:
            data['stats']['correct'] += 1
        
        save_user_data(user_id, data)
        
        due = context.user_data['due_cards']
        pos = due.index(idx)
        
        if pos + 1 < len(due):
            next_idx = due[pos + 1]
            context.user_data['current_card_index'] = next_idx
            card = data['cards'][next_idx]
            
            await query.edit_message_text(
                f"📚 Картка {pos + 2}/{len(due)}\n\n🇺🇦 **{card['ukrainian']}**",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Показати", callback_data="show_answer")]])
            )
        else:
            context.user_data.clear()
            await query.edit_message_text("🎉 Все повторено!")
    
    # Налаштування
    elif query.data == "settings_level":
        keyboard = [
            [InlineKeyboardButton("A1", callback_data="level_A1")],
            [InlineKeyboardButton("A2", callback_data="level_A2")],
            [InlineKeyboardButton("B1", callback_data="level_B1")],
            [InlineKeyboardButton("B2", callback_data="level_B2")],
            [InlineKeyboardButton("C1", callback_data="level_C1")]
        ]
        await query.edit_message_text("Виберіть рівень:", reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif query.data.startswith("level_"):
        level = query.data.split("_")[1]
        data['level'] = level
        data['read_texts'] = []
        save_user_data(user_id, data)
        await query.edit_message_text(f"✅ Рівень: {level}")
    
    elif query.data == "settings_language":
        keyboard = [
            [InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")],
            [InlineKeyboardButton("🇩🇪 Deutsch", callback_data="lang_de")],
            [InlineKeyboardButton("🇫🇷 Français", callback_data="lang_fr")]
        ]
        await query.edit_message_text("Мова:", reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif query.data.startswith("lang_"):
        lang = query.data.split("_")[1]
        data['target_language'] = lang
        save_user_data(user_id, data)
        await query.edit_message_text(f"✅ Мова встановлено")
    
    elif query.data == "settings_reminders":
        keyboard = [
            [InlineKeyboardButton("09:00", callback_data="rem_09:00"), InlineKeyboardButton("12:00", callback_data="rem_12:00")],
            [InlineKeyboardButton("18:00", callback_data="rem_18:00"), InlineKeyboardButton("20:00", callback_data="rem_20:00")],
            [InlineKeyboardButton("❌ Вимкнути", callback_data="rem_off")]
        ]
        
        status = "✅ увімкнені" if data['reminders']['enabled'] else "❌ вимкнені"
        await query.edit_message_text(
            f"⏰ Нагадування {status}\n\nЧас: {data['reminders']['time']}\n\nВиберіть час:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif query.data.startswith("rem_"):
        if query.data == "rem_off":
            data['reminders']['enabled'] = False
            save_user_data(user_id, data)
            await query.edit_message_text("❌ Нагадування вимкнено")
        else:
            time = query.data.replace("rem_", "")
            data['reminders']['time'] = time
            data['reminders']['enabled'] = True
            save_user_data(user_id, data)
            await query.edit_message_text(f"✅ Нагадування о {time}")

# Нагадування
async def send_reminders(application: Application):
    """Відправляє нагадування користувачам"""
    while True:
        try:
            now = datetime.now()
            current_time = now.strftime("%H:%M")
            
            all_users = get_all_users()
            
            for user_id, data in all_users.items():
                reminders = data.get('reminders', {})
                
                if reminders.get('enabled') and reminders.get('time') == current_time:
                    try:
                        cards_count = len(data.get('cards', []))
                        
                        messages = [
                            f"⏰ Час практикувати!\n\nУ вас {cards_count} слів для повторення.",
                            f"⏰ Не забудьте попрактикувати!\n\n📚 Повторіть кілька слів сьогодні.",
                            f"⏰ Час вивчати!\n\n🎮 Може зіграємо в Скремблер?",
                            f"⏰ Вітаю!\n\n📖 Може прочитаєте новий текст сьогодні?",
                        ]
                        
                        message = random.choice(messages)
                        
                        await application.bot.send_message(
                            chat_id=user_id,
                            text=message,
                            reply_markup=get_main_menu()
                        )
                        
                        logger.info(f"Reminder sent to user {user_id}")
                    
                    except Exception as e:
                        logger.error(f"Error sending reminder to {user_id}: {e}")
            
            await asyncio.sleep(60)
        
        except Exception as e:
            logger.error(f"Error in send_reminders: {e}")
            await asyncio.sleep(60)

def main():
    # Ініціалізація БД
    init_database()
    
    TOKEN = os.getenv("TOKEN")
    application = Application.builder().token(TOKEN).build()
    
    # Команди
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("text", text_command))
    application.add_handler(CommandHandler("review", review))
    application.add_handler(CommandHandler("translate", translate_command))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CommandHandler("settings", settings_command))
    application.add_handler(CommandHandler("games", games_menu))
    application.add_handler(CommandHandler("dictionary", dictionary_command))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Запуск нагадувань після старту бота
    async def post_init(app: Application) -> None:
        app.create_task(send_reminders(app))
    
    application.post_init = post_init
    
    print("🤖 Бот з PostgreSQL запущено!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
