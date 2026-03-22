import asyncio
import logging
import sqlite3
import os
import subprocess
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandObject
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# Bot configuration
TOKEN = "8690938829:AAFNQriBsEJwFUjwzzpLpADrNt51wMyWAHA"
CHANNEL_ID = -1003783009565
OWNER_ID = 7666967863
REFERRAL_POINTS = 70

# Plans
PLANS = {
    "daily": {"name": "يومي", "points": 50, "days": 1},
    "weekly": {"name": "أسبوعي", "points": 500, "days": 7},
    "monthly": {"name": "شهري", "points": 1250, "days": 30}
}

# States
class HostingStates(StatesGroup):
    waiting_for_token = State()
    waiting_for_code = State()

# Database helper functions
DB_PATH = "bot_database.db"
HOSTED_DIR = "hosted_bots"

if not os.path.exists(HOSTED_DIR):
    os.makedirs(HOSTED_DIR)

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        points INTEGER DEFAULT 0,
        referrer_id INTEGER,
        is_admin BOOLEAN DEFAULT 0,
        joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS subscriptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        bot_token TEXT,
        plan_type TEXT,
        start_date TIMESTAMP,
        end_date TIMESTAMP,
        status TEXT DEFAULT 'active'
    )
    ''')
    conn.commit()
    conn.close()

def execute_query(query, params=(), fetchone=False, fetchall=False):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(query, params)
    result = None
    if fetchone:
        result = cursor.fetchone()
    elif fetchall:
        result = cursor.fetchall()
    conn.commit()
    conn.close()
    return result

# Bot and Dispatcher
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Active processes tracking
active_processes = {}

# Middleware for channel check
async def check_channel_join(user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception:
        return False

# Keyboards
def main_menu_kb(user_id: int):
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🚀 تشغيل استضافة جديدة", callback_data="host_bot"))
    builder.row(InlineKeyboardButton(text="💳 اشتراكاتي", callback_data="my_subs"), 
                InlineKeyboardButton(text="💰 رصيدي", callback_data="my_points"))
    builder.row(InlineKeyboardButton(text="🔗 دعوة الأصدقاء", callback_data="ref_link"))
    
    if user_id == OWNER_ID:
        builder.row(InlineKeyboardButton(text="📊 الإحصائيات (للمطور)", callback_data="stats"))
        
    builder.row(InlineKeyboardButton(text="🛠️ الدعم الفني", url="https://t.me/7666967863"))
    return builder.as_markup()

def plans_kb():
    builder = InlineKeyboardBuilder()
    for key, plan in PLANS.items():
        builder.row(InlineKeyboardButton(text=f"🔹 {plan['name']} - {plan['points']} نقطة", callback_data=f"buy_{key}"))
    builder.row(InlineKeyboardButton(text="🔙 عودة", callback_data="main_menu"))
    return builder.as_markup()

# Handlers
@dp.message(Command("start"))
async def start_cmd(message: Message, command: CommandObject, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    
    user = execute_query("SELECT * FROM users WHERE user_id = ?", (user_id,), fetchone=True)
    
    if not user:
        referrer_id = None
        if command.args and command.args.isdigit():
            ref_id = int(command.args)
            if ref_id != user_id:
                referrer_id = ref_id
                execute_query("UPDATE users SET points = points + ? WHERE user_id = ?", (REFERRAL_POINTS, referrer_id))
                try:
                    await bot.send_message(referrer_id, f"🎉 لقد انضم مستخدم جديد من خلال رابطك! حصلت على {REFERRAL_POINTS} نقطة.")
                except: pass
        
        execute_query("INSERT INTO users (user_id, username, points, referrer_id) VALUES (?, ?, 50, ?)", 
                      (user_id, username, referrer_id))
    
    is_joined = await check_channel_join(user_id)
    if not is_joined:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📢 اشترك في القناة أولاً", url="https://t.me/c/3783009565")],
            [InlineKeyboardButton(text="✅ تم الاشتراك", callback_data="check_join")]
        ])
        return await message.answer("⚠️ عذراً! يجب عليك الاشتراك في قناة البوت الرسمية أولاً لتتمكن من استخدامه.", reply_markup=kb)
    
    welcome_msg = (
        f"👋 **أهلاً بك يا {message.from_user.first_name}!**\n\n"
        "🚀 **مرحباً بك في أقوى بوت استضافة على تلجرام!**\n\n"
        "✨ **مميزاتنا:**\n"
        "✅ استضافة حقيقية 24/7\n"
        "✅ تشغيل فوري لبوتك\n"
        "✅ نظام نقاط سهل وممتع\n\n"
        "👇 **اختر من القائمة أدناه للبدء:**"
    )
    await message.answer(welcome_msg, parse_mode="Markdown", reply_markup=main_menu_kb(user_id))

@dp.callback_query(F.data == "check_join")
async def check_join_callback(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    is_joined = await check_channel_join(user_id)
    if is_joined:
        await callback.message.edit_text("✅ شكراً لانضمامك! يمكنك الآن استخدام البوت.", reply_markup=main_menu_kb(user_id))
    else:
        await callback.answer("❌ لم تشترك في القناة بعد!", show_alert=True)

@dp.callback_query(F.data == "my_points")
async def my_points_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    result = execute_query("SELECT points FROM users WHERE user_id = ?", (user_id,), fetchone=True)
    points = result[2] if result else 0
    msg = (
        f"💰 **رصيد نقاطك:** `{points}` نقطة\n\n"
        "📈 **كيف تحصل على نقاط إضافية؟**\n"
        "🎁 شارك رابط الدعوة الخاص بك مع أصدقائك.\n"
        "🎁 ستحصل على **70 نقطة** لكل شخص ينضم عبر رابطك!\n\n"
        "👇 **اضغط أدناه للحصول على رابط الدعوة:**"
    )
    await callback.message.edit_text(msg, parse_mode="Markdown", reply_markup=main_menu_kb(user_id))

@dp.callback_query(F.data == "ref_link")
async def ref_link_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    bot_info = await bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start={user_id}"
    await callback.message.edit_text(f"🔗 رابط الدعوة الخاص بك:\n`{ref_link}`\n\n🎁 ستحصل على **{REFERRAL_POINTS}** نقطة مقابل كل شخص ينضم من خلال رابطك!", parse_mode="Markdown", reply_markup=main_menu_kb(user_id))

@dp.callback_query(F.data == "host_bot")
async def host_bot_callback(callback: CallbackQuery):
    await callback.message.edit_text("💎 اختر خطة الاشتراك المناسبة لك لبدء استضافة بوتك:", reply_markup=plans_kb())

@dp.callback_query(F.data.startswith("buy_"))
async def buy_plan_callback(callback: CallbackQuery, state: FSMContext):
    plan_key = callback.data.split("_")[1]
    plan = PLANS[plan_key]
    user_id = callback.from_user.id
    
    result = execute_query("SELECT points FROM users WHERE user_id = ?", (user_id,), fetchone=True)
    points = result[2] if result else 0
    
    if points < plan['points']:
        return await callback.answer(f"❌ نقاطك غير كافية! تحتاج إلى {plan['points']} نقطة.", show_alert=True)
    
    execute_query("UPDATE users SET points = points - ? WHERE user_id = ?", (plan['points'], user_id))
    await state.update_data(plan=plan_key)
    await callback.message.edit_text(f"✅ تم شراء الاشتراك {plan['name']} بنجاح!\n\nالرجاء إرسال **توكن البوت** الذي تريد استضافته الآن:")
    await state.set_state(HostingStates.waiting_for_token)

@dp.message(HostingStates.waiting_for_token)
async def process_token(message: Message, state: FSMContext):
    if ":" not in message.text or len(message.text) < 20:
        return await message.answer("❌ التوكن غير صحيح! يرجى إرسال توكن صالح:")
    
    await state.update_data(token=message.text)
    await message.answer("✅ تم حفظ التوكن بنجاح!\n\nالآن، يرجى إرسال **ملف كود البايثون (.py)** الذي تريد تشغيله:")
    await state.set_state(HostingStates.waiting_for_code)

@dp.message(HostingStates.waiting_for_code, F.document)
async def process_code(message: Message, state: FSMContext):
    if not message.document.file_name.endswith(".py"):
        return await message.answer("❌ يرجى إرسال ملف ينتهي بـ `.py` فقط!")
    
    user_id = message.from_user.id
    data = await state.get_data()
    token = data.get("token")
    plan_key = data.get("plan")
    plan = PLANS[plan_key]
    
    user_dir = os.path.join(HOSTED_DIR, str(user_id))
    if not os.path.exists(user_dir):
        os.makedirs(user_dir)
    
    file_path = os.path.join(user_dir, "bot.py")
    file = await bot.get_file(message.document.file_id)
    await bot.download_file(file.file_path, file_path)
    
    if user_id in active_processes:
        active_processes[user_id].terminate()
    
    env = os.environ.copy()
    env["BOT_TOKEN"] = token
    
    process = subprocess.Popen(
        ["python3", file_path],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    active_processes[user_id] = process
    
    execute_query(
        "INSERT INTO subscriptions (user_id, bot_token, plan_type, start_date, end_date) VALUES (?, ?, ?, ?, ?)",
        (user_id, token, plan_key, datetime.now(), datetime.now() + timedelta(days=plan['days']))
    )
    
    await message.answer(
        f"🚀 **مبروك! تم تشغيل بوتك بنجاح.**\n\n"
        f"🤖 التوكن: `{token}`\n"
        f"📄 الملف: `{message.document.file_name}`\n"
        f"⏱️ مدة الاشتراك: {plan['name']}\n"
        f"✅ بوتك الآن يعمل في الخلفية 24/7!",
        parse_mode="Markdown",
        reply_markup=main_menu_kb(user_id)
    )
    await state.clear()

@dp.callback_query(F.data == "my_subs")
async def my_subs_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    subs = execute_query("SELECT * FROM subscriptions WHERE user_id = ? AND status = 'active'", (user_id,), fetchall=True)
    
    if not subs:
        return await callback.message.edit_text("❌ ليس لديك اشتراكات نشطة حالياً.", reply_markup=main_menu_kb(user_id))
    
    msg = "📋 **اشتراكاتك النشطة:**\n\n"
    for sub in subs:
        msg += f"🤖 بوت: `{sub[2][:10]}...`\n"
        msg += f"📅 ينتهي في: `{sub[5]}`\n"
        msg += "------------------\n"
    
    await callback.message.edit_text(msg, parse_mode="Markdown", reply_markup=main_menu_kb(user_id))

@dp.callback_query(F.data == "main_menu")
async def back_to_main(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    user_id = callback.from_user.id
    await callback.message.edit_text("🏠 القائمة الرئيسية:", reply_markup=main_menu_kb(user_id))

# Admin commands
@dp.callback_query(F.data == "stats")
async def stats_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    if user_id != OWNER_ID:
        return await callback.answer("❌ هذا القسم خاص بالمطور فقط!", show_alert=True)
    
    total_users = execute_query("SELECT COUNT(*) FROM users", fetchone=True)[0]
    total_subs = execute_query("SELECT COUNT(*) FROM subscriptions", fetchone=True)[0]
    total_points_res = execute_query("SELECT SUM(points) FROM users", fetchone=True)
    total_points = total_points_res[0] if total_points_res else 0
    
    msg = (
        "📊 **إحصائيات البوت:**\n\n"
        f"👥 إجمالي المستخدمين: `{total_users}`\n"
        f"🚀 إجمالي الاشتراكات: `{total_subs}`\n"
        f"💰 إجمالي النقاط الموزعة: `{total_points}`"
    )
    await callback.message.edit_text(msg, parse_mode="Markdown", reply_markup=main_menu_kb(user_id))

@dp.message(Command("add_points"))
async def add_points_cmd(message: Message, command: CommandObject):
    if message.from_user.id != OWNER_ID:
        return
    
    if not command.args:
        return await message.answer("⚠️ الاستخدام: `/add_points [user_id] [points]`")
    
    try:
        args = command.args.split()
        target_id = int(args[0])
        amount = int(args[1])
        
        execute_query("UPDATE users SET points = points + ? WHERE user_id = ?", (amount, target_id))
        await message.answer(f"✅ تم إضافة {amount} نقطة للمستخدم {target_id}")
        try:
            await bot.send_message(target_id, f"🎁 لقد قام المطور بإهدائك {amount} نقطة!")
        except: pass
    except Exception as e:
        await message.answer(f"❌ خطأ: {str(e)}")

# Global handler
@dp.message()
async def global_handler(message: Message, state: FSMContext):
    user_id = message.from_user.id
    is_joined = await check_channel_join(user_id)
    if not is_joined:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📢 اشترك في القناة", url="https://t.me/c/3783009565")],
            [InlineKeyboardButton(text="✅ تم الاشتراك", callback_data="check_join")]
        ])
        return await message.answer("⚠️ يجب عليك الاشتراك في القناة للاستمرار!", reply_markup=kb)

    current_state = await state.get_state()
    if current_state:
        return

    await message.answer("❓ عذراً، لم أفهم طلبك. استخدم القائمة الرئيسية.", reply_markup=main_menu_kb(user_id))

async def main():
    logging.basicConfig(level=logging.INFO)
    init_db() # Ensure DB tables are created
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
