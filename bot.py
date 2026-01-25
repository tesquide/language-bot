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

# Тематичні словники (РОЗШИРЕНІ)
THEMATIC_VOCABULARIES = {
    '✈️ Подорожі': {
        'airport': 'аеропорт', 'flight': 'рейс', 'ticket': 'квиток', 'passport': 'паспорт',
        'luggage': 'багаж', 'hotel': 'готель', 'reservation': 'бронювання', 'tourist': 'турист',
        'guide': 'гід', 'map': 'карта', 'destination': 'пункт призначення', 'journey': 'подорож',
        'adventure': 'пригода', 'explore': 'досліджувати', 'vacation': 'відпустка', 'souvenir': 'сувенір',
        'beach': 'пляж', 'mountain': 'гора', 'city': 'місто', 'museum': 'музей',
        'restaurant': 'ресторан', 'taxi': 'таксі', 'train': 'поїзд', 'bus': 'автобус',
        'station': 'станція', 'arrival': 'прибуття', 'departure': 'відправлення', 'delay': 'затримка',
        'customs': 'митниця', 'visa': 'віза', 'border': 'кордон', 'backpack': 'рюкзак',
        'cruise': 'круїз', 'island': 'острів', 'sunset': 'захід сонця', 'harbor': 'гавань'
    },
    '🍔 Їжа': {
        'breakfast': 'сніданок', 'lunch': 'обід', 'dinner': 'вечеря', 'snack': 'перекус',
        'vegetable': 'овоч', 'fruit': 'фрукт', 'meat': 'м\'ясо', 'fish': 'риба',
        'bread': 'хліб', 'cheese': 'сир', 'milk': 'молоко', 'water': 'вода',
        'juice': 'сік', 'coffee': 'кава', 'tea': 'чай', 'sugar': 'цукор',
        'salt': 'сіль', 'pepper': 'перець', 'recipe': 'рецепт', 'dish': 'страва',
        'menu': 'меню', 'waiter': 'офіціант', 'bill': 'рахунок', 'delicious': 'смачний',
        'soup': 'суп', 'salad': 'салат', 'dessert': 'десерт', 'appetizer': 'закуска',
        'sauce': 'соус', 'spicy': 'гострий', 'sweet': 'солодкий', 'bitter': 'гіркий',
        'chicken': 'курка', 'beef': 'яловичина', 'pork': 'свинина', 'potato': 'картопля'
    },
    '💼 Бізнес': {
        'job': 'робота', 'career': 'кар\'єра', 'office': 'офіс', 'manager': 'менеджер',
        'employee': 'працівник', 'salary': 'зарплата', 'contract': 'контракт', 'meeting': 'зустріч',
        'project': 'проект', 'deadline': 'дедлайн', 'team': 'команда', 'colleague': 'колега',
        'boss': 'бос', 'client': 'клієнт', 'profit': 'прибуток', 'budget': 'бюджет',
        'invoice': 'рахунок-фактура', 'deal': 'угода', 'agreement': 'домовленість', 'presentation': 'презентація',
        'report': 'звіт', 'marketing': 'маркетинг', 'sales': 'продажі', 'revenue': 'дохід',
        'startup': 'стартап', 'investor': 'інвестор', 'partnership': 'партнерство', 'strategy': 'стратегія',
        'goal': 'ціль', 'success': 'успіх', 'failure': 'невдача', 'growth': 'зростання'
    },
    '🏥 Здоров\'я': {
        'doctor': 'лікар', 'hospital': 'лікарня', 'medicine': 'ліки', 'pain': 'біль',
        'headache': 'головний біль', 'fever': 'температура', 'cold': 'застуда', 'cough': 'кашель',
        'flu': 'грип', 'prescription': 'рецепт', 'pharmacy': 'аптека', 'treatment': 'лікування',
        'diagnosis': 'діагноз', 'symptom': 'симптом', 'exercise': 'вправа', 'diet': 'дієта',
        'vitamin': 'вітамін', 'injury': 'травма', 'surgery': 'операція', 'recovery': 'одужання',
        'patient': 'пацієнт', 'nurse': 'медсестра', 'clinic': 'клініка', 'emergency': 'екстрений випадок',
        'appointment': 'прийом', 'vaccine': 'вакцина', 'allergy': 'алергія', 'infection': 'інфекція',
        'bandage': 'бинт', 'pill': 'таблетка', 'healthy': 'здоровий', 'sick': 'хворий'
    },
    '🎓 Освіта': {
        'school': 'школа', 'university': 'університет', 'student': 'студент', 'teacher': 'вчитель',
        'lesson': 'урок', 'homework': 'домашнє завдання', 'exam': 'іспит', 'test': 'тест',
        'grade': 'оцінка', 'knowledge': 'знання', 'study': 'вивчати', 'learn': 'вчити',
        'book': 'книга', 'notebook': 'зошит', 'pen': 'ручка', 'pencil': 'олівець',
        'library': 'бібліотека', 'course': 'курс', 'subject': 'предмет', 'classroom': 'клас',
        'professor': 'професор', 'lecture': 'лекція', 'diploma': 'диплом', 'scholarship': 'стипендія',
        'assignment': 'завдання', 'research': 'дослідження', 'thesis': 'дисертація', 'campus': 'кампус',
        'semester': 'семестр', 'certificate': 'сертифікат', 'tuition': 'плата за навчання', 'major': 'спеціальність'
    },
    '💻 Технології': {
        'computer': 'комп\'ютер', 'internet': 'інтернет', 'website': 'вебсайт', 'email': 'електронна пошта',
        'password': 'пароль', 'software': 'програмне забезпечення', 'application': 'додаток', 'download': 'завантажити',
        'upload': 'вивантажити', 'file': 'файл', 'folder': 'папка', 'data': 'дані',
        'smartphone': 'смартфон', 'tablet': 'планшет', 'screen': 'екран', 'keyboard': 'клавіатура',
        'mouse': 'миша', 'printer': 'принтер', 'wifi': 'вайфай', 'network': 'мережа',
        'browser': 'браузер', 'search': 'пошук', 'cloud': 'хмара', 'backup': 'резервна копія',
        'update': 'оновлення', 'virus': 'вірус', 'security': 'безпека', 'coding': 'програмування',
        'algorithm': 'алгоритм', 'database': 'база даних', 'server': 'сервер', 'digital': 'цифровий'
    },
    '🏠 Дім': {
        'house': 'будинок', 'room': 'кімната', 'kitchen': 'кухня', 'bathroom': 'ванна',
        'bedroom': 'спальня', 'living room': 'вітальня', 'furniture': 'меблі', 'table': 'стіл',
        'chair': 'стілець', 'bed': 'ліжко', 'sofa': 'диван', 'window': 'вікно',
        'door': 'двері', 'floor': 'підлога', 'ceiling': 'стеля', 'wall': 'стіна',
        'lamp': 'лампа', 'curtain': 'штора', 'carpet': 'килим', 'mirror': 'дзеркало',
        'closet': 'шафа', 'drawer': 'ящик', 'shelf': 'полиця', 'pillow': 'подушка',
        'blanket': 'ковдра', 'towel': 'рушник', 'shower': 'душ', 'sink': 'раковина',
        'stove': 'плита', 'refrigerator': 'холодильник', 'garden': 'сад', 'garage': 'гараж'
    },
    '👔 Одяг': {
        'clothes': 'одяг', 'shirt': 'сорочка', 'pants': 'штани', 'dress': 'сукня',
        'skirt': 'спідниця', 'jacket': 'куртка', 'coat': 'пальто', 'shoes': 'взуття',
        'boots': 'чоботи', 'sneakers': 'кросівки', 'hat': 'капелюх', 'cap': 'кепка',
        'scarf': 'шарф', 'gloves': 'рукавички', 'socks': 'шкарпетки', 'belt': 'пояс',
        'tie': 'краватка', 'sweater': 'светр', 'jeans': 'джинси', 't-shirt': 'футболка',
        'suit': 'костюм', 'blouse': 'блузка', 'underwear': 'білизна', 'pajamas': 'піжама',
        'uniform': 'уніформа', 'hoodie': 'худі', 'vest': 'жилет', 'shorts': 'шорти',
        'sandals': 'сандалі', 'slippers': 'тапочки', 'raincoat': 'дощовик', 'swimsuit': 'купальник'
    }
}

