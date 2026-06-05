import os
import asyncio
import zipfile
from io import BytesIO
from pathlib import Path
from tempfile import mkdtemp
from aiogram import F, Router, types, Bot
from aiogram.types import BufferedInputFile, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.enums import ParseMode
import shutil
from start.start import check_subscription

router = Router()

bild = [
    "bilb_sign1.btx", "bilb_sign2.btx", "Billb_AlienCity.btx",
    "Billb_GostownParadise.btx", "Billb_GTABer.btx", "Billb_GTAUnited.btx",
    "Billb_MyriadIslands.btx", "Billb_SanVice.btx", "Billb_YouAreHere.btx",
    "BLBRD_1_a889.btx", "BLBRD_2_889.btx", "BLBRD_3_889.btx",
    "BLBRD_4_889.btx", "BLBRD_5_889.btx", "BLBRD_6_889.btx",
    "BLBRD_btn1_a889.btx", "BLBRD_main1_a889.btx", "reclam62.btx",
    "reclam63.btx", "reclam64.btx", "reclam65.btx", "reclam66.btx",
    "reclam67.btx", "reclam68.btx", "reclam69.btx"
]

async def cleanup_temp_dir(temp_dir: Path):
    if temp_dir.exists():
        shutil.rmtree(temp_dir, ignore_errors=True)

async def process_bild_file(input_data: bytes, user_id: int) -> bytes:
    temp_dir = Path(mkdtemp(prefix=f"bild_{user_id}_"))
    try:
        input_path = temp_dir / "input.btx"
        input_path.write_bytes(input_data)
        
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as zipf:
            for filename in bild:
                zipf.write(input_path, filename)
        
        return zip_buffer.getvalue()
    finally:
        await cleanup_temp_dir(temp_dir)

@router.message(F.text == "/bild")
async def bild_command(message: types.Message, bot: Bot):
    if not await check_subscription(message, bot):
        return
    name = message.from_user.first_name
    await message.answer(
        "<b>чтоб создать кастом билдборды кидай -</b> <code>/bild</code> <b>+ BTX файл</b>",
        parse_mode=ParseMode.HTML
    )

@router.message(F.document, F.caption.in_(["/bild"]) | F.caption.startswith("/bild "))
async def bild_xyina(message: types.Message, bot: Bot):
    if not await check_subscription(message, bot):
        return
    user_id = message.from_user.id
    name = message.from_user.first_name

    if not message.document.file_name.lower().endswith('.btx'):
        await message.reply(f"<b>кидай мне BTX файл!</b>", parse_mode="HTML")
        return
    
    progress_msg = await message.reply(f"<b>⏳ идет процесс ок.</b>", parse_mode="HTML")
    
    try:
        file = await bot.get_file(message.document.file_id)
        file_data = await bot.download_file(file.file_path)
        zip_data = await process_bild_file(file_data.read(), user_id)
        
        await message.reply_document(
            BufferedInputFile(zip_data, "bild.zip"),
            caption=f"<b>📊 файл готов</b>\n<b>📝 назва - bild.zip</b>",
            parse_mode="HTML"
        )
    except Exception as e:
        await message.reply(f"<b>⚠️ ошибко:</b> {str(e)}", parse_mode="HTML")
    finally:
        await progress_msg.delete()