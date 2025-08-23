import logging, io, asyncio, nest_asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

# ------------------- SOZLAMALAR -------------------
BOT_TOKEN = "8277657972:AAHyPqHETqmwvjoeWHvoN31g3SKpdpf5GzU"  # ← bot tokeningiz
SERVICE_ACCOUNT_FILE = "credentials.json"  # ← Colab’ga yuklagan fayl nomi
FOLDER_ID = "1NzxdUHEiq2PWoS3EjodT32drl0NOhH-Z"  # ← Google Drive papka ID
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
DELETE_AFTER = 3600  # 1 soat = 3600 sekund

# ------------------- GOOGLE DRIVE -------------------
creds = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
drive_service = build("drive", "v3", credentials=creds)

# ------------------- LOGGER -------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("salary-bot")

# ------------------- GLOBAL -------------------
MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
user_year = {}  # {telegram_id: year}

# ------------------- UI: keyboard qurish -------------------
def build_keyboard(year:int) -> InlineKeyboardMarkup:
    year_row = [
        InlineKeyboardButton("⬅️", callback_data=f"year_{year-1}"),
        InlineKeyboardButton(str(year), callback_data="noop"),
        InlineKeyboardButton("➡️", callback_data=f"year_{year+1}")
    ]
    month_rows = []
    for i in range(0, 12, 3):
        row = [InlineKeyboardButton(MONTHS[j], callback_data=f"month_{MONTHS[j]}_{year}") for j in range(i, i+3)]
        month_rows.append(row)
    return InlineKeyboardMarkup([year_row] + month_rows)

# ------------------- DELETE FUNCTION -------------------
async def auto_delete(context: ContextTypes.DEFAULT_TYPE, chat_id: int, message_id: int):
    await asyncio.sleep(DELETE_AFTER)
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception as e:
        logger.warning(f"O‘chirishda xatolik: {e}")

# ------------------- /start -------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    year = 2025
    user_year[uid] = year
    msg = await update.message.reply_text(
        "📅 Yil va oyni tanlang:", 
        reply_markup=build_keyboard(year),
        protect_content=True
    )
    context.application.create_task(auto_delete(context, msg.chat_id, msg.message_id))

# ------------------- callbacklar -------------------
async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    uid = query.from_user.id

    if data.startswith("year_"):
        year = int(data.split("_")[1])
        user_year[uid] = year
        await query.edit_message_text(
            "📅 Yil va oyni tanlang:", 
            reply_markup=build_keyboard(year),
            protect_content=True
        )
        return

    if data.startswith("month_"):
        _, mon, year = data.split("_")
        filename = f"{uid}_{mon}_{year}.jpg"

        res = drive_service.files().list(
            q=f"name='{filename}' and '{FOLDER_ID}' in parents and trashed=false",
            fields="files(id, name, mimeType)",
            pageSize=1
        ).execute()
        files = res.get("files", [])

        if not files:
            msg = await query.message.reply_text(f"❌ Fayl topilmadi: {filename}", protect_content=True)
            context.application.create_task(auto_delete(context, msg.chat_id, msg.message_id))
            return

        file_id = files[0]["id"]
        req = drive_service.files().get_media(fileId=file_id)
        buf = io.BytesIO()
        downloader = MediaIoBaseDownload(buf, req)
        done = False
        while not done:
            status, done = downloader.next_chunk()
        buf.seek(0)

        msg = await query.message.reply_photo(
            photo=buf, 
            caption=f"📄 {filename}",
            protect_content=True
        )
        context.application.create_task(auto_delete(context, msg.chat_id, msg.message_id))

        current_year = int(year)
        user_year[uid] = current_year
        menu_msg = await query.message.reply_text(
            "📅 Yil va oyni tanlang:", 
            reply_markup=build_keyboard(current_year),
            protect_content=True
        )
        context.application.create_task(auto_delete(context, menu_msg.chat_id, menu_msg.message_id))
        return

    if data == "noop":
        await query.answer("Yilni o‘zgartirish uchun ⬅️ yoki ➡️ ni bosing.", show_alert=False)

# ------------------- APP -------------------
app = Application.builder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(on_button))

nest_asyncio.apply()

print("🤖 Bot ishga tushdi...")

async def main():
    await app.run_polling()

asyncio.run(main())
