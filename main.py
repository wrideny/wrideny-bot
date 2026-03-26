import os
import sqlite3
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InlineQueryResultVoice
from aiogram.contrib.fsm_storage.memory import MemoryStorage

# ────────────────
# CONFIG
# ────────────────
TOKEN = os.getenv("TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

if not TOKEN:
    raise Exception("TOKEN is not set")

bot = Bot(token=TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())

# ────────────────
# DB
# ────────────────
conn = sqlite3.connect("sounds.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS sounds (
name TEXT PRIMARY KEY,
file_id TEXT,
category TEXT,
favorite INTEGER DEFAULT 0
)
""")
conn.commit()

# ────────────────
# STATES (simple)
# ────────────────
user_state = {}
user_voice = {}

# ────────────────
# HELPERS
# ────────────────
def menu():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("➕ Добавить", callback_data="add"))
    kb.add(InlineKeyboardButton("📜 Все звуки", callback_data="all"))
    return kb


def is_admin(user_id):
    return user_id == ADMIN_ID

# ────────────────
# START
# ────────────────
@dp.message_handler(commands=["start"])
async def start(msg: types.Message):
    if not is_admin(msg.from_user.id):
        return
    await msg.answer("🎧 Sound Bot готов", reply_markup=menu())

# ────────────────
# ADD VOICE STEP 1
# ────────────────
@dp.callback_query_handler(lambda c: c.data == "add")
async def add(cb: types.CallbackQuery):
    user_state[cb.from_user.id] = "voice"
    await cb.message.answer("Отправь голосовое 🎤")

# ────────────────
# VOICE STEP 2
# ────────────────
@dp.message_handler(content_types=["voice"])
async def voice(msg: types.Message):
    if user_state.get(msg.from_user.id) != "voice":
        return

    user_voice[msg.from_user.id] = msg.voice.file_id
    user_state[msg.from_user.id] = "name"

    await msg.answer("Теперь напиши название звука ✏️")

# ────────────────
# TEXT SAVE
# ────────────────
@dp.message_handler()
async def save(msg: types.Message):
    if user_state.get(msg.from_user.id) != "name":
        return

    name = msg.text
    file_id = user_voice.get(msg.from_user.id)

    if not file_id:
        await msg.answer("Ошибка ❌ попробуй заново")
        return

    cursor.execute(
        "INSERT OR REPLACE INTO sounds VALUES (?, ?, ?, 0)",
        (name, file_id, "default")
    )
    conn.commit()

    user_state[msg.from_user.id] = None

    await msg.answer("Сохранено ✅", reply_markup=menu())

# ────────────────
# LIST ALL
# ────────────────
@dp.callback_query_handler(lambda c: c.data == "all")
async def all_sounds(cb: types.CallbackQuery):
    cursor.execute("SELECT name FROM sounds")
    sounds = cursor.fetchall()

    kb = InlineKeyboardMarkup()

    for s in sounds:
        kb.add(InlineKeyboardButton(s[0], callback_data=f"play:{s[0]}"))

    await cb.message.answer("Все звуки 🎧", reply_markup=kb)

# ────────────────
# PLAY SOUND
# ────────────────
@dp.callback_query_handler(lambda c: c.data.startswith("play:"))
async def play(cb: types.CallbackQuery):
    name = cb.data.split(":")[1]

    cursor.execute("SELECT file_id FROM sounds WHERE name=?", (name,))
    res = cursor.fetchone()

    if res:
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("⭐", callback_data=f"fav:{name}"))
        kb.add(InlineKeyboardButton("❌", callback_data=f"del:{name}"))

        await bot.send_voice(cb.message.chat.id, res[0], reply_markup=kb)

# ────────────────
# FAVORITE
# ────────────────
@dp.callback_query_handler(lambda c: c.data.startswith("fav:"))
async def fav(cb: types.CallbackQuery):
    name = cb.data.split(":")[1]

    cursor.execute("UPDATE sounds SET favorite=1 WHERE name=?", (name,))
    conn.commit()

    await cb.message.answer("Добавлено ⭐")

# ────────────────
# DELETE
# ────────────────
@dp.callback_query_handler(lambda c: c.data.startswith("del:"))
async def delete(cb: types.CallbackQuery):
    name = cb.data.split(":")[1]

    cursor.execute("DELETE FROM sounds WHERE name=?", (name,))
    conn.commit()

    await cb.message.answer("Удалено ❌")

# ────────────────
# INLINE SEARCH
# ────────────────
@dp.inline_handler()
async def inline(q: types.InlineQuery):
    cursor.execute("SELECT name, file_id FROM sounds")
    sounds = cursor.fetchall()

    results = []

    for name, file_id in sounds:
        if q.query.lower() in name.lower():
            results.append(
                InlineQueryResultVoice(
                    id=name,
                    voice_url=file_id,
                    title=name
                )
            )

    await bot.answer_inline_query(q.id, results, cache_time=1)

# ────────────────
# RUN
# ────────────────
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
