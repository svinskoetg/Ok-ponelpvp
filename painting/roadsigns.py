import zipfile
import asyncio
from io import BytesIO
from pathlib import Path
import numpy as np
from PIL import Image, ImageColor
from aiogram import Router, F, Bot
from aiogram.types import Message, BufferedInputFile, CallbackQuery
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.enums import ParseMode
import tempfile
import shutil
import os
from start.start import check_subscription

router = Router()

ROADSIGNS_DIR = Path("painting/photo/roadsigns")

def colar66(image: Image.Image, color_hex: str) -> Image.Image:
    color = ImageColor.getrgb(color_hex)
    r_target, g_target, b_target = color[:3]

    if image.mode != 'RGBA':
        image = image.convert('RGBA')

    img_array = np.array(image, dtype=np.float32)
    r, g, b, a = img_array[:, :, 0], img_array[:, :, 1], img_array[:, :, 2], img_array[:, :, 3]
    luminance = (r * 0.299 + g * 0.587 + b * 0.114) / 255.0
    
    img_array[:, :, 0] = luminance * r_target
    img_array[:, :, 1] = luminance * g_target  
    img_array[:, :, 2] = luminance * b_target
    
    return Image.fromarray(np.clip(img_array, 0, 255).astype(np.uint8), 'RGBA')

async def process_single_image(image_path: Path, color_hex: str) -> bytes:
    with Image.open(image_path) as img:
        colored_img = colar66(img, color_hex)
        output = BytesIO()
        colored_img.save(output, format='PNG', optimize=True)
        return output.getvalue()

async def process_roadsigns_images(color_hex: str, user_id: int) -> bytes:
    temp_dir = Path(f"temp_roadsigns_{user_id}")
    temp_dir.mkdir(exist_ok=True)
    
    try:
        image_files = [f.name for f in ROADSIGNS_DIR.glob('*.png')]
        
        tasks = []
        for image_file in image_files:
            image_path = ROADSIGNS_DIR / image_file
            tasks.append(process_single_image(image_path, color_hex))
        
        processed_images = await asyncio.gather(*tasks, return_exceptions=True)
        
        for image_file, processed_data in zip(image_files, processed_images):
            if not isinstance(processed_data, Exception):
                with open(temp_dir / image_file, 'wb') as f:
                    f.write(processed_data)
            else:
                shutil.copy(ROADSIGNS_DIR / image_file, temp_dir / image_file)
        
        output_zip = BytesIO()
        with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as zip_out:
            for image_file in image_files:
                file_path = temp_dir / image_file
                if file_path.exists():
                    zip_out.write(file_path, image_file)
        
        return output_zip.getvalue()
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

def get_roadsigns_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="🎨 палитра HEX цветов", url="https://csscolor.ru/")
    builder.adjust(1)
    return builder.as_markup()

@router.message(Command("roadsigns"))
async def roadsigns(message: Message, bot: Bot):
    if not await check_subscription(message, bot):
        return
    args = message.text.split()
    name = message.from_user.first_name
    user_id = message.from_user.id
    
    if len(args) == 1:
        await message.answer(
            f"<b>чтоб покрасить дорожные знаки кидай -</b> <code>/roadsigns #FFFFFF</code>",
            reply_markup=get_roadsigns_keyboard(),
            parse_mode=ParseMode.HTML
        )
        return
 
    try:
        progress_msg = await message.reply(f"<b>⏳ процесс идёт ок.</b>", parse_mode=ParseMode.HTML)
        
        color_hex = args[1].strip()
        ImageColor.getrgb(color_hex)
        
        zip_data = await process_roadsigns_images(color_hex, user_id)
        result_file = BufferedInputFile(zip_data, filename=f"roadsigns.zip")
        
        await message.reply_document(
            document=result_file,
            caption=f"<b>📊 файл готов</b>\n<b>📝 назва - roadsigns.zip</b>",
            parse_mode=ParseMode.HTML
        )
        
    except ValueError:
        await progress_msg.edit_text(
            f"<b>похоже ты ввел неправильный HEX-код, норм введи чтоб заработало.</b>",
            parse_mode=ParseMode.HTML
        )
        await asyncio.sleep(5)
    except Exception as e:
        await progress_msg.edit_text(
            f"<b>произошла ошибко: {str(e)}</b>",
            parse_mode=ParseMode.HTML
        )
        await asyncio.sleep(5)
    finally:
        try:
            await progress_msg.delete()
        except:
            pass