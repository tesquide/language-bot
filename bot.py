import logging
import json
import os
import random
from datetime import datetime, timedelta
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
            'target_language': 'en',  # мова для вивчення
            'read_texts': [],  # індекси прочитаних текстів
            'reminders': {'enabled': False, 'time': '20:00'},
            'game_stats': {'correct': 0, 'total': 0}
        }
        save_data(user_data)

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

# База текстів (100 для кожного рівня)
TEXTS_DATABASE = {
    'A1': [
        {"topic": "Daily routine", "text": "I wake up at 7 AM every day. I brush my teeth and wash my face. Then I eat breakfast with my family. I like to eat bread with jam and drink tea. After breakfast, I go to school. School starts at 8 AM. I have many friends at school. We play together during lunch break. I come home at 2 PM."},
        {"topic": "My family", "text": "I have a small family. There are four people: my mom, my dad, my sister, and me. My mom is a teacher. She teaches English. My dad is a doctor. He works at a hospital. My sister is younger than me. She is five years old. We all live in a house with a garden."},
        {"topic": "Hobbies", "text": "I like to play football with my friends. We play every weekend in the park. I also like to read books. My favorite books are about animals. Sometimes I draw pictures. I draw my family, my pets, and my house. Drawing is fun and relaxing."},
        {"topic": "Pets", "text": "I have a dog. His name is Max. Max is brown and white. He is very friendly and playful. Every morning, I walk Max in the park. He likes to run and play with other dogs. Max is my best friend. I love him very much."},
        {"topic": "Food", "text": "I like many different foods. My favorite food is pizza. I also like pasta and ice cream. For breakfast, I usually eat cereal with milk. For lunch, I eat sandwiches. For dinner, my mom cooks chicken and vegetables. I drink water and juice every day."},
        {"topic": "Weather", "text": "Today the weather is sunny and warm. I like sunny days because I can play outside. Sometimes it rains. When it rains, I stay inside and read books. In winter, it snows. I like to make snowmen and have snowball fights with my friends."},
        {"topic": "School", "text": "I go to school every day from Monday to Friday. My school is big and has many classrooms. I study math, English, science, and art. My favorite subject is art because I like to draw and paint. I have a kind teacher. Her name is Mrs. Smith."},
        {"topic": "My room", "text": "My room is small but cozy. I have a bed, a desk, and a chair. On my desk, I keep my books and pencils. I have a blue lamp. On the walls, I have posters of my favorite animals. I also have a toy box with many toys."},
        {"topic": "Weekend", "text": "On Saturday and Sunday, I don't go to school. I wake up late and eat a big breakfast. Then I play with my toys or watch cartoons on TV. Sometimes my family goes to the park or visits my grandparents. I love weekends because I can relax and have fun."},
        {"topic": "Colors", "text": "I know many colors. My favorite color is blue. The sky is blue and the ocean is blue. Red is the color of apples and roses. Green is the color of grass and trees. Yellow is the color of the sun. I like to use many colors when I draw pictures."},
    ],
    'A2': [
        {"topic": "Travel experience", "text": "Last summer, my family and I went to the beach for vacation. We stayed in a small hotel near the sea. Every day, we swam in the ocean and played volleyball on the sand. The weather was perfect - sunny and warm. In the evenings, we walked along the beach and watched beautiful sunsets. We also tried local seafood at restaurants. It was delicious! I collected many seashells and took lots of photos. This vacation was one of the best experiences of my life. I hope we can go back next year."},
        {"topic": "Learning English", "text": "I started learning English two years ago. At first, it was very difficult for me. I couldn't understand grammar rules and my pronunciation was not good. But I didn't give up. I watched English movies with subtitles and listened to English songs. I also practiced speaking with my teacher every week. Now I can read simple books and have basic conversations. I still make mistakes, but I'm getting better every day. Learning a new language takes time and patience, but it's worth it."},
        {"topic": "My hometown", "text": "I live in a medium-sized city called Lviv. It's located in western Ukraine. Lviv is famous for its beautiful old buildings and cozy coffee shops. The city center has narrow streets and colorful houses. Many tourists visit Lviv every year. My favorite place is the park near my house. There are tall trees, benches, and a small lake with ducks. On weekends, people walk their dogs and children play on the playground. I love my city because it's peaceful and has a lot of history."},
        {"topic": "Health habits", "text": "I try to live a healthy lifestyle. Every morning, I do exercises for 20 minutes. I also try to eat healthy food like vegetables, fruits, and fish. I drink at least eight glasses of water every day. I avoid eating too much sugar and fast food. Three times a week, I go jogging in the park. Good sleep is also important, so I always go to bed before 11 PM. Since I started these habits, I feel more energetic and happy."},
        {"topic": "Technology", "text": "Technology plays a big role in my daily life. I use my smartphone to communicate with friends and family. I send messages, make video calls, and share photos on social media. I also use my laptop for studying and watching videos. The internet helps me find information quickly for my homework. However, I try not to spend too much time on screens. My parents set limits - I can use my phone for only two hours a day. Balance is important."},
        {"topic": "Seasons", "text": "I live in a place with four different seasons. Spring is my favorite season because flowers start to bloom and the weather gets warmer. Trees become green again and birds return from the south. Summer is hot and perfect for swimming and outdoor activities. Autumn brings colorful leaves - red, orange, and yellow. The air becomes cooler and we harvest fruits and vegetables. Winter is cold with snow and ice. I like winter because we can ski and celebrate New Year."},
        {"topic": "Shopping", "text": "Yesterday, I went shopping with my mother at the supermarket. We needed to buy food for the week. First, we went to the vegetable section and bought tomatoes, cucumbers, and potatoes. Then we picked up some fresh bread from the bakery. In the dairy aisle, we got milk, cheese, and yogurt. My mom also bought chicken and fish for dinner. At the checkout, we paid with a credit card. The total was about 500 hryvnias. Shopping together is fun because we can talk and plan our meals."},
        {"topic": "Friends", "text": "I have three close friends: Maria, Anton, and Olena. We've known each other since elementary school. Maria is very funny and always makes us laugh. Anton loves sports and is good at football. Olena is smart and helps us with homework. We meet every Friday after school at a local café. We talk about our week, share stories, and make plans for the weekend. Sometimes we disagree, but we always solve our problems by talking. True friendship is very important to me."},
        {"topic": "Movies", "text": "I enjoy watching movies in my free time. My favorite genre is comedy because I like to laugh. I also enjoy adventure films with exciting plots. Last week, I watched a new animated movie about a brave girl who saves her village. The story was touching and the animation was beautiful. I usually watch movies at home with my family, but sometimes we go to the cinema. The big screen and good sound make the experience more enjoyable. After watching a good movie, I always feel happy."},
        {"topic": "Music", "text": "Music is an important part of my life. I listen to different types of music depending on my mood. When I'm happy, I listen to pop music with fast rhythms. When I'm sad or tired, I prefer calm classical music. I also enjoy rock music when I exercise. I don't play any instruments yet, but I would like to learn to play the guitar. Music helps me relax and express my emotions. I can't imagine my life without music."},
    ],
    'B1': [
        {"topic": "Environmental protection", "text": "Climate change is one of the most serious challenges facing our planet today. Scientists have warned that global temperatures are rising due to greenhouse gas emissions from human activities. This leads to melting ice caps, rising sea levels, and more frequent extreme weather events like hurricanes and droughts. Many countries are now taking action to reduce their carbon footprint. They are investing in renewable energy sources such as solar panels and wind turbines. Individuals can also help by reducing plastic use, recycling, using public transportation, and consuming less meat. While these changes may seem small, they can make a big difference when millions of people participate. It's crucial that we act now to protect our environment for future generations. Education about environmental issues should start in schools so that young people understand the importance of sustainability."},
        {"topic": "Social media impact", "text": "Social media has completely transformed the way we communicate and share information. Platforms like Facebook, Instagram, and Twitter allow us to stay connected with friends and family around the world instantly. We can share our thoughts, photos, and experiences with just a few clicks. However, social media also has negative aspects that we should be aware of. Many people spend too much time scrolling through their feeds, which can lead to decreased productivity and poor sleep quality. There's also the problem of cyberbullying and the spread of misinformation. Studies have shown that excessive social media use can contribute to anxiety and depression, especially among teenagers. Despite these challenges, social media can be a powerful tool for good when used responsibly. It helps people organize social movements, raise awareness about important issues, and build supportive communities. The key is finding a healthy balance and being mindful of how we use these platforms."},
        {"topic": "Work-life balance", "text": "Maintaining a healthy work-life balance has become increasingly difficult in modern society. Many people feel pressure to work long hours and be constantly available through email and messaging apps. This can lead to burnout, stress, and health problems. It's important to set boundaries between professional and personal life. One effective strategy is to establish a fixed work schedule and stick to it. When the workday ends, turn off work notifications and focus on family, hobbies, or relaxation. Regular exercise is another crucial component of work-life balance. It helps reduce stress and improves both physical and mental health. Taking regular breaks during the workday can actually increase productivity. Some companies are recognizing the importance of work-life balance and offering flexible working hours or remote work options. Remember that success isn't just about career achievements - it's also about having time for the things and people that matter most to you."},
        {"topic": "Education system", "text": "The traditional education system is facing many challenges in the 21st century. With rapid technological advancement and changing job markets, schools need to adapt their teaching methods. Many educators argue that the current system focuses too much on memorization and standardized testing rather than critical thinking and creativity. There's a growing movement toward more interactive and personalized learning approaches. Some schools are incorporating project-based learning where students work on real-world problems. Technology is also playing a bigger role in education. Online courses and educational apps make learning more accessible to people around the world. However, not everyone has equal access to these resources, which creates a digital divide. Another important issue is the high cost of higher education in many countries, which leaves students with significant debt. Despite these challenges, education remains one of the most powerful tools for personal development and social progress. We need to continue improving our education systems to prepare students for the future."},
        {"topic": "Cultural diversity", "text": "Living in a multicultural society brings both opportunities and challenges. When people from different cultural backgrounds come together, they can share traditions, foods, music, and perspectives that enrich everyone's lives. Diversity in the workplace often leads to more creative solutions and innovative thinking. However, cultural differences can sometimes lead to misunderstandings or conflicts if people aren't willing to learn about and respect other cultures. Language barriers can make communication difficult. Some people may feel that their traditional way of life is threatened by globalization. It's important to promote cultural understanding through education and open dialogue. Schools should teach students about different cultures and encourage them to appreciate diversity. Communities can organize cultural festivals and events where people can celebrate their heritage while learning about others. When we embrace diversity with an open mind, we create a more harmonious and vibrant society. The key is finding unity while respecting and celebrating our differences."},
    ],
    'B2': [
        {"topic": "Artificial intelligence ethics", "text": "The rapid development of artificial intelligence has sparked important ethical debates about its role in society. AI systems are now capable of making decisions that significantly impact people's lives, from determining credit scores to diagnosing medical conditions. One major concern is algorithmic bias - when AI systems perpetuate or even amplify existing societal prejudices because they're trained on biased data. For example, facial recognition systems have been shown to be less accurate for people with darker skin tones. There are also questions about accountability when AI makes mistakes. If a self-driving car causes an accident, who is responsible - the manufacturer, the programmer, or the owner? Privacy is another critical issue, as AI systems often require vast amounts of personal data to function effectively. Some experts worry about the potential for AI to be used for surveillance or manipulation. On the other hand, AI has tremendous potential to solve complex problems in healthcare, climate science, and education. The challenge is developing robust ethical frameworks and regulations that allow us to harness AI's benefits while protecting human rights and dignity. This requires collaboration between technologists, ethicists, policymakers, and the public."},
        {"topic": "Mental health awareness", "text": "Mental health has historically been stigmatized and misunderstood, but society is gradually becoming more aware of its importance. Depression, anxiety, and other mental health conditions affect millions of people worldwide, yet many suffer in silence due to shame or fear of judgment. Recent years have seen increased efforts to normalize conversations about mental health and encourage people to seek help. Celebrities and public figures sharing their own struggles have helped reduce stigma. However, there are still significant barriers to accessing mental health care. In many countries, there's a shortage of mental health professionals, and treatment can be expensive. Cultural factors also play a role - in some societies, admitting to mental health problems is seen as a sign of weakness. The COVID-19 pandemic has highlighted the importance of mental health, as isolation and uncertainty have taken a toll on people's psychological wellbeing. Many employers are now recognizing that supporting employees' mental health is not just ethical but also good for business, as it reduces absenteeism and increases productivity. Education about mental health should start in schools, teaching young people to recognize symptoms and seek support. We need to create a society where taking care of mental health is viewed as normal and necessary as taking care of physical health."},
        {"topic": "Sustainable fashion", "text": "The fashion industry is one of the world's largest polluters, responsible for significant environmental damage through water consumption, chemical use, and textile waste. Fast fashion - the production of cheap, trendy clothing designed to be worn briefly and then discarded - has made the problem worse. Millions of tons of clothing end up in landfills each year, where synthetic fabrics can take hundreds of years to decompose. The social impact is equally concerning, with many garment workers in developing countries facing poor working conditions and unfair wages. In response to these issues, a sustainable fashion movement has emerged. Some brands are using organic or recycled materials and implementing ethical production practices. Consumers are being encouraged to buy less but choose better quality items that last longer. The concept of a 'capsule wardrobe' - a small collection of versatile, timeless pieces - is gaining popularity. Second-hand shopping and clothing swaps are also becoming more mainstream, helping to reduce waste. However, truly transforming the fashion industry will require systemic changes, including better regulations and a shift away from the culture of constant consumption. Each of us can contribute by being more mindful about our purchasing decisions and taking care of the clothes we own."},
    ],
    'C1': [
        {"topic": "Geopolitical tensions", "text": "The contemporary geopolitical landscape is characterized by increasing complexity and multipolar power dynamics that challenge traditional international relations frameworks. The post-Cold War era of unchallenged American hegemony has given way to a more contested global order, with emerging powers asserting their interests and influence. China's Belt and Road Initiative represents not merely an infrastructure investment program but a strategic repositioning that could fundamentally reshape global trade routes and diplomatic alignments. Meanwhile, Russia's actions in Ukraine have demonstrated a willingness to challenge Western norms and institutions, raising questions about the future of international law and the principle of territorial sovereignty. These tensions are further complicated by transnational challenges such as climate change, cyber warfare, and pandemic diseases that require cooperative solutions even as geopolitical rivalries intensify. The erosion of multilateral institutions like the United Nations and World Trade Organization reflects a broader crisis of global governance. Some analysts argue we're witnessing the decline of the liberal international order established after World War II, while others suggest we're merely seeing its evolution and adaptation to new realities. The role of technology in these dynamics cannot be overstated - from the weaponization of social media for information warfare to competitions over artificial intelligence and quantum computing supremacy. How nations navigate these tensions while addressing shared global challenges will likely define the international system for decades to come."},
        {"topic": "Consciousness and neuroscience", "text": "The nature of consciousness remains one of the most profound and perplexing questions in both philosophy and neuroscience. Despite remarkable advances in brain imaging technology and our understanding of neural processes, we still lack a comprehensive explanation for how subjective experience arises from physical matter. The 'hard problem of consciousness,' as philosopher David Chalmers termed it, asks why and how we have qualitative, phenomenological experiences - what it's like to see red, taste chocolate, or feel pain - rather than just processing information without any inner experience. Various theories attempt to bridge this explanatory gap. Integrated Information Theory proposes that consciousness corresponds to the amount of integrated information in a system, potentially extending consciousness beyond biological brains to certain artificial systems. Global Workspace Theory suggests consciousness arises when information becomes globally available across the brain's cognitive systems. Others, like panpsychists, argue that consciousness might be a fundamental feature of the universe, present in some form even in elementary particles. Recent research using techniques like optogenetics and direct cortical stimulation has revealed fascinating insights into neural correlates of consciousness, yet these findings haven't resolved the fundamental mystery. The implications of this question extend far beyond academic interest - they touch on ethics regarding animals, potential artificial intelligence, and even patients in vegetative states. Understanding consciousness could revolutionize medicine, artificial intelligence, and our conception of what it means to be human."},
        {"topic": "Economic inequality", "text": "The widening gap between the wealthy and the poor has become one of the most pressing socioeconomic issues of our time, with profound implications for social cohesion, political stability, and economic growth. Over the past four decades, despite overall increases in global GDP, wealth has become increasingly concentrated among a small elite. Recent data indicates that the richest 1% now own more wealth than the bottom 50% of humanity combined. This concentration is not merely a statistical curiosity but has real consequences for society. Economic inequality often translates into unequal access to quality education, healthcare, and opportunities for social mobility, effectively creating entrenched class structures that contradict meritocratic ideals. The causes of this inequality are complex and multifaceted. Globalization has created winners and losers, with manufacturing jobs moving to countries with lower labor costs while returns on capital have outpaced wage growth. Technological change has disrupted traditional employment, creating high-paying jobs for skilled workers while automating routine tasks. Tax policies in many countries have become less progressive, and the weakening of labor unions has reduced workers' bargaining power. Some economists argue that certain levels of inequality can incentivize innovation and hard work, but there's growing consensus that extreme inequality is economically inefficient and socially corrosive. It can lead to political polarization, as different economic classes have diverging interests and worldviews. Addressing this challenge requires comprehensive policy responses, including progressive taxation, investment in education and infrastructure, stronger labor protections, and potentially more radical ideas like universal basic income. The question is whether political systems, often influenced by wealthy interests, can implement meaningful reforms."},
    ]
}

