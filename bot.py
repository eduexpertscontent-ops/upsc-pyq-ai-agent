import os
import pandas as pd
import logging
import glob
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters import Command
import asyncio

# 1. LOAD SETTINGS
load_dotenv()
API_TOKEN = os.getenv("BOT_TOKEN")
logging.basicConfig(level=logging.INFO)

# 2. LOAD EXCEL DATA
# The code looks for your specific file name
EXCEL_FILE = "Upsc_Prelims_PYQ_2014-2025 NEW.xlsx"

try:
    excel_data = pd.read_excel(EXCEL_FILE, sheet_name=None)
    all_sheets = [sheet for name, sheet in excel_data.items() if name != "All PYQ"]
    db = pd.concat(all_sheets, ignore_index=True)
    db['Year'] = db['Year'].astype(int)
    
    # Map topics to numbers so Telegram buttons don't break
    unique_topics = db['Broad Topic'].dropna().unique().tolist()
    topic_map = {i: topic for i, topic in enumerate(unique_topics)}
    rev_topic_map = {topic: i for i, topic in enumerate(unique_topics)}
except Exception as e:
    print(f"Error loading Excel: {e}")

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# 3. FORMATTING HELPER
def format_q(row):
    opts = []
    for L in ['A', 'B', 'C', 'D']:
        val = row.get(f'Option {L}')
        if pd.notna(val): opts.append(f"<b>{L})</b> {val}")
    
    return (f"📅 <b>UPSC {row['Year']}</b> | 📚 <b>{row['Subject']}</b>\n"
            f"🏷 <i>{row['Broad Topic']}</i>\n━━━━━━━━━━━━━━━\n\n"
            f"{row['Question Text']}\n\n" + "\n\n".join(opts))

# 4. MAIN MENU
@dp.message(Command("start"))
async def cmd_start(m: types.Message):
    # 1. If the message is in a group
    if m.chat.type in ["group", "supergroup"]:
        try:
            # Send the menu to the user's PRIVATE chat
            kb = InlineKeyboardBuilder()
            kb.row(types.InlineKeyboardButton(text="🗓 Year-wise", callback_data="start_year"))
            kb.row(types.InlineKeyboardButton(text="📖 Subject-wise", callback_data="start_sub"))
            
            await bot.send_message(
                m.from_user.id, 
                "<b>UPSC PYQ Agent</b>\nYou started this from the group. Here is your private study space:",
                reply_markup=kb.as_markup(),
                parse_mode="HTML"
            )
            
            # 2. DELETE the /start message from the group so others don't see it
            await m.delete()
            
        except Exception as e:
            # If the user has NEVER messaged the bot privately, the bot can't DM them.
            # We show a temporary notice and then delete it.
            note = await m.reply(f"Hi {m.from_user.first_name}, please click @{(await bot.get_me()).username} and press 'Start' first to enable private search!")
            await asyncio.sleep(10)
            await note.delete()
            await m.delete()
        return

    # 3. If the message is already in PRIVATE chat
    kb = InlineKeyboardBuilder()
    kb.row(types.InlineKeyboardButton(text="🗓 Year-wise", callback_data="start_year"))
    kb.row(types.InlineKeyboardButton(text="📖 Subject-wise", callback_data="start_sub"))
    await m.answer("<b>UPSC PYQ Agent</b>\nChoose a mode or type a keyword to search:", 
                   reply_markup=kb.as_markup(), parse_mode="HTML")
# --- YEAR WISE PATH ---
@dp.callback_query(F.data == "start_year")
async def yr_sel(c: types.CallbackQuery):
    years = sorted(db['Year'].unique(), reverse=True)
    kb = InlineKeyboardBuilder()
    for yr in years:
        kb.add(types.InlineKeyboardButton(text=str(yr), callback_data=f"y_{yr}"))
    kb.adjust(3)
    kb.row(types.InlineKeyboardButton(text="⬅️ Back", callback_data="home"))
    await c.message.edit_text("Select Year:", reply_markup=kb.as_markup())

@dp.callback_query(F.data.startswith("y_"))
async def sub_for_yr(c: types.CallbackQuery):
    yr = int(c.data.split("_")[1])
    subs = sorted(db[db['Year'] == yr]['Subject'].unique())
    kb = InlineKeyboardBuilder()
    for s in subs:
        kb.add(types.InlineKeyboardButton(text=s, callback_data=f"ys_{yr}_{s}"))
    kb.adjust(2)
    kb.row(types.InlineKeyboardButton(text="⬅️ Back", callback_data="start_year"))
    await c.message.edit_text(f"Subject for {yr}:", reply_markup=kb.as_markup())