# База текстів (РОЗШИРЕНА)
TEXTS_DATABASE = {
    'A1': [
        {"topic": "Daily routine", "text": "I wake up at 7 AM every day. I brush my teeth and wash my face. Then I eat breakfast with my family. I like to eat bread with jam and drink tea. After breakfast, I go to school."},
        {"topic": "My family", "text": "I have a small family. There are four people: my mom, my dad, my sister, and me. My mom is a teacher. My dad is a doctor. My sister is five years old. We love each other."},
        {"topic": "My pet", "text": "I have a cat. Her name is Lucy. She is white and very soft. Lucy likes to play with a ball. She sleeps on my bed. I feed her every morning and evening."},
        {"topic": "My room", "text": "My room is small but cozy. I have a bed, a desk, and a chair. On my desk, I have books and pencils. I have a lamp too. My room has one window."},
        {"topic": "Weekend", "text": "On Saturday and Sunday, I don't go to school. I wake up late. I play with my friends in the park. We ride bikes and play football. I like weekends very much."},
        {"topic": "School", "text": "I go to school every day. My school is big. I have many friends there. We study math, English, and science. My favorite subject is English. I like my teacher."},
        {"topic": "Food", "text": "I like pizza and ice cream. For breakfast, I eat cereal and milk. For lunch, I have a sandwich. For dinner, my mom cooks soup and chicken. I drink juice every day."},
        {"topic": "Colors", "text": "My favorite color is blue. The sky is blue. The ocean is blue too. I also like red and green. Red is the color of apples. Green is the color of grass and trees."},
        {"topic": "Weather", "text": "Today is sunny. The sun is shining. I like sunny days. Sometimes it rains. When it rains, I stay home. In winter, it snows. I like to make snowmen."},
        {"topic": "My friend", "text": "My best friend is Tom. He is ten years old like me. We go to the same school. Tom likes football. We play together every day after school. He is very funny."},
    ],
    'A2': [
        {"topic": "Travel", "text": "Last summer, my family went to the beach. We stayed in a hotel near the ocean. Every day we swam in the sea and played on the sand. The weather was perfect. In the evening, we ate fresh fish at restaurants. I collected many beautiful shells. It was the best vacation ever. I want to go back next year."},
        {"topic": "Hobby", "text": "I love reading books. Every week, I go to the library and borrow new books. My favorite books are adventure stories. Reading helps me learn new words and understand different cultures. Sometimes I read before bed. My parents are happy that I like reading. They buy me books for my birthday."},
        {"topic": "Shopping", "text": "Yesterday, I went shopping with my mother. We went to the supermarket to buy food for the week. We bought vegetables, fruits, meat, and bread. My mother also bought milk and eggs. I chose some cookies for myself. At the checkout, we paid with a credit card. Shopping took us two hours."},
        {"topic": "Technology", "text": "I use my smartphone every day. I send messages to my friends and watch videos online. Sometimes I play games on my phone. My parents say I should not use it too much. They allow me to use it for one hour after homework. I also use my computer for school projects."},
        {"topic": "Health", "text": "It is important to stay healthy. I try to eat fruits and vegetables every day. I also drink a lot of water. Three times a week, I play sports with my friends. I go to bed early to get enough sleep. When I feel sick, I visit the doctor. Being healthy makes me happy."},
        {"topic": "Learning English", "text": "I have been learning English for two years. At first, it was difficult to remember new words. But now I can understand simple conversations. I practice English by watching movies with subtitles. My teacher is very patient and helpful. I want to speak English fluently one day."},
        {"topic": "City life", "text": "I live in a big city. There are many tall buildings and busy streets. Every day I see lots of cars and buses. My city has beautiful parks where people walk and relax. There are also many shops and restaurants. Sometimes the city is noisy, but I like living here because there are many things to do."},
        {"topic": "Birthday party", "text": "Last week was my birthday. My parents organized a party for me. They invited all my friends. We played games and ate cake. My friends gave me many presents. I got books, toys, and clothes. We had pizza and juice. It was a wonderful day. I thanked everyone for coming."},
        {"topic": "Future plans", "text": "When I finish school, I want to go to university. I plan to study medicine because I want to be a doctor. Doctors help sick people and save lives. I know it will be difficult, but I will work hard. My parents support my dream. I hope to achieve my goal."},
        {"topic": "Environment", "text": "We should protect our environment. I try to recycle paper and plastic. I don't throw trash on the street. I use a reusable water bottle instead of buying plastic bottles. Saving water and electricity is important too. If everyone helps a little, we can make the Earth cleaner and healthier."},
    ],
    'B1': [
        {"topic": "Climate change", "text": "Climate change is one of the most pressing issues facing our planet today. Scientists warn that rising temperatures are causing polar ice caps to melt, leading to rising sea levels. Extreme weather events like hurricanes and droughts are becoming more frequent. Many countries are trying to reduce carbon emissions by using renewable energy sources such as solar and wind power. Individuals can also help by using public transportation, reducing plastic consumption, and recycling. While progress has been made, much more needs to be done to protect our environment for future generations."},
        {"topic": "Social media", "text": "Social media has changed the way we communicate and share information. Platforms like Facebook and Instagram allow us to stay connected with friends and family around the world. However, spending too much time on social media can have negative effects. It can lead to anxiety, sleep problems, and reduced face-to-face interaction. Many people compare their lives to others online, which can cause unhappiness. It's important to use social media responsibly and take regular breaks. Finding a balance between online and offline life is essential for our mental health."},
        {"topic": "Remote work", "text": "Working from home has become increasingly popular, especially after the pandemic. Many people appreciate the flexibility and time saved from not commuting. Remote work allows for a better work-life balance. However, it also has challenges. Some people feel isolated and miss the social interaction of an office. It can be difficult to separate work from personal life when both happen in the same space. Companies are now looking for ways to support remote workers better, including providing equipment and encouraging regular breaks."},
        {"topic": "Healthy lifestyle", "text": "Maintaining a healthy lifestyle requires effort and dedication. Regular exercise is crucial - experts recommend at least 30 minutes of physical activity five days a week. Eating a balanced diet with plenty of fruits and vegetables provides essential nutrients. Getting seven to eight hours of sleep each night helps the body recover and function properly. Managing stress through meditation or hobbies is equally important. Avoiding smoking and limiting alcohol consumption also contribute to better health. Small changes in daily habits can lead to significant improvements over time."},
        {"topic": "Online shopping", "text": "Online shopping has revolutionized the way we buy products. With just a few clicks, we can order almost anything and have it delivered to our door. This convenience saves time and often money, as online stores frequently offer discounts. However, there are disadvantages too. We cannot physically examine products before buying, and returning items can be complicated. There are also concerns about data security and online fraud. Despite these issues, e-commerce continues to grow rapidly, and traditional stores are adapting by creating their own online platforms."},
    ],
    'B2': [
        {"topic": "Artificial intelligence", "text": "Artificial intelligence is rapidly transforming various aspects of our lives. From virtual assistants on our smartphones to complex algorithms that drive autonomous vehicles, AI is becoming increasingly integrated into modern society. In healthcare, AI systems can analyze medical images and help doctors diagnose diseases more accurately. In finance, algorithms detect fraudulent transactions and make investment decisions. However, this technological advancement raises important ethical questions. There are concerns about job displacement as automation replaces human workers. Privacy issues arise when AI systems collect and analyze personal data. Bias in AI algorithms can perpetuate existing societal prejudices. As we develop more sophisticated AI systems, we must carefully consider their implications and establish appropriate regulations to ensure they benefit humanity as a whole."},
        {"topic": "Education reform", "text": "The traditional education system is facing significant challenges in the 21st century. Many educators argue that schools focus too heavily on standardized testing rather than fostering critical thinking and creativity. The rapid pace of technological change means that students need to develop adaptable skills rather than just memorizing facts. Some schools are experimenting with project-based learning, where students work on real-world problems and develop practical solutions. There's also growing interest in personalized learning approaches that cater to individual student needs and learning styles. However, implementing these changes is difficult. Teachers need training and support to adopt new methods. Not all schools have access to necessary technology and resources. Despite these obstacles, there's widespread agreement that education must evolve to prepare students for an uncertain future where the jobs they'll have may not even exist yet."},
        {"topic": "Globalization", "text": "Globalization has fundamentally altered how businesses operate and how cultures interact. International trade has created unprecedented economic opportunities, allowing companies to source materials globally and reach customers worldwide. This has lifted millions out of poverty, particularly in developing countries. However, globalization also has its critics. Local industries struggle to compete with multinational corporations. Cultural homogenization threatens to erode unique traditions and languages. Environmental degradation has accelerated as companies seek the cheapest production methods regardless of ecological cost. The COVID-19 pandemic highlighted vulnerabilities in global supply chains, prompting discussions about the need for more localized production. As we move forward, the challenge is finding a balance between the benefits of global cooperation and the need to preserve local communities and protect the environment."},
    ],
    'C1': [
        {"topic": "Philosophy", "text": "The philosophical debate surrounding free will versus determinism has captivated thinkers for centuries. On one hand, our subjective experience suggests that we make genuine choices and bear moral responsibility for our actions. We deliberate, weigh options, and ultimately decide based on our values and reasoning. On the other hand, advances in neuroscience reveal that many of our decisions may be predetermined by factors beyond our conscious control, including genetics, upbringing, and environmental influences. Brain imaging studies show that neural activity precedes conscious awareness of decisions, suggesting that our sense of choice might be an illusion. This paradox has profound implications not only for how we understand human behavior but also for our legal and ethical frameworks. If our actions are determined, can we truly be held responsible for them? Some contemporary philosophers argue for compatibilism, suggesting that free will and determinism need not be mutually exclusive concepts. They propose that freedom consists not in being undetermined, but in acting in accordance with one's own desires and rational deliberation, even if those desires themselves are causally determined. This nuanced view attempts to preserve moral responsibility while acknowledging the causal nature of the universe."},
    ]
}