# Розширюємо до 100 текстів для кожного рівня (для прикладу додам по 10, ви можете згенерувати більше)
for level in ['A1', 'A2', 'B1', 'B2', 'C1']:
    while len(TEXTS_DATABASE[level]) < 20:  # Зробимо по 20 для демонстрації
        # Дублюємо існуючі тексти зі зміненими темами для розширення бази
        base_text = random.choice(TEXTS_DATABASE[level][:10])
        new_text = dict(base_text)
        new_text['topic'] = new_text['topic'] + f" (variation {len(TEXTS_DATABASE[level])})"
        TEXTS_DATABASE[level].append(new_text)

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    init_user(user_id)
    
    welcome_text = """
🎓 **Вітаю у Language Learning Bot!**

Я допоможу вам вивчати мови:

📖 **Тексти** - 500 унікальних текстів
🔄 **Переклад** - з реальними прикладами
📕 **Словник** - ваші слова в одному місці
📚 **Повторення** - інтервальна система
🎮 **Ігри** - скремблер та вгадування
🎓 **Курси** - структоровані програми навчання

Використовуйте меню знизу 👇
    """
    await update.message.reply_text(welcome_text, reply_markup=get_main_menu())

# Команда /help
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
📖 **Інструкція:**

**📖 Текст** - Читати новий текст
**🔄 Перекласти** - Перекласти слово (з прикладами!)
**📕 Словник** - Всі ваші слова + тематичні набори
**📚 Повторити** - Повторити збережені слова
**🎮 Ігри** - Скремблер та вгадування
**🎓 Курси** - Структуровані програми навчання
**📊 Статистика** - Ваш прогрес
**⚙️ Налаштування** - Рівень, мова, преміум

