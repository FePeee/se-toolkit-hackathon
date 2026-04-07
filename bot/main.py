import asyncio
import logging
from datetime import datetime
import pytz

from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from openai import AsyncOpenAI
import httpx
import os

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
API_URL = os.getenv("API_URL", "http://backend:8000")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")

logging.basicConfig(level=logging.INFO)
router = Router()

ai_client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)

TIMEZONES = [
    "UTC", "Europe/Moscow", "Europe/London", "Europe/Berlin",
    "Asia/Yekaterinburg", "Asia/Novosibirsk", "Asia/Vladivostok",
    "America/New_York", "America/Los_Angeles", "Asia/Dubai"
]


class Registration(StatesGroup):
    waiting_name = State()
    waiting_timezone = State()

class AddHabit(StatesGroup):
    waiting_name = State()
    waiting_time = State()


async def ask_ai(prompt: str) -> str:
    try:
        response = await ai_client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"AI error: {str(e)}"


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    args = message.text.split()
    telegram_id = str(message.from_user.id)

    if len(args) > 1:
        code = args[1]
        async with httpx.AsyncClient() as client:
            r = await client.post(f"{API_URL}/api/link-telegram", json={
                "code": code, "telegram_id": telegram_id
            })
        if r.status_code == 200:
            await message.answer(f"✅ Account linked! Welcome, {r.json().get('name', '')}!\n\nUse /help to see all commands.")
        else:
            await message.answer("❌ Invalid code. Try again.")
        return

    async with httpx.AsyncClient() as client:
        r = await client.get(f"{API_URL}/api/user-by-telegram/{telegram_id}")

    if r.status_code == 200:
        await message.answer(f"👋 Welcome back, {r.json().get('name', '')}!\n\nUse /help to see all commands.")
    else:
        await state.set_state(Registration.waiting_name)
        await message.answer("👋 Welcome to *Habit Tracker*!\n\nLet's set up your account. What's your name?", parse_mode="Markdown")


@router.message(Registration.waiting_name)
async def reg_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    buttons = [[InlineKeyboardButton(text=tz, callback_data=f"tz:{tz}")] for tz in TIMEZONES]
    await state.set_state(Registration.waiting_timezone)
    await message.answer("🌍 Select your timezone:", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))


@router.callback_query(F.data.startswith("tz:"))
async def reg_timezone(callback: CallbackQuery, state: FSMContext):
    tz = callback.data.split(":", 1)[1]
    data = await state.get_data()
    name = data.get("name", callback.from_user.first_name)
    telegram_id = str(callback.from_user.id)

    async with httpx.AsyncClient() as client:
        r = await client.post(f"{API_URL}/api/register-telegram", json={
            "telegram_id": telegram_id, "name": name, "timezone": tz,
        })

    await state.clear()
    if r.status_code == 200:
        await callback.message.edit_text(
            f"✅ Account created!\nName: *{name}*\nTimezone: *{tz}*\n\nAdd your first habit with /add",
            parse_mode="Markdown"
        )
    else:
        await callback.message.edit_text(f"❌ Error: {r.json().get('detail', 'Error')}")


@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "📖 *Habit Tracker — commands:*\n\n"
        "/add — add a new habit\n"
        "/done — mark habits as complete today\n"
        "/list — view all your habits\n"
        "/stats — streaks and weekly progress\n"
        "/report — AI weekly accountability report\n"
        "/delete — delete a habit\n"
        "/timezone — change your timezone\n"
        "/help — show this message",
        parse_mode="Markdown"
    )


@router.message(Command("add"))
async def cmd_add(message: Message, state: FSMContext):
    telegram_id = str(message.from_user.id)
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{API_URL}/api/user-by-telegram/{telegram_id}")
    if r.status_code != 200:
        await message.answer("❌ Please register first by sending /start")
        return
    await state.set_state(AddHabit.waiting_name)
    await message.answer("📝 What habit do you want to track?\n\nExamples: Running, Read 30 min, Meditation")


@router.message(AddHabit.waiting_name)
async def process_habit_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await state.set_state(AddHabit.waiting_time)
    await message.answer("⏰ Set a daily reminder time (e.g. 08:00)\n\nOr send /skip to add without reminder")


