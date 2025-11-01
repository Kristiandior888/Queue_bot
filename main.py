import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
from telegram.constants import ParseMode
from collections import deque
import json
import os

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Файл для хранения очереди
QUEUE_FILE = 'queue.json'

# Словарь для временного хранения фамилий
pending_surnames = {}


class StudentQueue:
    def __init__(self):
        self.queue = deque()
        self.load_queue()
        self.migrate_old_data()

    def add_student(self, user_id: int, username: str, first_name: str, surname: str = ""):
        """Добавление студента в очередь"""
        student = {
            'user_id': user_id,
            'username': username,
            'first_name': first_name,
            'surname': surname
        }

        # Проверяем, нет ли уже студента в очереди
        for existing_student in self.queue:
            if existing_student['user_id'] == user_id:
                return False

        self.queue.append(student)
        self.save_queue()
        return True

    def remove_student(self, user_id: int):
        """Удаление студента из очереди"""
        for i, student in enumerate(self.queue):
            if student['user_id'] == user_id:
                del self.queue[i]
                self.save_queue()
                return True
        return False

    def remove_first(self):
        """Удаление первого студента из очереди"""
        if self.queue:
            removed = self.queue.popleft()
            self.save_queue()
            return removed
        return None

    def get_queue(self):
        """Получение текущей очереди"""
        return list(self.queue)

    def get_position(self, user_id: int):
        """Получение позиции студента в очереди"""
        for i, student in enumerate(self.queue):
            if student['user_id'] == user_id:
                return i + 1
        return None

    def save_queue(self):
        """Сохранение очереди в файл"""
        with open(QUEUE_FILE, 'w', encoding='utf-8') as f:
            json.dump(list(self.queue), f, ensure_ascii=False, indent=2)

    def load_queue(self):
        """Загрузка очереди из файла"""
        if os.path.exists(QUEUE_FILE):
            try:
                with open(QUEUE_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.queue = deque(data)
            except (json.JSONDecodeError, Exception):
                self.queue = deque()

    def migrate_old_data(self):
        """Миграция старых данных - добавление поля surname если его нет"""
        migrated = False
        for student in self.queue:
            if 'surname' not in student:
                student['surname'] = ""
                migrated = True

        if migrated:
            self.save_queue()
            print("Мигрированы старые данные: добавлено поле surname")

    def add_pre_existing_students(self, students_list):
        """Добавление студентов, которые уже были в очереди до создания бота"""
        for student_data in students_list:
            # student_data должен быть словарем с полями: first_name, surname, username (опционально)
            student = {
                'user_id': None,  # У очных студентов нет user_id
                'username': student_data.get('username', student_data['first_name']),
                'first_name': student_data['first_name'],
                'surname': student_data['surname']
            }
            self.queue.append(student)
        self.save_queue()


# Создаем экземпляр очереди
student_queue = StudentQueue()


# Вспомогательная функция для получения отображаемого имени
def get_display_name(student):
    """Получение отображаемого имени студента"""
    surname = student.get('surname', '')
    first_name = student.get('first_name', '')
    username = student.get('username', '')

    if surname:
        return f"{surname} {first_name}"
    else:
        return f"{first_name} ({username})"


# Создаем меню команд
async def set_commands(application: Application):
    """Устанавливаем меню команд в интерфейсе бота"""
    commands = [
        ("start", "Запустить бота"),
        ("join", "Встать в очередь"),
        ("leave", "Покинуть очередь"),
        ("queue", "Показать очередь"),
        ("position", "Моя позиция"),
        ("next", "Следующий студент (для преподавателя)"),
        ("help", "Помощь и инструкция")
    ]
    await application.bot.set_my_commands(commands)


# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    welcome_text = f"""
Привет, {user.first_name}! 👋

<strong>Бот для управления очередью на сдачу лабораторных работ</strong>

📋 <strong>Доступные команды:</strong>

/join - Встать в очередь
/leave - Покинуть очередь  
/queue - Показать текущую очередь
/position - Узнать свою позицию
/next - Убрать первого студента (для преподавателя)
/help - Помощь по использованию

Используй меню команд слева от поля ввода сообщения ⬅️

<em>Или воспользуйся кнопками ниже для быстрого доступа:</em>
    """

    keyboard = [
        [InlineKeyboardButton("📝 Встать в очередь", callback_data="join")],
        [InlineKeyboardButton("❌ Покинуть очередь", callback_data="leave")],
        [InlineKeyboardButton("📋 Показать очередь", callback_data="queue")],
        [InlineKeyboardButton("🔍 Моя позиция", callback_data="position")],
        [InlineKeyboardButton("✅ Следующий студент", callback_data="next")],
        [InlineKeyboardButton("ℹ️ Помощь", callback_data="help")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)


# Команда /help
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
<strong>📖 Инструкция по использованию бота:</strong>

<strong>Для студентов:</strong>
✅ <strong>/join</strong> - записаться в очередь на сдачу
✅ <strong>/leave</strong> - выйти из очереди (если передумал)
✅ <strong>/queue</strong> - посмотреть всю очередь
✅ <strong>/position</strong> - узнать свою позицию

<strong>Для преподавателя:</strong>
👨‍🏫 <strong>/next</strong> - отметить, что текущий студент сдал работу и перейти к следующему

<strong>Как это работает:</strong>
1. Студент встает в очередь командой /join
2. Преподаватель вызывает студентов по порядку
3. Когда студент сдал, преподаватель использует /next
4. Следующий студент автоматически получает уведомление

<em>Используй меню команд или кнопки для удобства!</em>
    """

    keyboard = [
        [InlineKeyboardButton("📝 Встать в очередь", callback_data="join")],
        [InlineKeyboardButton("📋 Показать очередь", callback_data="queue")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(help_text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)


# Обработчик ввода фамилии
async def handle_surname_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    surname = update.message.text.strip()

    if user.id in pending_surnames:
        username = f"@{user.username}" if user.username else user.first_name

        if student_queue.add_student(user.id, username, user.first_name, surname):
            position = student_queue.get_position(user.id)
            total = len(student_queue.get_queue())

            success_text = f"""
✅ <strong>Ты успешно добавлен в очередь!</strong>

📊 <strong>Информация:</strong>
🎯 Твоя позиция: <strong>{position}</strong>
👥 Всего в очереди: <strong>{total}</strong>
📝 <strong>Фамилия:</strong> {surname}

<em>Используй /position чтобы проверить свою позицию
Или /queue чтобы посмотреть всю очередь</em>
            """

            keyboard = [
                [InlineKeyboardButton("📋 Посмотреть очередь", callback_data="queue")],
                [InlineKeyboardButton("🔍 Моя позиция", callback_data="position")],
                [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(success_text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

            # Удаляем пользователя из ожидающих ввод
            del pending_surnames[user.id]
        else:
            await update.message.reply_text(
                "❌ <strong>Ты уже в очереди!</strong>\nИспользуй /position чтобы узнать свою позицию",
                parse_mode=ParseMode.HTML)
            del pending_surnames[user.id]


# Команда встать в очередь
async def join_queue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    # Проверяем, не находится ли пользователь уже в очереди
    if student_queue.get_position(user.id):
        await update.message.reply_text(
            "❌ <strong>Ты уже в очереди!</strong>\nИспользуй /position чтобы узнать свою позицию",
            parse_mode=ParseMode.HTML)
        return

    # Добавляем пользователя в ожидание ввода фамилии
    pending_surnames[user.id] = True

    await update.message.reply_text(
        "📝 <strong>Пожалуйста, введи свою фамилию:</strong>\n\n"
        "<em>Это нужно для того, чтобы преподаватель мог идентифицировать тебя</em>",
        parse_mode=ParseMode.HTML
    )


# Команда покинуть очередь
async def leave_queue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if student_queue.remove_student(user.id):
        await update.message.reply_text("✅ <strong>Ты удален из очереди!</strong>", parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text("❌ <strong>Тебя нет в очереди!</strong>", parse_mode=ParseMode.HTML)


# Команда показать очередь
async def show_queue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    queue = student_queue.get_queue()

    if not queue:
        queue_text = "📝 <strong>Очередь пуста!</strong>\n\nИспользуй /join чтобы встать в очередь"

        keyboard = [
            [InlineKeyboardButton("📝 Встать в очередь", callback_data="join")],
            [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(queue_text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
        return

    queue_text = "📋 <strong>Текущая очередь:</strong>\n\n"
    for i, student in enumerate(queue, 1):
        display_name = get_display_name(student)
        queue_text += f"<strong>{i}.</strong> {display_name}\n"

    queue_text += f"\n👥 <strong>Всего в очереди:</strong> {len(queue)}"

    keyboard = [
        [InlineKeyboardButton("📝 Встать в очередь", callback_data="join")],
        [InlineKeyboardButton("🔍 Моя позиция", callback_data="position")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(queue_text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)


# Команда узнать свою позицию
async def get_position(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    position = student_queue.get_position(user.id)

    if position:
        total = len(student_queue.get_queue())
        student_data = None
        for student in student_queue.get_queue():
            if student['user_id'] == user.id:
                student_data = student
                break

        position_text = f"""
🔍 <strong>Информация о твоей позиции:</strong>

🎯 <strong>Твоя позиция:</strong> {position}
👥 <strong>Всего в очереди:</strong> {total}
"""
        if student_data and student_data.get('surname'):
            position_text += f"📝 <strong>Фамилия:</strong> {student_data['surname']}\n"

        position_text += "\n<em>Используй /queue чтобы посмотреть всю очередь</em>"

        keyboard = [
            [InlineKeyboardButton("📋 Посмотреть очередь", callback_data="queue")],
            [InlineKeyboardButton("❌ Покинуть очередь", callback_data="leave")],
            [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(position_text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(
            "❌ <strong>Тебя нет в очереди!</strong>\nИспользуй /join чтобы встать в очередь",
            parse_mode=ParseMode.HTML
        )


# Команда для перехода к следующему студенту
async def next_student(update: Update, context: ContextTypes.DEFAULT_TYPE):
    removed_student = student_queue.remove_first()

    if removed_student:
        queue = student_queue.get_queue()

        display_name = get_display_name(removed_student)

        next_text = f"""
✅ <strong>Студент удален из очереди!</strong>

📝 <strong>Удален:</strong> {display_name}
👥 <strong>Осталось в очереди:</strong> {len(queue)}
        """

        if queue:
            next_student = queue[0]
            next_display_name = get_display_name(next_student)
            next_text += f"\n🎯 <strong>Следующий:</strong> {next_display_name}"

            # Уведомляем следующего студента (только если у него есть user_id)
            if next_student.get('user_id'):
                await context.bot.send_message(
                    chat_id=next_student['user_id'],
                    text="🎯 <strong>Ты следующий в очереди! Подготовься к сдаче.</strong>",
                    parse_mode=ParseMode.HTML
                )

        keyboard = [
            [InlineKeyboardButton("📋 Показать очередь", callback_data="queue")],
            [InlineKeyboardButton("✅ Следующий", callback_data="next")],
            [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(next_text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text("❌ <strong>Очередь пуста!</strong>", parse_mode=ParseMode.HTML)


# Обработчик нажатий на кнопки
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = query.from_user

    if query.data == "join":
        # Проверяем, не находится ли пользователь уже в очереди
        if student_queue.get_position(user.id):
            await query.edit_message_text("❌ <strong>Ты уже в очереди!</strong>", parse_mode=ParseMode.HTML)
            return

        # Добавляем пользователя в ожидание ввода фамилии
        pending_surnames[user.id] = True

        await query.edit_message_text(
            "📝 <strong>Пожалуйста, введи свою фамилию:</strong>\n\n"
            "<em>Это нужно для того, чтобы преподаватель мог идентифицировать тебя</em>",
            parse_mode=ParseMode.HTML
        )

    elif query.data == "leave":
        if student_queue.remove_student(user.id):
            await query.edit_message_text("✅ <strong>Ты удален из очереди!</strong>", parse_mode=ParseMode.HTML)
        else:
            await query.edit_message_text("❌ <strong>Тебя нет в очереди!</strong>", parse_mode=ParseMode.HTML)

    elif query.data == "queue":
        queue = student_queue.get_queue()
        if not queue:
            queue_text = "📝 <strong>Очередь пуста!</strong>"

            keyboard = [
                [InlineKeyboardButton("📝 Встать в очередь", callback_data="join")],
                [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(queue_text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
            return

        queue_text = "📋 <strong>Текущая очередь:</strong>\n\n"
        for i, student in enumerate(queue, 1):
            display_name = get_display_name(student)
            queue_text += f"<strong>{i}.</strong> {display_name}\n"

        queue_text += f"\n👥 <strong>Всего в очереди:</strong> {len(queue)}"

        keyboard = [
            [InlineKeyboardButton("📝 Встать в очередь", callback_data="join")],
            [InlineKeyboardButton("🔍 Моя позиция", callback_data="position")],
            [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(queue_text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

    elif query.data == "position":
        position = student_queue.get_position(user.id)
        if position:
            total = len(student_queue.get_queue())
            student_data = None
            for student in student_queue.get_queue():
                if student['user_id'] == user.id:
                    student_data = student
                    break

            position_text = f"""
🔍 <strong>Информация о твоей позиции:</strong>

🎯 <strong>Твоя позиция:</strong> {position}
👥 <strong>Всего в очереди:</strong> {total}
"""
            if student_data and student_data.get('surname'):
                position_text += f"📝 <strong>Фамилия:</strong> {student_data['surname']}\n"

            keyboard = [
                [InlineKeyboardButton("📋 Посмотреть очередь", callback_data="queue")],
                [InlineKeyboardButton("❌ Покинуть очередь", callback_data="leave")],
                [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(position_text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
        else:
            await query.edit_message_text("❌ <strong>Тебя нет в очереди!</strong>", parse_mode=ParseMode.HTML)

    elif query.data == "next":
        removed_student = student_queue.remove_first()
        if removed_student:
            queue = student_queue.get_queue()

            display_name = get_display_name(removed_student)

            next_text = f"""
✅ <strong>Студент удален из очереди!</strong>

📝 <strong>Удален:</strong> {display_name}
👥 <strong>Осталось в очереди:</strong> {len(queue)}
            """

            if queue:
                next_student = queue[0]
                next_display_name = get_display_name(next_student)
                next_text += f"\n🎯 <strong>Следующий:</strong> {next_display_name}"

            keyboard = [
                [InlineKeyboardButton("📋 Показать очередь", callback_data="queue")],
                [InlineKeyboardButton("✅ Следующий", callback_data="next")],
                [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(next_text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
        else:
            await query.edit_message_text("❌ <strong>Очередь пуста!</strong>", parse_mode=ParseMode.HTML)

    elif query.data == "help":
        help_text = """
<strong>📖 Инструкция по использованию бота:</strong>

<strong>Для студентов:</strong>
✅ <strong>/join</strong> - записаться в очередь на сдачу
✅ <strong>/leave</strong> - выйти из очереди (если передумал)
✅ <strong>/queue</strong> - посмотреть всю очередь
✅ <strong>/position</strong> - узнать свою позицию

<strong>Для преподавателя:</strong>
👨‍🏫 <strong>/next</strong> - отметить, что текущий студент сдал работу
        """

        keyboard = [
            [InlineKeyboardButton("📝 Встать в очередь", callback_data="join")],
            [InlineKeyboardButton("📋 Показать очередь", callback_data="queue")],
            [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(help_text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

    elif query.data == "main_menu":
        welcome_text = f"""
<strong>Главное меню</strong>

Привет, {user.first_name}! 👋

Выбери действие:
        """

        keyboard = [
            [InlineKeyboardButton("📝 Встать в очередь", callback_data="join")],
            [InlineKeyboardButton("❌ Покинуть очередь", callback_data="leave")],
            [InlineKeyboardButton("📋 Показать очередь", callback_data="queue")],
            [InlineKeyboardButton("🔍 Моя позиция", callback_data="position")],
            [InlineKeyboardButton("✅ Следующий студент", callback_data="next")],
            [InlineKeyboardButton("ℹ️ Помощь", callback_data="help")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(welcome_text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)


# Функция для добавления очных студентов
def add_pre_existing_students():
    """Добавляет студентов, которые уже были в очереди до создания бота"""
    pre_existing_students = [
        {"first_name": "Иван", "surname": "Иванов"},
        {"first_name": "Петр", "surname": "Петров"},
        {"first_name": "Мария", "surname": "Сидорова"},
        # Добавь здесь студентов, которые уже были в очереди
        # Формат: {"first_name": "Имя", "surname": "Фамилия"}
    ]

    student_queue.add_pre_existing_students(pre_existing_students)
    print(f"Добавлено {len(pre_existing_students)} очных студентов в очередь")


# Главная функция
def main():
    # Получаем токен из переменных окружения
    TOKEN = os.getenv("BOT_TOKEN")
    
    if not TOKEN:
        print("❌ Ошибка: BOT_TOKEN не установлен!")
        return

    application = Application.builder().token(TOKEN).build()

    # Устанавливаем меню команд
    application.post_init = set_commands

    # Добавляем обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("join", join_queue))
    application.add_handler(CommandHandler("leave", leave_queue))
    application.add_handler(CommandHandler("queue", show_queue))
    application.add_handler(CommandHandler("position", get_position))
    application.add_handler(CommandHandler("next", next_student))

    # Добавляем обработчик текстовых сообщений (для ввода фамилии)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_surname_input))

    # Добавляем обработчик кнопок
    application.add_handler(CallbackQueryHandler(button_handler))

    # Запускаем бота
    print("🚀 Бот запущен на Railway...")
    
    try:
        application.run_polling()
    except Exception as e:
        print(f"❌ Ошибка при запуске бота: {e}")


if __name__ == '__main__':

    main()
