import logging
import json
import os
import random
import asyncio
import psycopg2
from psycopg2.extras import Json, RealDictCursor
from datetime import datetime, timedelta, date
from deep_translator import GoogleTranslator
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")

# ==================== БАЗА ДАНИХ ====================

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

# ==================== ІНІЦІАЛІЗАЦІЯ КОРИСТУВАЧА ====================

def init_user(user_id):
    user_id = str(user_id)
    data = load_user_data(user_id)
    
    if data is None:
        data = {
            # Колоди (Decks)
            'decks': {
                'default': {
                    'name': '📚 Мої слова',
                    'cards': [],
                    'created_at': datetime.now().isoformat()
                }
            },
            'active_deck': 'default',
            
            # Статистика
            'stats': {
                'total_reviews': 0,
                'correct_reviews': 0,
                'current_streak': 0,
                'longest_streak': 0,
                'last_review_date': None,
                'total_study_time': 0,  # в хвилинах
                'daily_goal': 20,  # слів на день
                'daily_progress': {},  # {date: count}
                'cards_learned': 0,  # кількість вивчених карток
                'accuracy': 100.0  # точність у відсотках
            },
            
            # Досягнення
            'achievements': {
                'first_word': False,
                'streak_3': False,
                'streak_7': False,
                'streak_30': False,
                'learned_50': False,
                'learned_100': False,
                'learned_500': False,
                'perfect_session': False,
                'night_owl': False,
                'early_bird': False
            },
            
            # Налаштування
            'settings': {
                'level': 'B1',
                'target_language': 'en',
                'reminders': {
                    'enabled': True,
                    'time': '20:00',
                    'smart_reminders': True
                },
                'show_examples': True,
                'auto_play_audio': False,
                'review_order': 'smart'  # smart, random, oldest
            },
            
            # Інше
            'created_at': datetime.now().isoformat(),
            'last_active': datetime.now().isoformat()
        }
        save_user_data(user_id, data)
    
    # Оновлюємо час останньої активності
    data['last_active'] = datetime.now().isoformat()
    save_user_data(user_id, data)
    
    return data

# ==================== ГОЛОВНЕ МЕНЮ ====================