@dp.callback_query(F.data.startswith("ys_"))
async def top_for_yr(c: types.CallbackQuery):
    _, yr, s = c.data.split("_")
    tops = sorted(db[(db['Year'] == int(yr)) & (db['Subject'] == s)]['Broad Topic'].unique())
    kb = InlineKeyboardBuilder()
    for t in tops:
        kb.add(types.InlineKeyboardButton(text=t[:30], callback_data=f"f_yr_{yr}_{rev_topic_map[t]}_0"))
    kb.adjust(1)
    kb.row(types.InlineKeyboardButton(text="⬅️ Back", callback_data=f"y_{yr}"))
    await c.message.edit_text(f"Topic ({s} {yr}):", reply_markup=kb.as_markup())

# --- SUBJECT WISE PATH ---
@dp.callback_query(F.data == "start_sub")
async def sub_direct(c: types.CallbackQuery):
    subs = sorted(db['Subject'].unique())
    kb = InlineKeyboardBuilder()
    for s in subs:
        kb.add(types.InlineKeyboardButton(text=s, callback_data=f"s_{s}"))
    kb.adjust(2)
    kb.row(types.InlineKeyboardButton(text="⬅️ Back", callback_data="home"))
    await c.message.edit_text("Select Subject:", reply_markup=kb.as_markup())

@dp.callback_query(F.data.startswith("s_"))
async def top_direct(c: types.CallbackQuery):
    s = c.data.split("_")[1]
    tops = sorted(db[db['Subject'] == s]['Broad Topic'].unique())
    kb = InlineKeyboardBuilder()
    for t in tops:
        kb.add(types.InlineKeyboardButton(text=t[:30], callback_data=f"f_sub_{s}_{rev_topic_map[t]}_0"))
    kb.adjust(1)
    kb.row(types.InlineKeyboardButton(text="⬅️ Back", callback_data="start_sub"))
    await c.message.edit_text(f"Topic in {s}:", reply_markup=kb.as_markup())

# --- DISPLAY & PAGINATION ---
@dp.callback_query(F.data.startswith("f_"))
async def show_results(c: types.CallbackQuery):
    _, mode, f1, t_id, page = c.data.split("_")
    t_id, page = int(t_id), int(page)
    topic = topic_map[t_id]
    PAGE_SIZE = 3
    
    if mode == "yr":
        res = db[(db['Year'] == int(f1)) & (db['Broad Topic'] == topic)]
    else:
        res = db[(db['Subject'] == f1) & (db['Broad Topic'] == topic)]
    
    batch = res.iloc[page*PAGE_SIZE : (page+1)*PAGE_SIZE]
    await c.message.answer(f"📦 <b>{topic}</b> (Page {page+1})", parse_mode="HTML")
    
    for _, row in batch.iterrows():
        akb = InlineKeyboardBuilder()
        akb.add(types.InlineKeyboardButton(text="👁 Reveal Answer", callback_data=f"ans_{row['Answer']}"))
        await c.message.answer(format_q(row), reply_markup=akb.as_markup(), parse_mode="HTML")

    nav = InlineKeyboardBuilder()
    if page > 0:
        nav.add(types.InlineKeyboardButton(text="⬅️ Prev", callback_data=f"f_{mode}_{f1}_{t_id}_{page-1}"))
    if (page+1)*PAGE_SIZE < len(res):
        nav.add(types.InlineKeyboardButton(text="Next ➡️", callback_data=f"f_{mode}_{f1}_{t_id}_{page+1}"))
    
    if page > 0 or (page+1)*PAGE_SIZE < len(res):
        await c.message.answer("Navigation:", reply_markup=nav.as_markup())
    await c.answer()

@dp.callback_query(F.data.startswith("ans_"))
async def reveal(c: types.CallbackQuery):
    await c.answer(f"Correct Answer: {c.data.split('_')[1]}", show_alert=True)

@dp.callback_query(F.data == "home")
async def home(c: types.CallbackQuery):
    await cmd_start(c.message)

# --- SEARCH FEATURE ---
@dp.message()
async def search_handler(m: types.Message):
    if not m.text or len(m.text) < 3: return
    query = m.text.lower()
    mask = db['Question Text'].str.lower().str.contains(query, na=False) | \
           db['Broad Topic'].str.lower().str.contains(query, na=False)
    results = db[mask].head(5)
    
    if results.empty:
        await m.reply("No matches found. Try a different keyword.")
    else:
        for _, row in results.iterrows():
            akb = InlineKeyboardBuilder()
            akb.add(types.InlineKeyboardButton(text="👁 Reveal Answer", callback_data=f"ans_{row['Answer']}"))
            await m.answer(format_q(row), reply_markup=akb.as_markup(), parse_mode="HTML")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":

    asyncio.run(main())