@router.message(AddHabit.waiting_time)
async def process_habit_time(message: Message, state: FSMContext):
    data = await state.get_data()
    telegram_id = str(message.from_user.id)
    reminder_time = None if message.text.strip() == "/skip" else message.text.strip()

    async with httpx.AsyncClient() as client:
        create_r = await client.post(
            f"{API_URL}/api/habits-by-telegram-create/{telegram_id}",
            json={"name": data["name"], "reminder_time": reminder_time}
        )

    if create_r.status_code == 200:
        reminder_text = f" — reminder at {reminder_time}" if reminder_time else ""
        await message.answer(f"✅ Habit added: *{data['name']}*{reminder_text}", parse_mode="Markdown")
    else:
        await message.answer(f"❌ Error: {create_r.text}")
    await state.clear()


@router.message(Command("list"))
async def cmd_list(message: Message):
    telegram_id = str(message.from_user.id)
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{API_URL}/api/habits-by-telegram/{telegram_id}")
    if r.status_code != 200:
        await message.answer("❌ Please register first by sending /start")
        return
    habits = r.json()
    if not habits:
        await message.answer("You have no habits yet. Add one with /add")
        return
    text = "📋 *Your habits:*\n\n"
    for h in habits:
        status = "✅" if h["done_today"] else "❌"
        text += f"{status} {h['name']}\n"
    await message.answer(text, parse_mode="Markdown")


@router.message(Command("done"))
async def cmd_done(message: Message):
    telegram_id = str(message.from_user.id)
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{API_URL}/api/habits-by-telegram/{telegram_id}")
    if r.status_code != 200:
        await message.answer("❌ Please register first by sending /start")
        return
    habits = r.json()
    if not habits:
        await message.answer("No habits found. Add one with /add")
        return
    pending = [h for h in habits if not h["done_today"]]
    if not pending:
        await message.answer("🎉 All habits completed for today! Great job!")
        return
    buttons = [[InlineKeyboardButton(text=f"✅ {h['name']}", callback_data=f"complete:{h['id']}")] for h in pending]
    await message.answer("Which habit did you complete today?", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))


@router.callback_query(F.data.startswith("complete:"))
async def callback_complete(callback: CallbackQuery):
    habit_id = callback.data.split(":")[1]
    telegram_id = str(callback.from_user.id)
    async with httpx.AsyncClient() as client:
        r = await client.post(f"{API_URL}/api/complete-by-telegram/{telegram_id}/{habit_id}")
    if r.status_code == 200:
        streak = r.json().get("streak", 0)
        await callback.answer(f"✅ Done! Streak: {streak} days 🔥")
        await callback.message.edit_text(f"✅ Marked as complete! Current streak: *{streak} days* 🔥", parse_mode="Markdown")
    else:
        await callback.answer("❌ Error. Try again.")


@router.message(Command("stats"))
async def cmd_stats(message: Message):
    telegram_id = str(message.from_user.id)
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{API_URL}/api/stats/{telegram_id}")
    if r.status_code != 200:
        await message.answer("❌ Please register first by sending /start")
        return
    data = r.json()
    habits = data["habits"]
    if not habits:
        await message.answer("No habits yet. Add one with /add")
        return
    text = f"📊 *Stats for {data['name']}*\n\n"
    for h in habits:
        status = "✅" if h["done_today"] else "❌"
        fire = " 🔥" if h["streak"] >= 3 else ""
        text += f"{status} *{h['name']}*{fire}\n"
        text += f"   Streak: {h['streak']} days | This week: {h['week_completion']}\n\n"
    await message.answer(text, parse_mode="Markdown")

@router.message(Command("timezone"))
async def cmd_timezone(message: Message):
    timezones = [
        ("🇷🇺 Moscow (UTC+3)", "Europe/Moscow"),
        ("🇷🇺 Yekaterinburg (UTC+5)", "Asia/Yekaterinburg"),
        ("🇷🇺 Novosibirsk (UTC+7)", "Asia/Novosibirsk"),
        ("🇷🇺 Vladivostok (UTC+10)", "Asia/Vladivostok"),
        ("🌍 UTC+0", "UTC"),
        ("🇩🇪 Berlin (UTC+1/2)", "Europe/Berlin"),
        ("🇦🇪 Dubai (UTC+4)", "Asia/Dubai"),
        ("🇺🇸 New York (UTC-5)", "America/New_York"),
        ("🇺🇸 Los Angeles (UTC-8)", "America/Los_Angeles"),
    ]
    buttons = [[InlineKeyboardButton(text=label, callback_data=f"settz:{tz}")] for label, tz in timezones]
    await message.answer("🌍 Select your timezone:", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))


@router.callback_query(F.data.startswith("settz:"))
async def callback_set_timezone(callback: CallbackQuery):
    tz = callback.data.split(":", 1)[1]
    telegram_id = str(callback.from_user.id)

    async with httpx.AsyncClient() as client:
        r = await client.patch(
            f"{API_URL}/api/user-timezone/{telegram_id}",
            json={"timezone": tz}
        )

    if r.status_code == 200:
        await callback.message.edit_text(f"✅ Timezone updated to *{tz}*", parse_mode="Markdown")
    else:
        await callback.answer("❌ Error. Try again.")


