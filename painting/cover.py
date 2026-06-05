import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Optional
from aiogram import Router, F, Bot
from aiogram.types import Message, BufferedInputFile, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from PIL import Image, ImageFilter, ImageDraw, ImageFont
from aiogram.enums import ParseMode
from io import BytesIO
from start.start import check_subscription

router = Router()

def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip('#')
    if len(hex_color) == 3:
        hex_color = ''.join([c * 2 for c in hex_color])
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

async def cleanup_temp_dir(temp_dir: Path):
    if temp_dir.exists():
        shutil.rmtree(temp_dir, ignore_errors=True)

def get_main_keyboard():
    builder = InlineKeyboardBuilder()
    builder.add(
        InlineKeyboardButton(text="🎨 Палитра HEX цветов", url="https://csscolor.ru/")
    )
    builder.adjust(1)
    return builder.as_markup()

async def process_cover(image_data: bytes, hex_color: str, border_size: int, user_id: int) -> bytes:
    temp_dir = Path(tempfile.mkdtemp(prefix=f"cover_{user_id}_"))
    try:
        input_path = temp_dir / "input.jpg"
        output_path = temp_dir / "output.jpg"
        
        input_path.write_bytes(image_data)
        
        with Image.open(input_path) as original_image:
            width, height = original_image.size
            
            blurred_image = original_image.copy().filter(ImageFilter.GaussianBlur(15))
            blurred_image = blurred_image.crop((0, 0, width, height))
            
            scale = 0.9
            resized_copy = original_image.resize(
                (int(width * scale), int(height * scale)), 
                Image.LANCZOS
            )
            
            if border_size > 0:
                border_color = hex_to_rgb(hex_color)
                bordered_image = Image.new("RGB", 
                    (resized_copy.width + 2 * border_size, resized_copy.height + 2 * border_size),
                    border_color
                )
                bordered_image.paste(resized_copy, (border_size, border_size))
                resized_copy = bordered_image
            
            blurred_image.paste(
                resized_copy,
                ((width - resized_copy.width) // 2, (height - resized_copy.height) // 2))
            
            blurred_image.save(output_path, quality=95)
            
            with open(output_path, "rb") as f:
                return f.read()
    finally:
        await cleanup_temp_dir(temp_dir)

@router.message(Command("cover"))
async def cover(message: Message, bot: Bot):
    if not await check_subscription(message, bot):
        return
    user_id = message.from_user.id
    name = message.from_user.first_name
    
    has_photo = message.photo is not None
    has_document = (message.document and 
                   message.document.mime_type in ['image/png', 'image/jpeg', 'image/jpg'])
    
    if not (has_photo or has_document):
        await message.answer(
            f"<b>Чтобы создать обложку сборки отправьте -</b> <code>/cover #FFFFFF 20</code> <b>+ PNG, JPG, JPEG</b>",
            reply_markup=get_main_keyboard(),
            parse_mode=ParseMode.HTML
        )
        return
    
    if not message.caption:
        await message.answer(f"<b>Используй команду в правильных параметрах!</b>", parse_mode=ParseMode.HTML)
        return
    
    args = message.caption.split()
    if len(args) != 3 or not re.match(r'^#([0-9a-fA-F]{3}){1,2}$', args[1]) or not args[2].isdigit():
        await message.answer(
            f"<b>Кажется вы ввели неверный формат команды!</b>",
            parse_mode=ParseMode.HTML
        )
        return
    
    hex_color = args[1]
    border_size = int(args[2])
    
    try:
        progress_msg = await message.reply(f"<b>⏳ Обрабатываю ваш файл...</b>", parse_mode=ParseMode.HTML)
        if has_photo:
            file_id = message.photo[-1].file_id
            original_filename = f"cover_{user_id}.jpg"
        else:
            file_id = message.document.file_id
            original_filename = message.document.file_name
        
        file = await message.bot.get_file(file_id)
        file_data = await message.bot.download_file(file.file_path)
        
        processed_image = await process_cover(file_data.read(), hex_color, border_size, user_id)
        
        await message.answer_photo(
            photo=BufferedInputFile(processed_image, original_filename),
            caption=f"<b>📊 Ваш файл готов</b>\n<b>📝 Название - photo.jpg</b>",
            parse_mode=ParseMode.HTML
        )
        await progress_msg.delete()
                
    except Exception as e:
        await message.answer(
            f"<b>Ошибка обработки:</b> {str(e)}",
            parse_mode=ParseMode.HTML
        )