# Курси
async def courses_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🌱 Початковий курс", callback_data="course_beginner")],
        [InlineKeyboardButton("📚 Інформація про курси", callback_data="course_info")]
    ]
    await update.message.reply_text("🎓 **Курси:**", reply_markup=InlineKeyboardMarkup(keyboard))

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
        reverso_lang = 'uk'
    else:
        translation = translate_word(word, from_lang=target_lang, to_lang='uk')
        from_word, to_word = word, translation
        from_flag, to_flag = get_flag(target_lang), "🇺🇦"
        reverso_lang = target_lang
    
    if translation:
        response = f"{from_flag} **{from_word}**\n{to_flag} **{to_word}**"
        
        # Додаємо приклади ТІЛЬКИ для англійських слів (не фраз)
        if len(from_word.split()) == 1 and not is_cyrillic and target_lang == 'en':
            try:
                examples = get_reverso_examples(from_word, source_lang='en', target_lang='uk')
                if examples and len(examples) > 0:
                    response += "\n\n📝 **Приклади:**"
                    for i, ex in enumerate(examples[:3], 1):
                        response += f"\n{i}. {ex['source']}"
                        response += f"\n   → {ex['target']}\n"
            except Exception as e:
                logger.error(f"Reverso examples failed: {e}")
                # Продовжуємо без прикладів якщо Reverso не спрацював
        
        keyboard = [[InlineKeyboardButton("➕ Додати в словник", callback_data=f"add_to_cards:{from_word}:{to_word}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if message:
            await message.reply_text(response, reply_markup=reply_markup)
        else:
            await update.callback_query.message.reply_text(response, reply_markup=reply_markup)
    else:
        error_msg = f"❌ Не вдалося перекласти '{word}'"
        if message:
            await message.reply_text(error_msg, reply_markup=get_main_menu())
        else:
            await update.callback_query.message.reply_text(error_msg)

# Словник
async def dictionary_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    data = init_user(user_id)
    
    keyboard = [
        [InlineKeyboardButton("📋 Мої слова", callback_data="dict_my")],
        [InlineKeyboardButton("📚 Тематичні", callback_data="dict_thematic")],
        [InlineKeyboardButton("🗑 Видалити слово", callback_data="dict_delete")]
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
    elif text == "🎓 Курси":
        await courses_menu(update, context)
    elif text == "📊 Статистика":
        await stats(update, context)
    elif text == "⚙️ Налаштування":
        await settings_command(update, context)
    elif text == "❓ Допомога":
        await help_command(update, context)
    # Видалення зі словника
    elif context.user_data.get('dict_delete_mode'):
        data = init_user(user_id)
        deleted = False
        
        # Перевірка чи це номер
        try:
            num = int(text) - 1
            if 0 <= num < len(data['cards']):
                deleted_card = data['cards'].pop(num)
                save_user_data(user_id, data)
                deleted = True
                await update.message.reply_text(
                    f"🗑 Видалено: {deleted_card['ukrainian']} → {deleted_card['english']}",
                    reply_markup=get_main_menu()
                )
        except ValueError:
            # Це не номер, шукаємо по назві
            for i, card in enumerate(data['cards']):
                if text.lower() in card['ukrainian'].lower() or text.lower() in card['english'].lower():
                    deleted_card = data['cards'].pop(i)
                    save_user_data(user_id, data)
                    deleted = True
                    await update.message.reply_text(
                        f"🗑 Видалено: {deleted_card['ukrainian']} → {deleted_card['english']}",
                        reply_markup=get_main_menu()
                    )
                    break
        
        if not deleted:
            await update.message.reply_text("❌ Слово не знайдено", reply_markup=get_main_menu())
        
        context.user_data['dict_delete_mode'] = False
        return
    # Скремблер
    elif context.user_data.get('scramble_word'):
        data = init_user(user_id)
        if text.lower() == context.user_data['scramble_word']:
            data['game_stats']['total'] += 1
            data['game_stats']['correct'] += 1
            save_user_data(user_id, data)
            context.user_data.clear()
            
            keyboard = [[InlineKeyboardButton("🔄 Грати ще", callback_data="game_scramble")]]
            await update.message.reply_text("🎉 Правильно!", reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await update.message.reply_text("❌ Спробуйте ще раз")
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
    
    # Курси
    elif query.data == "course_beginner":
        await query.edit_message_text(
            "🌱 **Початковий курс**\n\n"
            "Цей курс допоможе вам вивчити базову англійську.\n\n"
            "📚 10 уроків\n⏱ 3 місяці\n📝 225 слів\n\n"
            "Почніть з основ і поступово прогресуйте!"
        )
    elif query.data == "course_info":
        await query.edit_message_text(
            "📚 **Інформація про курси**\n\n"
            "Наші курси структуровані для послідовного навчання.\n\n"
            "🌱 Початковий (A1→A2)\n"
            "📘 Середній (B1→B2)\n"
            "🎓 Просунутий (C1)\n\n"
            "Кожен курс містить тексти, слова та вправи."
        )
    
    # Словник
    elif query.data == "dict_my":
        if data['cards']:
            msg = "📕 **Ваші слова:**\n\n"
            for c in data['cards'][:10]:
                msg += f"🇺🇦 {c['ukrainian']} → 🇬🇧 {c['english']}\n"
            
            if len(data['cards']) > 10:
                msg += f"\n...та ще {len(data['cards']) - 10} слів"
            
            await query.edit_message_text(msg)
        else:
            await query.edit_message_text("Словник порожній")
    
    elif query.data == "dict_delete":
        if data['cards']:
            msg = "🗑 **Видалити слово**\n\nВаші слова:\n\n"
            for i, c in enumerate(data['cards'][:15], 1):
                msg += f"{i}. {c['english']} - {c['ukrainian']}\n"
            
            msg += "\n💡 Напишіть номер або назву слова для видалення"
            context.user_data['dict_delete_mode'] = True
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
    application.add_handler(CommandHandler("courses", courses_menu))
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