def get_main_menu():
    """Головне меню як у Reword"""
    keyboard = [
        [KeyboardButton("🎯 Вивчати"), KeyboardButton("📊 Статистика")],
        [KeyboardButton("📚 Колоди"), KeyboardButton("➕ Додати")],
        [KeyboardButton("🏆 Досягнення"), KeyboardButton("⚙️ Налаштування")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# ==================== ПЕРЕКЛАД ====================

def translate_word(text, from_lang='auto', to_lang='uk'):
    try:
        translator = GoogleTranslator(source=from_lang, target=to_lang)
        return translator.translate(text)
    except Exception as e:
        logger.error(f"Translation error: {e}")
        return None

def get_flag(lang_code):
    flags = {'en': '🇬🇧', 'de': '🇩🇪', 'fr': '🇫🇷', 'es': '🇪🇸', 'it': '🇮🇹', 'pl': '🇵🇱'}
    return flags.get(lang_code, '🌍')

# ==================== STREAK СИСТЕМА ====================

def update_streak(data):
    """Оновлює streak користувача"""
    today = date.today().isoformat()
    last_review = data['stats'].get('last_review_date')
    
    if last_review is None:
        # Перший раз
        data['stats']['current_streak'] = 1
        data['stats']['longest_streak'] = 1
    elif last_review == today:
        # Вже вчив сьогодні
        pass
    else:
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        if last_review == yesterday:
            # Продовжуємо streak
            data['stats']['current_streak'] += 1
            if data['stats']['current_streak'] > data['stats']['longest_streak']:
                data['stats']['longest_streak'] = data['stats']['current_streak']
        else:
            # Streak перервано
            data['stats']['current_streak'] = 1
    
    data['stats']['last_review_date'] = today
    
    # Оновлюємо щоденний прогрес
    if today not in data['stats']['daily_progress']:
        data['stats']['daily_progress'][today] = 0
    
    return data

def get_streak_emoji(streak):
    """Повертає емодзі залежно від streak"""
    if streak >= 30:
        return "🔥💎"
    elif streak >= 14:
        return "🔥🔥"
    elif streak >= 7:
        return "🔥"
    elif streak >= 3:
        return "⭐"
    else:
        return "✨"

# ==================== СИСТЕМА КАРТОК ====================

def create_card(ukrainian, english, deck='default', difficulty='new'):
    """Створює нову картку"""
    return {
        'ukrainian': ukrainian,
        'english': english,
        'difficulty': difficulty,  # new, learning, easy, medium, hard, mastered
        'created_at': datetime.now().isoformat(),
        'next_review': datetime.now().isoformat(),
        'interval': 1,  # днів до наступного повторення
        'ease_factor': 2.5,  # фактор легкості (для SM-2 алгоритму)
        'reviews': 0,
        'correct_reviews': 0,
        'last_reviewed': None,
        'deck': deck,
        'examples': [],
        'notes': ''
    }

def get_cards_due(data, deck=None):
    """Повертає картки які треба повторити"""
    if deck is None:
        deck = data['active_deck']
    
    cards = data['decks'].get(deck, {}).get('cards', [])
    now = datetime.now()
    
    due_cards = []
    for i, card in enumerate(cards):
        next_review = datetime.fromisoformat(card['next_review'])
        if next_review <= now:
            due_cards.append(i)
    
    return due_cards

def get_new_cards(data, deck=None, limit=5):
    """Повертає нові картки для вивчення"""
    if deck is None:
        deck = data['active_deck']
    
    cards = data['decks'].get(deck, {}).get('cards', [])
    
    new_cards = []
    for i, card in enumerate(cards):
        if card['difficulty'] == 'new' and card['reviews'] == 0:
            new_cards.append(i)
            if len(new_cards) >= limit:
                break
    
    return new_cards

# ==================== SM-2 АЛГОРИТМ (як у Anki/Reword) ====================

def calculate_next_interval(card, quality):
    """
    Розраховує наступний інтервал за алгоритмом SM-2
    quality: 0-5 (0=знову, 1=важко, 2-3=добре, 4-5=легко)
    """
    if quality < 3:
        # Неправильна відповідь - повертаємо на початок
        card['interval'] = 1
        card['ease_factor'] = max(1.3, card['ease_factor'] - 0.2)
        card['difficulty'] = 'learning'
    else:
        # Правильна відповідь
        if card['reviews'] == 0:
            card['interval'] = 1
        elif card['reviews'] == 1:
            card['interval'] = 6
        else:
            card['interval'] = round(card['interval'] * card['ease_factor'])
        
        # Оновлюємо ease_factor
        card['ease_factor'] = card['ease_factor'] + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
        card['ease_factor'] = max(1.3, card['ease_factor'])
        
        # Оновлюємо складність
        if card['interval'] >= 21:
            card['difficulty'] = 'mastered'
        elif card['interval'] >= 7:
            card['difficulty'] = 'easy'
        elif card['interval'] >= 3:
            card['difficulty'] = 'medium'
        else:
            card['difficulty'] = 'learning'
    
    card['next_review'] = (datetime.now() + timedelta(days=card['interval'])).isoformat()
    card['reviews'] += 1
    if quality >= 3:
        card['correct_reviews'] += 1
    card['last_reviewed'] = datetime.now().isoformat()
    
    return card

# ==================== КОМАНДИ ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    data = init_user(user_id)
    
    welcome_text = f"""
🎓 **Вітаємо у Reword Bot!**

Розумна система вивчення слів з інтервальним повторенням.

📊 **Ваш прогрес:**
🔥 Streak: {data['stats']['current_streak']} днів
📚 Вивчено: {data['stats']['cards_learned']} слів
🎯 Точність: {data['stats']['accuracy']:.0f}%

**Що можна робити:**
🎯 **Вивчати** - розпочати сесію
📊 **Статистика** - детальна статистика
📚 **Колоди** - керування колодами
➕ **Додати** - додати нове слово
🏆 **Досягнення** - ваші нагороди
⚙️ **Налаштування** - персоналізація

💡 Почніть з додавання слів або вивчення!
"""
    
    await update.message.reply_text(welcome_text, reply_markup=get_main_menu())

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
📖 **Довідка Reword Bot**

**🎯 Вивчати**
Розпочинає сесію навчання. Система автоматично вибере:
• Нові слова для вивчення
• Слова що треба повторити
• Складні слова для закріплення

**📊 Статистика**
Ваш прогрес:
• Щоденна активність
• Streak (послідовні дні)
• Точність відповідей
• Графіки прогресу

**📚 Колоди**
Організуйте слова за темами:
• Створіть кілька колод
• Перемикайтеся між ними
• Відстежуйте прогрес кожної

**➕ Додати слово**
Два способи додавання:
• Швидке: напишіть слово
• Детальне: з прикладами та нотатками

**🏆 Досягнення**
Отримуйте нагороди за:
• Регулярність навчання
• Кількість вивчених слів
• Досконалі сесії

**⚙️ Налаштування**
• Щоденна ціль
• Час нагадувань
• Режим повторення
• Інше

💡 Система використовує SM-2 алгоритм для оптимального запам'ятовування!
"""
    
    await update.message.reply_text(help_text, reply_markup=get_main_menu())

# ==================== СТАТИСТИКА ====================

async def show_statistics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    data = init_user(user_id)
    stats = data['stats']
    
    # Підраховуємо картки
    total_cards = sum(len(deck['cards']) for deck in data['decks'].values())
    mastered = sum(1 for deck in data['decks'].values() for card in deck['cards'] if card['difficulty'] == 'mastered')
    learning = sum(1 for deck in data['decks'].values() for card in deck['cards'] if card['difficulty'] in ['learning', 'new'])
    
    # Щоденна ціль
    today = date.today().isoformat()
    today_progress = stats['daily_progress'].get(today, 0)
    daily_goal = stats['daily_goal']
    progress_bar = create_progress_bar(today_progress, daily_goal)
    
    # Streak емодзі
    streak_emoji = get_streak_emoji(stats['current_streak'])
    
    stats_text = f"""
📊 **Ваша статистика**

{streak_emoji} **Streak:** {stats['current_streak']} днів (рекорд: {stats['longest_streak']})

📚 **Картки:**
• Всього: {total_cards}
• Вивчено: {mastered} 🌟
• Вивчається: {learning} 📖

🎯 **Щоденна ціль:** {today_progress}/{daily_goal}
{progress_bar}

📈 **Загальна статистика:**
• Всього повторень: {stats['total_reviews']}
• Правильних: {stats['correct_reviews']}
• Точність: {stats['accuracy']:.1f}%
• Час навчання: {stats['total_study_time']} хв

📅 **Ця тиждень:**
{get_week_stats(stats)}
"""
    
    keyboard = [
        [InlineKeyboardButton("📈 Детальна статистика", callback_data="detailed_stats")],
        [InlineKeyboardButton("🎯 Змінити ціль", callback_data="change_goal")]
    ]
    
    await update.message.reply_text(stats_text, reply_markup=InlineKeyboardMarkup(keyboard))

def create_progress_bar(current, goal, length=10):
    """Створює прогрес бар"""
    if goal == 0:
        return "▱" * length
    
    filled = min(int((current / goal) * length), length)
    empty = length - filled
    
    bar = "▰" * filled + "▱" * empty
    percentage = min(int((current / goal) * 100), 100)
    
    return f"{bar} {percentage}%"

def get_week_stats(stats):
    """Статистика за тиждень"""
    week_text = ""
    for i in range(6, -1, -1):
        day = (date.today() - timedelta(days=i)).isoformat()
        count = stats['daily_progress'].get(day, 0)
        day_name = (date.today() - timedelta(days=i)).strftime("%a")
        
        if count > 0:
            bars = "█" * min(count // 5 + 1, 5)
            week_text += f"{day_name}: {bars} ({count})\n"
        else:
            week_text += f"{day_name}: ▱\n"
    
    return week_text

# ==================== КОЛОДИ ====================

async def show_decks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    data = init_user(user_id)
    
    decks_text = "📚 **Ваші колоди:**\n\n"
    
    keyboard = []
    for deck_id, deck in data['decks'].items():
        total = len(deck['cards'])
        due = len(get_cards_due(data, deck_id))
        new = len(get_new_cards(data, deck_id))
        
        active_mark = "✅ " if deck_id == data['active_deck'] else ""
        decks_text += f"{active_mark}**{deck['name']}**\n"
        decks_text += f"📊 {total} слів | 🔄 {due} до повторення | 🆕 {new} нових\n\n"
        
        keyboard.append([InlineKeyboardButton(
            f"{active_mark}{deck['name']}", 
            callback_data=f"deck_select_{deck_id}"
        )])
    
    keyboard.append([InlineKeyboardButton("➕ Створити колоду", callback_data="deck_create")])
    
    await update.message.reply_text(decks_text, reply_markup=InlineKeyboardMarkup(keyboard))

# ==================== ДОДАВАННЯ СЛОВА ====================

async def add_word_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Початок додавання слова"""
    context.user_data['adding_word'] = True
    context.user_data['word_step'] = 'ukrainian'
    
    keyboard = [[KeyboardButton("❌ Скасувати")]]
    
    await update.message.reply_text(
        "➕ **Додати нове слово**\n\n"
        "Крок 1/2: Напишіть слово українською:\n\n"
        "💡 Наприклад: собака",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

async def process_add_word(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    """Обробка додавання слова"""
    user_id = str(update.effective_user.id)
    data = init_user(user_id)
    
    if text == "❌ Скасувати":
        context.user_data['adding_word'] = False
        await update.message.reply_text("❌ Скасовано", reply_markup=get_main_menu())
        return
    
    step = context.user_data.get('word_step')
    
    if step == 'ukrainian':
        context.user_data['word_ukrainian'] = text.strip()
        context.user_data['word_step'] = 'english'
        
        await update.message.reply_text(
            f"✅ Українське: **{text}**\n\n"
            f"Крок 2/2: Переклад англійською:\n\n"
            f"💡 Наприклад: dog"
        )
    
    elif step == 'english':
        ukrainian = context.user_data.get('word_ukrainian', '')
        english = text.strip()
        
        # Створюємо картку
        deck = data['active_deck']
        card = create_card(ukrainian, english, deck)
        
        if deck not in data['decks']:
            data['decks'][deck] = {'name': deck, 'cards': []}
        
        data['decks'][deck]['cards'].append(card)
        
        # Перше досягнення
        if not data['achievements']['first_word']:
            data['achievements']['first_word'] = True
            achievement_text = "\n\n🏆 **Досягнення розблоковано:** Перше слово!"
        else:
            achievement_text = ""
        
        save_user_data(user_id, data)
        
        context.user_data['adding_word'] = False
        context.user_data['word_step'] = None
        
        keyboard = [
            [InlineKeyboardButton("➕ Додати ще", callback_data="add_another")],
            [InlineKeyboardButton("🎯 Почати вивчати", callback_data="start_learning")]
        ]
        
        total_cards = sum(len(d['cards']) for d in data['decks'].values())
        
        await update.message.reply_text(
            f"✅ **Слово додано!**\n\n"
            f"🇺🇦 {ukrainian}\n"
            f"🇬🇧 {english}\n\n"
            f"📚 Всього слів: {total_cards}{achievement_text}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        await asyncio.sleep(1)
        await update.message.reply_text("Головне меню:", reply_markup=get_main_menu())

# ==================== НАВЧАННЯ ====================

async def start_learning(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Початок сесії навчання"""
    user_id = str(update.effective_user.id)
    data = init_user(user_id)
    
    deck = data['active_deck']
    due = get_cards_due(data, deck)
    new = get_new_cards(data, deck, limit=5)
    
    # Комбінуємо картки
    cards_to_review = due + new
    
    if not cards_to_review:
        await update.message.reply_text(
            "🎉 **Вітаємо!**\n\n"
            "Немає карток для повторення сьогодні!\n\n"
            "➕ Додайте нові слова або поверніться пізніше.",
            reply_markup=get_main_menu()
        )
        return
    
    # Перемішуємо
    random.shuffle(cards_to_review)
    
    context.user_data['learning_session'] = {
        'cards': cards_to_review,
        'current': 0,
        'correct': 0,
        'start_time': datetime.now(),
        'deck': deck
    }
    
    keyboard = [
        [InlineKeyboardButton("📖 Класичний", callback_data="learn_classic")],
        [InlineKeyboardButton("🎯 Тест (1 з 4)", callback_data="learn_quiz")],
        [InlineKeyboardButton("✍️ Написання", callback_data="learn_typing")]
    ]
    
    await update.message.reply_text(
        f"🎯 **Сесія навчання**\n\n"
        f"📚 Слів до вивчення: {len(cards_to_review)}\n"
        f"🔄 До повторення: {len(due)}\n"
        f"🆕 Нових: {len(new)}\n\n"
        f"Виберіть режим:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def show_learning_card(query, context, mode='classic'):
    """Показує картку для вивчення"""
    session = context.user_data.get('learning_session')
    if not session:
        await query.edit_message_text("Сесія завершена")
        return
    
    user_id = str(query.from_user.id)
    data = init_user(user_id)
    
    cards = session['cards']
    current_idx = session['current']
    
    if current_idx >= len(cards):
        # Завершення сесії
        await finish_learning_session(query, context, user_id, data)
        return
    
    card_idx = cards[current_idx]
    deck = session['deck']
    card = data['decks'][deck]['cards'][card_idx]
    
    if mode == 'classic':
        keyboard = [[InlineKeyboardButton("👁 Показати відповідь", callback_data="show_card_answer")]]
        
        await query.edit_message_text(
            f"📚 Картка {current_idx + 1}/{len(cards)}\n\n"
            f"🇺🇦 **{card['ukrainian']}**\n\n"
            f"🔄 Повторень: {card['reviews']}\n"
            f"📊 Рівень: {get_difficulty_emoji(card['difficulty'])}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif mode == 'quiz':
        # Вікторина
        await show_quiz_card_learning(query, context, data, deck, card_idx, current_idx, len(cards))

def get_difficulty_emoji(difficulty):
    """Емодзі для рівня складності"""
    emojis = {
        'new': '🆕 Нове',
        'learning': '📖 Вивчається',
        'easy': '😊 Легко',
        'medium': '🤔 Середнє',
        'hard': '😓 Складно',
        'mastered': '⭐ Вивчено'
    }
    return emojis.get(difficulty, '📖')

async def show_quiz_card_learning(query, context, data, deck, card_idx, current, total):
    """Показує картку-тест"""
    card = data['decks'][deck]['cards'][card_idx]
    
    # Генеруємо неправильні відповіді
    all_cards = data['decks'][deck]['cards']
    wrong = [c for i, c in enumerate(all_cards) if i != card_idx]
    
    if len(wrong) >= 3:
        wrong_options = random.sample(wrong, 3)
    else:
        wrong_options = wrong
    
    options = [card] + wrong_options
    random.shuffle(options)
    
    context.user_data['quiz_correct'] = card['english']
    
    keyboard = []
    for opt in options:
        keyboard.append([InlineKeyboardButton(
            opt['english'],
            callback_data=f"quiz_ans_{opt['english']}"
        )])
    
    await query.edit_message_text(
        f"🎯 Тест {current + 1}/{total}\n\n"
        f"🇺🇦 **{card['ukrainian']}**\n\n"
        f"Виберіть правильний переклад:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def finish_learning_session(query, context, user_id, data):
    """Завершує сесію навчання"""
    session = context.user_data.get('learning_session')
    if not session:
        return
    
    # Підраховуємо статистику
    total = len(session['cards'])
    correct = session.get('correct', 0)
    duration = (datetime.now() - session['start_time']).total_seconds() / 60
    
    # Оновлюємо streak
    data = update_streak(data)
    
    # Оновлюємо щоденний прогрес
    today = date.today().isoformat()
    data['stats']['daily_progress'][today] = data['stats']['daily_progress'].get(today, 0) + total
    
    # Оновлюємо загальну статистику
    data['stats']['total_study_time'] += int(duration)
    
    # Точність
    if data['stats']['total_reviews'] > 0:
        data['stats']['accuracy'] = (data['stats']['correct_reviews'] / data['stats']['total_reviews']) * 100
    
    # Перевіряємо досягнення
    achievements_unlocked = []
    
    if correct == total and total >= 10 and not data['achievements']['perfect_session']:
        data['achievements']['perfect_session'] = True
        achievements_unlocked.append("🏆 Ідеальна сесія")
    
    if data['stats']['current_streak'] >= 3 and not data['achievements']['streak_3']:
        data['achievements']['streak_3'] = True
        achievements_unlocked.append("🔥 3 дні підряд")
    
    if data['stats']['current_streak'] >= 7 and not data['achievements']['streak_7']:
        data['achievements']['streak_7'] = True
        achievements_unlocked.append("🔥 Тиждень streak")
    
    save_user_data(user_id, data)
    
    # Повідомлення
    percentage = int((correct / total) * 100) if total > 0 else 0
    
    if percentage >= 90:
        result_emoji = "🏆"
        result_text = "Чудова робота!"
    elif percentage >= 70:
        result_emoji = "🌟"
        result_text = "Добре!"
    else:
        result_emoji = "💪"
        result_text = "Продовжуйте!"
    
    achievements_text = ""
    if achievements_unlocked:
        achievements_text = "\n\n🏆 **Досягнення:**\n" + "\n".join(f"• {a}" for a in achievements_unlocked)
    
    streak_emoji = get_streak_emoji(data['stats']['current_streak'])
    
    result_message = f"""
{result_emoji} **Сесію завершено!**

📊 **Результат:**
• Картки: {total}
• Правильно: {correct} ({percentage}%)
• Час: {int(duration)} хв

{streak_emoji} **Streak:** {data['stats']['current_streak']} днів

{result_text}{achievements_text}
"""
    
    keyboard = [
        [InlineKeyboardButton("🔄 Ще раз", callback_data="start_learning")],
        [InlineKeyboardButton("📊 Статистика", callback_data="show_stats")]
    ]
    
    await query.edit_message_text(result_message, reply_markup=InlineKeyboardMarkup(keyboard))
    
    context.user_data.pop('learning_session', None)

# ==================== ДОСЯГНЕННЯ ====================

async def show_achievements(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    data = init_user(user_id)
    
    achievements = data['achievements']
    
    achievements_list = [
        ('first_word', '📚', 'Перше слово', 'Додайте перше слово'),
        ('streak_3', '🔥', '3 дні streak', 'Вчіться 3 дні підряд'),
        ('streak_7', '🔥🔥', 'Тиждень streak', 'Вчіться тиждень підряд'),
        ('streak_30', '💎', '30 днів streak', 'Вчіться місяць підряд'),
        ('learned_50', '⭐', '50 слів', 'Вивчіть 50 слів'),
        ('learned_100', '🌟', '100 слів', 'Вивчіть 100 слів'),
        ('learned_500', '💫', '500 слів', 'Вивчіть 500 слів'),
        ('perfect_session', '🏆', 'Ідеальна сесія', '100% у сесії з 10+ слів'),
        ('night_owl', '🦉', 'Нічна сова', 'Вчіться після 23:00'),
        ('early_bird', '🐦', 'Рання пташка', 'Вчіться до 7:00')
    ]
    
    text = "🏆 **Ваші досягнення**\n\n"
    
    unlocked = 0
    for key, emoji, name, desc in achievements_list:
        if achievements.get(key, False):
            text += f"{emoji} **{name}** ✅\n"
            unlocked += 1
        else:
            text += f"🔒 {name}\n   _{desc}_\n"
        text += "\n"
    
    text += f"\n📊 Розблоковано: {unlocked}/{len(achievements_list)}"
    
    await update.message.reply_text(text, reply_markup=get_main_menu())

# ==================== НАЛАШТУВАННЯ ====================

async def show_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    data = init_user(user_id)
    settings = data['settings']
    
    keyboard = [
        [InlineKeyboardButton(f"🎯 Щоденна ціль: {data['stats']['daily_goal']}", callback_data="set_daily_goal")],
        [InlineKeyboardButton(f"⏰ Нагадування: {settings['reminders']['time']}", callback_data="set_reminder_time")],
        [InlineKeyboardButton(f"📊 Рівень: {settings['level']}", callback_data="set_level")],
        [InlineKeyboardButton(f"🌍 Мова: {settings['target_language']}", callback_data="set_language")]
    ]
    
    await update.message.reply_text(
        "⚙️ **Налаштування**\n\nВиберіть опцію:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ==================== ОБРОБКА ПОВІДОМЛЕНЬ ====================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    
    # Головні кнопки меню
    if text == "🎯 Вивчати":
        await start_learning(update, context)
    elif text == "📊 Статистика":
        await show_statistics(update, context)
    elif text == "📚 Колоди":
        await show_decks(update, context)
    elif text == "➕ Додати":
        await add_word_start(update, context)
    elif text == "🏆 Досягнення":
        await show_achievements(update, context)
    elif text == "⚙️ Налаштування":
        await show_settings(update, context)
    # Додавання слова
    elif context.user_data.get('adding_word'):
        await process_add_word(update, context, text)
    # Режим написання в навчанні
    elif context.user_data.get('learning_mode') == 'typing':
        await process_typing_answer(update, context, text)
    else:
        # Швидке додавання через переклад
        await quick_translate(update, context, text)

async def quick_translate(update: Update, context: ContextTypes.DEFAULT_TYPE, word: str):
    """Швидкий переклад і додавання слова"""
    user_id = str(update.effective_user.id)
    data = init_user(user_id)
    
    is_cyrillic = any('\u0400' <= char <= '\u04FF' for char in word)
    
    if is_cyrillic:
        translation = translate_word(word, from_lang='uk', to_lang='en')
        from_word, to_word = word, translation
        from_flag, to_flag = "🇺🇦", "🇬🇧"
    else:
        translation = translate_word(word, from_lang='en', to_lang='uk')
        from_word, to_word = translation, word
        from_flag, to_flag = "🇺🇦", "🇬🇧"
    
    if translation:
        keyboard = [[InlineKeyboardButton("➕ Додати до колоди", callback_data=f"quick_add:{from_word}:{to_word}")]]
        
        await update.message.reply_text(
            f"{from_flag} **{from_word}**\n{to_flag} **{to_word}**",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def process_typing_answer(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    """Обробка відповіді в режимі написання"""
    # TODO: реалізувати
    pass

# ==================== CALLBACK ОБРОБНИКИ ====================

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    data = init_user(user_id)
    
    # Швидке додавання
    if query.data.startswith("quick_add:"):
        parts = query.data.split(":", 2)
        ukrainian, english = parts[1], parts[2]
        
        deck = data['active_deck']
        card = create_card(ukrainian, english, deck)
        data['decks'][deck]['cards'].append(card)
        save_user_data(user_id, data)
        
        await query.edit_message_text(f"✅ Додано: {ukrainian} → {english}")
    
    # Додати ще слово
    elif query.data == "add_another":
        context.user_data['adding_word'] = True
        context.user_data['word_step'] = 'ukrainian'
        await query.edit_message_text("➕ Напишіть слово українською:")
    
    # Почати вивчати
    elif query.data == "start_learning":
        await query.message.reply_text("🎯 Розпочинаємо навчання...")
        # Перенаправляємо на функцію навчання
        update_copy = update
        update_copy.message = query.message
        await start_learning(update_copy, context)
    
    # Режими навчання
    elif query.data == "learn_classic":
        context.user_data['learning_mode'] = 'classic'
        await show_learning_card(query, context, 'classic')
    
    elif query.data == "learn_quiz":
        context.user_data['learning_mode'] = 'quiz'
        await show_learning_card(query, context, 'quiz')
    
    # Показати відповідь (класичний режим)
    elif query.data == "show_card_answer":
        session = context.user_data.get('learning_session')
        if session:
            card_idx = session['cards'][session['current']]
            deck = session['deck']
            card = data['decks'][deck]['cards'][card_idx]
            
            keyboard = [
                [InlineKeyboardButton("😊 Легко", callback_data="rate_5")],
                [InlineKeyboardButton("👍 Добре", callback_data="rate_3")],
                [InlineKeyboardButton("🤔 Важко", callback_data="rate_1")],
                [InlineKeyboardButton("❌ Знову", callback_data="rate_0")]
            ]
            
            await query.edit_message_text(
                f"🇺🇦 {card['ukrainian']}\n"
                f"🇬🇧 **{card['english']}**\n\n"
                f"Як добре ви знаєте це слово?",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
    
    # Оцінка картки
    elif query.data.startswith("rate_"):
        quality = int(query.data.split("_")[1])
        session = context.user_data.get('learning_session')
        
        if session:
            card_idx = session['cards'][session['current']]
            deck = session['deck']
            
            # Оновлюємо картку за SM-2
            data['decks'][deck]['cards'][card_idx] = calculate_next_interval(
                data['decks'][deck]['cards'][card_idx],
                quality
            )
            
            # Оновлюємо статистику
            data['stats']['total_reviews'] += 1
            if quality >= 3:
                data['stats']['correct_reviews'] += 1
                session['correct'] = session.get('correct', 0) + 1
            
            save_user_data(user_id, data)
            
            # Наступна картка
            session['current'] += 1
            context.user_data['learning_session'] = session
            
            await show_learning_card(query, context, 'classic')
    
    # Відповідь у вікторині
    elif query.data.startswith("quiz_ans_"):
        answer = query.data.replace("quiz_ans_", "")
        correct = context.user_data.get('quiz_correct')
        session = context.user_data.get('learning_session')
        
        if session:
            card_idx = session['cards'][session['current']]
            deck = session['deck']
            
            is_correct = (answer == correct)
            quality = 4 if is_correct else 1
            
            # Оновлюємо картку
            data['decks'][deck]['cards'][card_idx] = calculate_next_interval(
                data['decks'][deck]['cards'][card_idx],
                quality
            )
            
            # Статистика
            data['stats']['total_reviews'] += 1
            if is_correct:
                data['stats']['correct_reviews'] += 1
                session['correct'] = session.get('correct', 0) + 1
            
            save_user_data(user_id, data)
            
            # Наступна
            session['current'] += 1
            context.user_data['learning_session'] = session
            
            await query.answer("✅ Правильно!" if is_correct else f"❌ Правильно: {correct}")
            await show_learning_card(query, context, 'quiz')
    
    # Статистика
    elif query.data == "show_stats":
        update_copy = update
        update_copy.message = query.message
        await show_statistics(update_copy, context)

# ==================== ГОЛОВНА ФУНКЦІЯ ====================

def main():
    init_database()
    
    TOKEN = os.getenv("TOKEN")
    application = Application.builder().token(TOKEN).build()
    
    # Команди
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    
    # Callback
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Повідомлення
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("🤖 Reword Bot запущено!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
