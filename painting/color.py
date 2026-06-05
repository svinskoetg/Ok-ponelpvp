import asyncio
import zipfile
from io import BytesIO
from pathlib import Path
import numpy as np
from PIL import Image, ImageColor
from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import Command
from aiogram.types import Message, BufferedInputFile, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.enums import ParseMode
from tempfile import mkdtemp
import shutil
from start.start import check_subscription

router = Router()

def validate_hex_color(color_hex: str) -> bool:
    try:
        ImageColor.getrgb(color_hex)
        return True
    except ValueError:
        return False

async def cleanup_temp_dir(temp_dir: Path):
    if temp_dir.exists():
        shutil.rmtree(temp_dir, ignore_errors=True)

async def process(image_data: bytes, color_hex: str) -> bytes:
    with Image.open(BytesIO(image_data)) as img:
        if img.mode != 'RGBA':
            img = img.convert('RGBA')

        color = ImageColor.getrgb(color_hex)
        r_target, g_target, b_target = color[:3]

        img_array = np.array(img, dtype=np.float32)
        r, g, b = img_array[:, :, 0], img_array[:, :, 1], img_array[:, :, 2]
        luminance = (r * 0.299 + g * 0.587 + b * 0.114) / 255.0
        
        img_array[:, :, 0] = luminance * r_target
        img_array[:, :, 1] = luminance * g_target
        img_array[:, :, 2] = luminance * b_target
        
        output = BytesIO()
        Image.fromarray(np.clip(img_array, 0, 255).astype(np.uint8), 'RGBA').save(output, format='PNG', optimize=True)
        return output.getvalue()

async def process_zip_file(zip_data: bytes, color_hex: str) -> bytes:
    temp_dir = Path(mkdtemp(prefix="color_"))
    try:
        output_zip = BytesIO()
        with zipfile.ZipFile(BytesIO(zip_data), 'r') as zip_in, \
             zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as zip_out:
            
            for file_info in zip_in.infolist():
                file_ext = Path(file_info.filename).suffix.lower()
                if file_ext in {'.png', '.jpg', '.jpeg'}:
                    try:
                        processed = await process(zip_in.read(file_info.filename), color_hex)
                        zip_out.writestr(file_info.filename, processed)
                    except Exception:
                        zip_out.writestr(file_info.filename, zip_in.read(file_info.filename))
                else:
                    zip_out.writestr(file_info.filename, zip_in.read(file_info.filename))
        
        return output_zip.getvalue()
    finally:
        await cleanup_temp_dir(temp_dir)

def get_main_keyboard():
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="🎨 палитра HEX цветов", url="https://csscolor.ru/"))
    builder.adjust(1)
    return builder.as_markup()

@router.message(Command("color"))
async def color(message: Message, bot: Bot):
    if not await check_subscription(message, bot):
        return
    name = message.from_user.first_name
    message_text = message.text or message.caption
    
    if not message_text or len(message_text.split()) < 2:
        if not (message.document or message.photo):
            await message.answer(
                f"<b>чтоб покрасить файлы, кидай - </b><code>/color #FFFFFF</code> <b>+ PNG, JPG, ZIP файл</b>",
                parse_mode="HTML",
                reply_markup=get_main_keyboard()
            )
            return
    
    args = message_text.split()
    color_hex = args[1].strip()

    if not (message.document or message.photo):
        await message.answer(
            f"<b>прикрепи файлы PNG, JPG, JPEG или ZIP-архив!</b>",
            parse_mode="HTML",
            reply_markup=get_main_keyboard()
        )
        return

    progress_msg = await message.reply(f"<b>⏳ процесс идёт ок.</b>",     parse_mode=ParseMode.HTML)
    
    temp_dir = Path(mkdtemp(prefix=f"color_{message.from_user.id}_"))
    try:
        if message.document:
            file_id = message.document.file_id
            file_name = message.document.file_name or "file"
            file_ext = Path(file_name).suffix.lower()
        else:
            file_id = message.photo[-1].file_id
            file_name = "photo.jpg"
            file_ext = ".jpg"
    
        if file_ext not in {'.png', '.jpg', '.jpeg', '.zip'}:
            await progress_msg.edit_text(
                f"<b>неподдерживаемый формат файла!</b>"
            )
            await asyncio.sleep(5)
            return
        
        bot = message.bot
        file = await bot.get_file(file_id)
        file_path = temp_dir / file_name
        await bot.download_file(file.file_path, file_path)
        
        with open(file_path, "rb") as f:
            file_data = f.read()
        
        if file_ext == '.zip':
            result_data = await process_zip_file(file_data, color_hex)
            result_name = f"shouxs.color.zip"
        else:
            result_data = await process(file_data, color_hex)
            result_name = f"shouxs.{file_ext}"
        
        result_file = BufferedInputFile(result_data, filename=result_name)
        await message.reply_document(
            document=result_file,
            caption=f"<b>📊 файл готов</b>\n<b>📝 назва - {result_name}</b>",
            parse_mode="HTML"
        )
        
    except Exception as e:
        await progress_msg.edit_text(
            f"<b>произошла ошибко:</b>\n<b><code>{str(e)}</code></b>"
        )
        await asyncio.sleep(5)
    finally:
        try:
            await progress_msg.delete()
        except:
            pass
        await cleanup_temp_dir(temp_dir)