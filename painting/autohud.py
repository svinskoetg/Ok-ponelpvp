import asyncio
import zipfile
from io import BytesIO
from pathlib import Path
import numpy as np
from PIL import Image, ImageColor
from aiogram import Router, F,  Bot
from aiogram.types import Message, BufferedInputFile, CallbackQuery
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from concurrent.futures import ThreadPoolExecutor
import os
import random
from tempfile import mkdtemp
import shutil
from start.start import check_subscription

router = Router()
thread_pool = ThreadPoolExecutor(max_workers=os.cpu_count() * 2)

async def validate_hex_color(color_hex: str) -> bool:
    try:
        ImageColor.getrgb(color_hex)
        return True
    except ValueError:
        return False

def colar1(image: Image.Image, color_hex: str) -> Image.Image:
    try:
        color = ImageColor.getrgb(color_hex)
        r_target, g_target, b_target = color[:3]

        if image.mode != 'RGBA':
            image = image.convert('RGBA')

        img_array = np.array(image, dtype=np.float32)
        r, g, b, a = img_array[:, :, 0], img_array[:, :, 1], img_array[:, :, 2], img_array[:, :, 3]
        
        luminance = (r * 0.299 + g * 0.587 + b * 0.114)
        max_lum = luminance.max()
        if max_lum > 0:
            luminance = luminance / max_lum

        mask = a > 0
        
        img_array[mask, 0] = r_target * luminance[mask]
        img_array[mask, 1] = g_target * luminance[mask]
        img_array[mask, 2] = b_target * luminance[mask]
        
        return Image.fromarray(np.clip(img_array, 0, 255).astype(np.uint8), 'RGBA')
    except Exception as e:
        raise ValueError(f"ошибко обработки изображения: {str(e)}")

async def process_single_image(image_path: Path, color_hex: str) -> bytes:
    loop = asyncio.get_running_loop()
    try:
        with Image.open(image_path) as img:
            colored_img = await loop.run_in_executor(
                thread_pool,
                lambda: colar1(img, color_hex)
            )
            
            output = BytesIO()
            await loop.run_in_executor(
                thread_pool,
                lambda: colored_img.save(
                    output, 
                    format='PNG', 
                    optimize=True, 
                    compress_level=9,
                    bits=8
                )
            )
            return output.getvalue()
    except Exception as e:
        print(f"ошибка обработки изображения {image_path.name}: {str(e)}")
        return await loop.run_in_executor(
            thread_pool,
            lambda: open(image_path, 'rb').read()
        )

async def process_all_images(color_hex: str) -> bytes:
    loop = asyncio.get_running_loop()
    output_zip = BytesIO()
    
    autohud_dir = Path("painting/photo/autohud")
    png_files = [f for f in autohud_dir.glob('*.png') if f.is_file()]
    
    if not png_files:
        raise ValueError("в папке autohud не найдено PNG файлов")
    
    with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as zip_out:
        tasks = []
        
        for img_file in png_files:
            tasks.append(process_single_image(img_file, color_hex))
        
        results = await asyncio.gather(*tasks)
        
        for img_file, img_data in zip(png_files, results):
            zip_out.writestr(img_file.name, img_data)
    
    return output_zip.getvalue()

def get_autohud_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="🎨 Палитра HEX цветов", url="https://csscolor.ru/")
    builder.adjust(1)
    return builder.as_markup()

@router.message(Command("autohud"))
async def autohud(message: Message, bot: Bot):
    if not await check_subscription(message, bot):
        return
    name = message.from_user.first_name
    args = message.text.split()
    
    if len(args) == 1:
        await message.answer(
            "<b>чтоб покрасить HUD-Авто введи -</b> <code>/autohud #FFFFFF</code>",
            reply_markup=get_autohud_keyboard(),
            parse_mode="HTML"
        )
        return
    
    try:
        color_hex = args[1].strip()
        if not await validate_hex_color(color_hex):
            raise ValueError("неверный формат HEX цвета, норм введи чтоб заработало.")
        
        processing_msg = await message.reply(f"<b>⏳ процесс идёт ок.</b>", parse_mode="HTML")
        zip_data = await process_all_images(color_hex)
        
        if len(zip_data) == 0:
            raise ValueError("произошла ошибко - не удалось обработать изображения")
        
        result_file = BufferedInputFile(zip_data, filename=f"autohud.zip")
        
        await message.reply_document(
            document=result_file,
            caption=f"<b>📊 файл готов</b>\n<b>📝 назва - autohud.zip</b>",
            parse_mode="HTML"
        )
        
    except ValueError as e:
        await message.answer(
            f"<b>ошибко: {str(e)}</b>",
            parse_mode="HTML"
        )
    except Exception as e:
        await message.answer(
            f"<b>произошла ошибко при обработке:</b> {str(e)}",
            parse_mode="HTML"
        )
    finally:
        if 'processing_msg' in locals():
            try:
                await processing_msg.delete()
            except Exception:
                pass