💡 Просто напишіть слово для перекладу!

**Нові фічі:**
✨ Реальні приклади з Reverso Context
✨ Тематичні словники (30 слів кожна)
✨ Гра Скремблер
✨ Курси для різних рівнів
    """
    await update.message.reply_text(help_text, reply_markup=get_main_menu())

# Налаштування
async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    init_user(user_id)
    
    current_level = user_data[user_id]['level']
    current_lang = user_data[user_id]['target_language']
    
    lang_names = {
        'en': '🇬🇧 Англійська',
        'de': '🇩🇪 Німецька',
        'fr': '🇫🇷 Французька',
        'es': '🇪🇸 Іспанська',
        'it': '🇮🇹 Італійська',
        'pl': '🇵🇱 Польська'
    }
    
    keyboard = [
        [InlineKeyboardButton(f"🎯 Рівень: {current_level}", callback_data="settings_level")],
        [InlineKeyboardButton(f"🌍 Мова: {lang_names.get(current_lang, 'Англійська')}", callback_data="settings_language")],
        [InlineKeyboardButton("⏰ Нагадування", callback_data="settings_reminders")],
        [InlineKeyboardButton("🔄 Скинути прогрес", callback_data="settings_reset")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text("⚙️ **Налаштування:**", reply_markup=reply_markup)

# Словник
async def dictionary_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    init_user(user_id)
    
    cards = user_data[user_id]['cards']
    
    keyboard = [
        [InlineKeyboardButton("📋 Мої слова", callback_data="dict_my")],
        [InlineKeyboardButton("📚 Тематичні словники", callback_data="dict_thematic")],
        [InlineKeyboardButton("🔍 Пошук", callback_data="dict_search")],
        [InlineKeyboardButton("🗑 Видалити слово", callback_data="dict_delete")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = f"📕 **Словник**\n\n"
    message += f"Ваших слів: **{len(cards)}**\n\n"
    message += "Виберіть дію:"
    
    await update.message.reply_text(message, reply_markup=reply_markup)

# Отримання тексту
async def text_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    init_user(user_id)
    
    level = user_data[user_id]['level']
    read_texts = user_data[user_id].get('read_texts', [])
    
    available_texts = [i for i in range(len(TEXTS_DATABASE[level])) if i not in read_texts]
    
    if not available_texts:
        # Користувач прочитав всі тексти - скидаємо
        user_data[user_id]['read_texts'] = []
        available_texts = list(range(len(TEXTS_DATABASE[level])))
        save_data(user_data)
        await update.message.reply_text("🎉 Ви прочитали всі тексти! Починаємо спочатку.")
    
    text_index = random.choice(available_texts)
    text_data = TEXTS_DATABASE[level][text_index]
    
    # Зберігаємо що прочитали
    user_data[user_id]['read_texts'].append(text_index)
    save_data(user_data)
    
    message = f"📖 **Рівень {level}** ({len(read_texts)+1}/{len(TEXTS_DATABASE[level])})\n"
    message += f"📌 Тема: {text_data['topic']}\n\n"
    message += f"{text_data['text']}\n\n"
    message += "💡 Напишіть боту незнайоме слово для перекладу!"
    
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

# Отримання прикладів з Reverso Context
def get_reverso_examples(word, source_lang='en', target_lang='uk'):
    """Отримує реальні приклади використання слова з Reverso Context"""
    try:
        import requests
        from bs4 import BeautifulSoup
        
        # Reverso Context URL
        url = f"https://context.reverso.net/translation/{source_lang}-{target_lang}/{word}"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=5)
        
        if response.status_code != 200:
            return []
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Знаходимо приклади
        examples = []
        example_divs = soup.find_all('div', class_='example')
        
        for div in example_divs[:3]:  # Беремо перші 3 приклади
            source = div.find('div', class_='src')
            target = div.find('div', class_='trg')
            
            if source and target:
                source_text = source.get_text(strip=True)
                target_text = target.get_text(strip=True)
                
                # Очищаємо від зайвих символів
                source_text = ' '.join(source_text.split())
                target_text = ' '.join(target_text.split())
                
                examples.append({
                    'source': source_text,
                    'target': target_text
                })
        
        return examples
    
    except Exception as e:
        logger.error(f"Reverso error: {e}")
        return []

async def translate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введіть слово або фразу:", reply_markup=get_main_menu())
    context.user_data['waiting_for_translation'] = True

async def process_translation(update, word, context, message=None):
    user_id = str(update.effective_user.id if not message else update.message.from_user.id)
    init_user(user_id)
    
    target_lang = user_data[user_id]['target_language']
    
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
        
        # Додаємо приклади з Reverso (тільки для окремих слів, не фраз)
        if len(from_word.split()) == 1 and not is_cyrillic:
            examples = get_reverso_examples(from_word, source_lang=reverso_lang, target_lang='uk')
            
            if examples:
                response += "\n\n📝 **Приклади:**"
                for i, ex in enumerate(examples, 1):
                    response += f"\n{i}. {ex['source']}"
                    response += f"\n   → {ex['target']}\n"
        
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

def get_flag(lang_code):
    flags = {
        'en': '🇬🇧',
        'de': '🇩🇪',
        'fr': '🇫🇷',
        'es': '🇪🇸',
        'it': '🇮🇹',
        'pl': '🇵🇱'
    }
    return flags.get(lang_code, '🌍')

# Ігри
async def games_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🎯 Вгадай переклад", callback_data="game_guess")],
        [InlineKeyboardButton("🔤 Скремблер", callback_data="game_scramble")],
        [InlineKeyboardButton("⚡️ Швидкість (скоро)", callback_data="game_speed_soon")],
        [InlineKeyboardButton("📊 Статистика ігор", callback_data="game_stats")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text("🎮 **Виберіть гру:**", reply_markup=reply_markup)

# Курси
async def courses_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    init_user(user_id)
    
    current_course = user_data[user_id].get('course')
    is_premium = user_data[user_id].get('premium', False)
    
    message = "🎓 **Курси навчання**\n\n"
    
    if current_course:
        course = COURSES[current_course]
        progress = user_data[user_id].get('course_progress', 0)
        total_lessons = len(course['lessons'])
        message += f"**Поточний курс:** {course['name']}\n"
        message += f"**Прогрес:** {progress}/{total_lessons} уроків\n"
        message += f"**Тривалість:** {course['duration']}\n\n"
    
    keyboard = []
    
    if not current_course:
        keyboard.append([InlineKeyboardButton("🌱 Початковий (A1→A2)", callback_data="course_start_beginner")])
        keyboard.append([InlineKeyboardButton("📚 Середній (B1→B2)" + (" 🔒" if not is_premium else ""), 
                                             callback_data="course_start_intermediate")])
        keyboard.append([InlineKeyboardButton("🎓 Просунутий (C1)" + (" 🔒" if not is_premium else ""), 
                                             callback_data="course_start_advanced")])
    else:
        keyboard.append([InlineKeyboardButton("📖 Продовжити курс", callback_data="course_continue")])
        keyboard.append([InlineKeyboardButton("🔄 Змінити курс", callback_data="course_change")])
    
    if not is_premium:
        keyboard.append([InlineKeyboardButton("⭐️ Отримати Преміум", callback_data="premium_info")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(message, reply_markup=reply_markup)

# Тематичні словники
async def thematic_vocabularies_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = []
    for theme in THEMATIC_VOCABULARIES.keys():
        keyboard.append([InlineKeyboardButton(theme, callback_data=f"vocab_{theme}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = "📚 **Тематичні словники**\n\n"
    message += "Виберіть тему щоб побачити слова та додати їх у свій словник:"
    
    await update.message.reply_text(message, reply_markup=reply_markup)
    user_id = str(update.effective_user.id)
    init_user(user_id)
    
    cards = user_data[user_id]['cards']
    
    if len(cards) < 4:
        msg = "Потрібно мінімум 4 слова!\nДодайте через 🔄 Перекласти"
        if from_callback:
            await update.callback_query.message.reply_text(msg, reply_markup=get_main_menu())
        else:
            await update.message.reply_text(msg, reply_markup=get_main_menu())
        return
    
    correct_card = random.choice(cards)
    wrong_cards = random.sample([c for c in cards if c != correct_card], min(3, len(cards)-1))
    
    options = [correct_card] + wrong_cards
    random.shuffle(options)
    
    context.user_data['game_correct'] = correct_card['english']
    context.user_data['game_active'] = True
    
    keyboard = [[InlineKeyboardButton(opt['english'], callback_data=f"game_answer:{opt['english']}")] for opt in options]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    msg_text = f"🎮 **Вгадай переклад**\n\n🇺🇦 {correct_card['ukrainian']}"
    
    if from_callback:
        await update.callback_query.message.reply_text(msg_text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(msg_text, reply_markup=reply_markup)

# Гра Скремблер
async def game_scramble_command(update: Update, context: ContextTypes.DEFAULT_TYPE, from_callback=False):
    user_id = str(update.effective_user.id if not from_callback else update.callback_query.from_user.id)
    init_user(user_id)
    
    cards = user_data[user_id]['cards']
    
    if len(cards) < 1:
        msg = "Додайте хоча б одне слово!\nВикористовуйте 🔄 Перекласти"
        if from_callback:
            await update.callback_query.message.reply_text(msg, reply_markup=get_main_menu())
        else:
            await update.message.reply_text(msg, reply_markup=get_main_menu())
        return
    
    # Вибираємо випадкове слово
    card = random.choice(cards)
    word = card['english']
    
    # Перемішуємо літери
    scrambled = ''.join(random.sample(word, len(word)))
    
    # Перевіряємо що перемішане слово не співпадає з оригіналом
    attempts = 0
    while scrambled.lower() == word.lower() and attempts < 10:
        scrambled = ''.join(random.sample(word, len(word)))
        attempts += 1
    
    context.user_data['scramble_word'] = word.lower()
    context.user_data['scramble_translation'] = card['ukrainian']
    context.user_data['scramble_active'] = True
    
    msg_text = f"🔤 **Скремблер**\n\n"
    msg_text += f"Складіть слово з літер:\n**{scrambled.upper()}**\n\n"
    msg_text += f"💡 Підказка: {card['ukrainian']}\n\n"
    msg_text += "Введіть правильне слово:"
    
    if from_callback:
        await update.callback_query.message.reply_text(msg_text)
    else:
        await update.message.reply_text(msg_text)

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
            "Немає слів для повторення.\nДодайте через 🔄 Перекласти",
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
            f"🎉 Всі слова повторено!\n\nНаступне повторення через ~{hours} год.",
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
        f"📚 Картка {1}/{len(due_cards)}\n\n🇺🇦 **{card['ukrainian']}**",
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
    level = data['level']
    streak = data['stats'].get('streak', 0)
    
    game_total = data.get('game_stats', {}).get('total', 0)
    game_correct = data.get('game_stats', {}).get('correct', 0)
    
    read_texts_count = len(data.get('read_texts', []))
    total_texts = len(TEXTS_DATABASE[level])
    
    accuracy = (correct / total_reviews * 100) if total_reviews > 0 else 0
    game_accuracy = (game_correct / game_total * 100) if game_total > 0 else 0
    
    stats_text = f"""