@router.message(Command("report"))
async def cmd_report(message: Message):
    telegram_id = str(message.from_user.id)
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{API_URL}/api/stats/{telegram_id}")
    if r.status_code != 200:
        await message.answer("❌ Please register first by sending /start")
        return
    data = r.json()
    habits = data["habits"]
    if not habits:
        await message.answer("No habits to analyze yet. Add some with /add")
        return

    await message.answer("🤖 Analyzing your habits... please wait")

    habits_text = "\n".join([
        f"- {h['name']}: streak {h['streak']} days, this week {h['week_completion']}, done today: {h['done_today']}"
        for h in habits
    ])
    prompt = f"""You are an accountability coach. Analyze this person's habit data and give a short motivational weekly report.

User: {data['name']}
Habits this week:
{habits_text}

Write a brief report (3-5 sentences) that:
1. Highlights their strongest habit
2. Points out which habit needs more attention
3. Gives one specific actionable tip
4. Ends with encouragement

Be direct, friendly, and specific. Use emojis."""

    report = await ask_ai(prompt)
    await message.answer(f"📊 *Weekly Report for {data['name']}*\n\n{report}", parse_mode="Markdown")


@router.message(Command("delete"))
async def cmd_delete(message: Message):
    telegram_id = str(message.from_user.id)
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{API_URL}/api/habits-by-telegram/{telegram_id}")
    if r.status_code != 200:
        await message.answer("❌ Please register first by sending /start")
        return
    habits = r.json()
    if not habits:
        await message.answer("No habits to delete.")
        return
    buttons = [[InlineKeyboardButton(text=f"🗑 {h['name']}", callback_data=f"delete:{h['id']}")] for h in habits]
    await message.answer("Which habit do you want to delete?", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))


@router.callback_query(F.data.startswith("delete:"))
async def callback_delete(callback: CallbackQuery):
    habit_id = callback.data.split(":")[1]
    telegram_id = str(callback.from_user.id)
    async with httpx.AsyncClient() as client:
        r = await client.delete(f"{API_URL}/api/habits-by-telegram-delete/{telegram_id}/{habit_id}")
    if r.status_code == 200:
        await callback.answer("🗑 Deleted!")
        await callback.message.edit_text("✅ Habit deleted.")
    else:
        await callback.answer("❌ Error. Try again.")


async def send_reminders(bot: Bot):
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{API_URL}/api/all-users-habits")
    if r.status_code != 200:
        return
    for entry in r.json():
        telegram_id = entry["telegram_id"]
        timezone = entry.get("timezone", "UTC")
        habit_name = entry["habit_name"]
        reminder_time = entry["reminder_time"]
        done_today = entry["done_today"]
        if not reminder_time or not telegram_id:
            continue
        try:
            tz = pytz.timezone(timezone)
            now_local = datetime.now(tz)
            habit_hour, habit_min = map(int, reminder_time.split(":"))
            if now_local.hour == habit_hour and now_local.minute == habit_min and not done_today:
                await bot.send_message(telegram_id, f"⏰ Reminder: *{habit_name}*\nDon't forget to complete it today!", parse_mode="Markdown")
        except Exception as e:
            logging.error(f"Reminder error: {e}")


async def ai_accountability_check(bot: Bot):
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{API_URL}/api/all-users-stats")
    if r.status_code != 200:
        return
    for user_data in r.json():
        telegram_id = user_data.get("telegram_id")
        if not telegram_id:
            continue
        skipped = [h for h in user_data["habits"] if not h["done_today"] and h["streak"] > 0]
        if not skipped:
            continue
        skipped_names = ", ".join([h["name"] for h in skipped])
        prompt = f"""The user '{user_data['name']}' skipped these habits today: {skipped_names}.
Their streaks are at risk. Write a short (2-3 sentences) friendly but firm accountability message. Use emojis."""
        msg = await ask_ai(prompt)
        try:
            await bot.send_message(telegram_id, f"🤖 *Accountability check*\n\n{msg}", parse_mode="Markdown")
        except Exception as e:
            logging.error(f"AI check error: {e}")


async def main():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    scheduler = AsyncIOScheduler()
    scheduler.add_job(send_reminders, "cron", minute="*", args=[bot])
    scheduler.add_job(ai_accountability_check, "cron", hour=21, minute=0, args=[bot])
    scheduler.start()

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())