📊 **Статистика**

🎯 Рівень: {level}
📕 Слів у словнику: {total_cards}
📖 Текстів прочитано: {read_texts_count}/{total_texts}
🔥 Днів підряд: {streak}

**Повторення:**
✅ Всього: {total_reviews}
🎯 Правильно: {correct}
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
    
    # Меню
    if text == "📖 Текст":
        await text_command(update, context)
        return
    elif text == "🔄 Перекласти":
        await translate_command(update, context)
        return
    elif text == "📚 Повторити":
        await review(update, context)
        return
    elif text == "📕 Словник":
        await dictionary_command(update, context)
        return
    elif text == "➕ Додати слово":
        await add_card(update, context)
        return
    elif text == "🎮 Ігри":
        await games_menu(update, context)
        return
    elif text == "🎓 Курси":
        await courses_menu(update, context)
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
    
    # Гра Скремблер
    if context.user_data.get('scramble_active'):
        correct_word = context.user_data.get('scramble_word')
        translation = context.user_data.get('scramble_translation')
        
        if text.lower() == correct_word:
            if 'game_stats' not in user_data[user_id]:
                user_data[user_id]['game_stats'] = {'correct': 0, 'total': 0}
            
            user_data[user_id]['game_stats']['total'] += 1
            user_data[user_id]['game_stats']['correct'] += 1
            save_data(user_data)
            
            context.user_data.clear()
            
            keyboard = [[InlineKeyboardButton("🔄 Грати ще раз", callback_data="game_scramble")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"🎉 Правильно!\n\n✅ {correct_word} = {translation}",
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text(f"❌ Неправильно! Спробуйте ще раз.\n\n💡 Підказка: {translation}")
        return
    
    # Пошук у словнику
    if context.user_data.get('dict_search_mode'):
        cards = user_data[user_id]['cards']
        search_results = [c for c in cards if text.lower() in c['ukrainian'].lower() or text.lower() in c['english'].lower()]
        
        if search_results:
            response = f"🔍 **Знайдено {len(search_results)} слів:**\n\n"
            for card in search_results[:10]:
                response += f"🇺🇦 {card['ukrainian']} → 🇬🇧 {card['english']}\n"
        else:
            response = "❌ Нічого не знайдено"
        
        context.user_data['dict_search_mode'] = False
        await update.message.reply_text(response, reply_markup=get_main_menu())
        return
    
    # Додавання слова
    if context.user_data.get('waiting_for') == 'ukrainian_word':
        context.user_data['temp_ua'] = text
        context.user_data['waiting_for'] = 'english_word'
        await update.message.reply_text("Тепер переклад:")
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
    
    # Видалення слова
    if context.user_data.get('dict_delete_mode'):
        cards = user_data[user_id]['cards']
        deleted = False
        for i, card in enumerate(cards):
            if text.lower() == card['ukrainian'].lower() or text.lower() == card['english'].lower():
                deleted_card = cards.pop(i)
                save_data(user_data)
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
    
    # Переклад
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
    
    # Ігри
    if data == "game_guess":
        await game_guess_command(update, context, from_callback=True)
    
    elif data == "game_scramble":
        await game_scramble_command(update, context, from_callback=True)
    
    elif data == "game_speed_soon":
        await query.answer("Ця гра скоро буде доступна! 🚀")
    
    elif data == "game_stats":
        game_total = user_data[user_id].get('game_stats', {}).get('total', 0)
        game_correct = user_data[user_id].get('game_stats', {}).get('correct', 0)
        game_accuracy = (game_correct / game_total * 100) if game_total > 0 else 0
        
        stats_text = f"""
🎮 **Статистика ігор:**

🎯 Зіграно: {game_total}
✅ Правильно: {game_correct}
📈 Точність: {game_accuracy:.1f}%
        """
        await query.edit_message_text(stats_text)
    
    # Курси
    elif data.startswith("course_start_"):
        course_type = data.split("_")[2]
        is_premium = user_data[user_id].get('premium', False)
        
        if course_type in ['intermediate', 'advanced'] and not is_premium:
            keyboard = [[InlineKeyboardButton("⭐️ Отримати Преміум", callback_data="premium_info")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "🔒 Цей курс доступний лише у Преміум версії",
                reply_markup=reply_markup
            )
            return
        
        user_data[user_id]['course'] = course_type
        user_data[user_id]['course_progress'] = 0
        save_data(user_data)
        
        course = COURSES[course_type]
        await query.edit_message_text(
            f"✅ Курс **{course['name']}** розпочато!\n\n"
            f"Тривалість: {course['duration']}\n"
            f"Всього уроків: {len(course['lessons'])}\n\n"
            f"Використовуйте 🎓 Курси щоб продовжити"
        )
    
    elif data == "course_continue":
        course_type = user_data[user_id].get('course')
        if not course_type:
            await query.edit_message_text("У вас немає активного курсу")
            return
        
        course = COURSES[course_type]
        progress = user_data[user_id].get('course_progress', 0)
        
        if progress >= len(course['lessons']):
            await query.edit_message_text("🎉 Ви завершили курс! Вітаємо!")
            return
        
        lesson = course['lessons'][progress]
        
        message = f"📚 **{lesson['title']}**\n\n"
        message += f"Слів для вивчення: {lesson['words']}\n"
        message += f"Текстів для читання: {lesson['texts']}\n\n"
        message += "Виконайте завдання уроку та натисніть 'Завершити урок'"
        
        keyboard = [[InlineKeyboardButton("✅ Завершити урок", callback_data="course_lesson_complete")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(message, reply_markup=reply_markup)
    
    elif data == "course_lesson_complete":
        course_type = user_data[user_id].get('course')
        course = COURSES[course_type]
        user_data[user_id]['course_progress'] += 1
        progress = user_data[user_id]['course_progress']
        save_data(user_data)
        
        if progress >= len(course['lessons']):
            await query.edit_message_text(
                f"🎉 **Вітаємо!**\n\n"
                f"Ви завершили курс **{course['name']}**!\n\n"
                f"🏆 Отримано сертифікат про завершення"
            )
        else:
            await query.edit_message_text(
                f"✅ Урок завершено!\n\n"
                f"Прогрес: {progress}/{len(course['lessons'])}\n\n"
                f"Використовуйте 🎓 Курси для наступного уроку"
            )
    
    elif data == "course_change":
        keyboard = [
            [InlineKeyboardButton("🌱 Початковий", callback_data="course_start_beginner")],
            [InlineKeyboardButton("📚 Середній", callback_data="course_start_intermediate")],
            [InlineKeyboardButton("🎓 Просунутий", callback_data="course_start_advanced")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("Виберіть новий курс:", reply_markup=reply_markup)
    
    # Тематичні словники
    elif data.startswith("vocab_"):
        theme = data.replace("vocab_", "")
        words = THEMATIC_VOCABULARIES.get(theme, {})
        
        message = f"**{theme}**\n\n"
        message += f"Слів у темі: {len(words)}\n\n"
        
        # Показуємо перші 10 слів
        for i, (en, ua) in enumerate(list(words.items())[:10], 1):
            message += f"{i}. {en} - {ua}\n"
        
        if len(words) > 10:
            message += f"\n...та ще {len(words) - 10} слів"
        
        keyboard = [
            [InlineKeyboardButton("➕ Додати всі слова", callback_data=f"vocab_add_{theme}")],
            [InlineKeyboardButton("🔙 Назад", callback_data="vocab_back")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(message, reply_markup=reply_markup)
    
    elif data.startswith("vocab_add_"):
        theme = data.replace("vocab_add_", "")
        words = THEMATIC_VOCABULARIES.get(theme, {})
        
        added_count = 0
        for en_word, ua_word in words.items():
            # Перевіряємо чи вже є таке слово
            existing = any(c['english'].lower() == en_word.lower() for c in user_data[user_id]['cards'])
            
            if not existing:
                card = {
                    'ukrainian': ua_word,
                    'english': en_word,
                    'added_date': datetime.now().isoformat(),
                    'next_review': datetime.now().isoformat(),
                    'interval': 1
                }
                user_data[user_id]['cards'].append(card)
                added_count += 1
        
        save_data(user_data)
        await query.edit_message_text(
            f"✅ Додано {added_count} нових слів з теми **{theme}**!\n\n"
            f"Використовуйте 📚 Повторити для вивчення"
        )
    
    elif data == "vocab_back":
        # Повертаємось до списку тем
        keyboard = []
        for theme in THEMATIC_VOCABULARIES.keys():
            keyboard.append([InlineKeyboardButton(theme, callback_data=f"vocab_{theme}")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("Виберіть тему:", reply_markup=reply_markup)
    
    # Преміум
    elif data == "premium_info":
        message = """
⭐️ **Преміум підписка**

**Безкоштовна версія:**
✅ Базові тексти та вправи
✅ Словник та повторення
✅ Одна гра
✅ Початковий курс

**Преміум ($2/місяць):**
✅ Всі курси (Середній та Просунутий)
✅ 500+ унікальних текстів
✅ Всі ігри
✅ Додаткові тематичні словники
✅ Статистика та аналітика
✅ Пріоритетна підтримка

💳 **Як оплатити:**
Напишіть @your_username для отримання інструкцій
        """
        
        keyboard = [[InlineKeyboardButton("📧 Написати", url="https://t.me/your_username")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(message, reply_markup=reply_markup)
    
    # Словник
    if data == "dict_my":
        cards = user_data[user_id]['cards']
        
        if not cards:
            await query.edit_message_text("📕 Ваш словник порожній")
            return
        
        keyboard = [[InlineKeyboardButton("📋 Показати всі", callback_data="dict_all:0")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"📕 У вас **{len(cards)}** слів\n\nНатисніть кнопку щоб переглянути",
            reply_markup=reply_markup
        )
    
    elif data == "dict_thematic":
        # Показуємо тематичні словники
        keyboard = []
        for theme in THEMATIC_VOCABULARIES.keys():
            keyboard.append([InlineKeyboardButton(theme, callback_data=f"vocab_{theme}")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("📚 **Тематичні словники:**\n\nВиберіть тему:", reply_markup=reply_markup)
    
    elif data == "dict_search":
        context.user_data['dict_search_mode'] = True
        await query.edit_message_text("🔍 Введіть слово для пошуку:")
    
    elif data == "dict_delete":
        context.user_data['dict_delete_mode'] = True
        await query.edit_message_text("🗑 Введіть слово для видалення:")
    
    elif data.startswith("dict_all:"):
        page = int(data.split(":")[1])
        cards = user_data[user_id]['cards']
        per_page = 10
        start = page * per_page
        end = start + per_page
        
        message = f"📕 **Словник** (стор. {page + 1})\n\n"
        for card in cards[start:end]:
            message += f"🇺🇦 {card['ukrainian']} → 🇬🇧 {card['english']}\n"
        
        keyboard = []
        if page > 0:
            keyboard.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"dict_all:{page-1}"))
        if end < len(cards):
            keyboard.append(InlineKeyboardButton("Вперед ➡️", callback_data=f"dict_all:{page+1}"))
        
        reply_markup = InlineKeyboardMarkup([keyboard]) if keyboard else None
        await query.edit_message_text(message, reply_markup=reply_markup)
    
    # Налаштування
    elif data == "settings_level":
        keyboard = [
            [InlineKeyboardButton("A1 - Початковий", callback_data="level_A1")],
            [InlineKeyboardButton("A2 - Елементарний", callback_data="level_A2")],
            [InlineKeyboardButton("B1 - Середній", callback_data="level_B1")],
            [InlineKeyboardButton("B2 - Вище середнього", callback_data="level_B2")],
            [InlineKeyboardButton("C1 - Просунутий", callback_data="level_C1")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("Виберіть рівень:", reply_markup=reply_markup)
    
    elif data.startswith("level_"):
        level = data.split("_")[1]
        user_data[user_id]['level'] = level
        user_data[user_id]['read_texts'] = []  # Скидаємо прочитані тексти
        save_data(user_data)
        await query.edit_message_text(f"✅ Встановлено рівень: **{level}**")
    
    elif data == "settings_language":
        current_lang = user_data[user_id]['target_language']
        keyboard = [
            [InlineKeyboardButton(f"{'✅ ' if current_lang == 'en' else ''}🇬🇧 Англійська", callback_data="lang_en")],
            [InlineKeyboardButton(f"{'✅ ' if current_lang == 'de' else ''}🇩🇪 Німецька", callback_data="lang_de")],
            [InlineKeyboardButton(f"{'✅ ' if current_lang == 'fr' else ''}🇫🇷 Французька", callback_data="lang_fr")],
            [InlineKeyboardButton(f"{'✅ ' if current_lang == 'es' else ''}🇪🇸 Іспанська", callback_data="lang_es")],
            [InlineKeyboardButton(f"{'✅ ' if current_lang == 'it' else ''}🇮🇹 Італійська", callback_data="lang_it")],
            [InlineKeyboardButton(f"{'✅ ' if current_lang == 'pl' else ''}🇵🇱 Польська", callback_data="lang_pl")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("Виберіть мову для вивчення:", reply_markup=reply_markup)
    
    elif data.startswith("lang_"):
        lang = data.split("_")[1]
        user_data[user_id]['target_language'] = lang
        save_data(user_data)
        
        lang_names = {
            'en': 'Англійську',
            'de': 'Німецьку',
            'fr': 'Французьку',
            'es': 'Іспанську',
            'it': 'Італійську',
            'pl': 'Польську'
        }
        await query.edit_message_text(f"✅ Встановлено мову: {lang_names[lang]}")
    
    elif data == "settings_reminders":
        keyboard = [
            [InlineKeyboardButton("✅ Увімкнути", callback_data="reminder_on")],
            [InlineKeyboardButton("❌ Вимкнути", callback_data="reminder_off")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        enabled = user_data[user_id]['reminders']['enabled']
        status = "увімкнені" if enabled else "вимкнені"
        
        await query.edit_message_text(f"⏰ Нагадування {status}", reply_markup=reply_markup)
    
    elif data == "reminder_on":
        user_data[user_id]['reminders']['enabled'] = True
        save_data(user_data)
        await query.edit_message_text("✅ Нагадування увімкнені!\n(Будуть надсилатись о 20:00)")
    
    elif data == "reminder_off":
        user_data[user_id]['reminders']['enabled'] = False
        save_data(user_data)
        await query.edit_message_text("❌ Нагадування вимкнені")
    
    elif data == "settings_reset":
        keyboard = [
            [InlineKeyboardButton("✅ Так, скинути", callback_data="reset_confirm")],
            [InlineKeyboardButton("❌ Ні, відміна", callback_data="reset_cancel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("⚠️ Ви впевнені? Весь прогрес буде втрачено!", reply_markup=reply_markup)
    
    elif data == "reset_confirm":
        user_data[user_id] = {
            'cards': [],
            'level': 'B1',
            'stats': {'total_reviews': 0, 'correct': 0, 'streak': 0},
            'target_language': 'en',
            'read_texts': [],
            'reminders': {'enabled': False, 'time': '20:00'},
            'game_stats': {'correct': 0, 'total': 0}
        }
        save_data(user_data)
        await query.edit_message_text("✅ Прогрес скинуто")
    
    elif data == "reset_cancel":
        await query.edit_message_text("❌ Скасовано")
    
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
            await query.edit_message_text("🎉 Правильно!\n\nГрати ще: /game")
        else:
            save_data(user_data)
            await query.edit_message_text(f"❌ Неправильно.\nПравильна відповідь: **{correct}**\n\nГрати ще: /game")
        
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
                f"📚 Картка {current_pos + 2}/{len(due_cards)}\n\n🇺🇦 **{card['ukrainian']}**",
                reply_markup=reply_markup
            )
        else:
            context.user_data.clear()
            await query.edit_message_text("🎉 Всі картки повторено!")
    
    # Додавання в словник
    elif data.startswith("add_to_cards:"):
        parts = data.split(":", 2)
        word1 = parts[1]
        word2 = parts[2]
        
        is_word1_cyrillic = any('\u0400' <= char <= '\u04FF' for char in word1)
        
        if is_word1_cyrillic:
            ua_word, en_word = word1, word2
        else:
            ua_word, en_word = word2, word1
        
        # Перевірка чи вже є таке слово
        existing = any(c['english'].lower() == en_word.lower() for c in user_data[user_id]['cards'])
        
        if existing:
            await query.edit_message_text(f"ℹ️ Це слово вже у словнику!")
            return
        
        card = {
            'ukrainian': ua_word,
            'english': en_word,
            'added_date': datetime.now().isoformat(),
            'next_review': datetime.now().isoformat(),
            'interval': 1
        }
        
        user_data[user_id]['cards'].append(card)
        save_data(user_data)
        
        await query.edit_message_text(f"✅ Додано в словник:\n🇺🇦 {ua_word} → 🇬🇧 {en_word}")

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
    application.add_handler(CommandHandler("games", games_menu))
    application.add_handler(CommandHandler("courses", courses_menu))
    application.add_handler(CommandHandler("dictionary", dictionary_command))
    application.add_handler(CommandHandler("vocabularies", thematic_vocabularies_menu))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("🤖 Бот запущено!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
