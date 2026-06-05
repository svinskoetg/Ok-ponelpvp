import zipfile
from io import BytesIO
from pathlib import Path
import numpy as np
import asyncio
from PIL import Image, ImageColor
from aiogram import Router, F, Bot
from aiogram.types import Message, BufferedInputFile, CallbackQuery
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.enums import ParseMode
from start.start import check_subscription

router = Router()

hp = Path("painting/photo/hp")
image = [
    "hud_ruble.png",
    "hud_heart.png",
    "hud_health_scale.png",
    "hud_armor_scale.png",
    "hud_armor.png"
]

def colar73(image: Image.Image, color_hex: str) -> Image.Image:
    try:
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
    except Exception as e:
        raise ValueError(f"<b>произошла непредвиденная ошибко обработки изображения - {str(e)}</b>")

async def process_hp_image(image_path: Path, color_hex: str) -> bytes:
    try:
        with Image.open(image_path) as img:
            colored_img = colar73(img, color_hex)
            output = BytesIO()
            colored_img.save(output, format='PNG', optimize=True)
            return output.getvalue()
    except Exception:
        with open(image_path, 'rb') as f:
            return f.read()

def get_hp_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="🎨 палитра HEX цветов", url="https://csscolor.ru/")
    builder.adjust(1)
    return builder.as_markup()

@router.message(Command("hp"))
async def hp_command(message: Message, bot: Bot):
    if not await check_subscription(message, bot):
        return
    name = message.from_user.first_name
    args = message.text.split()
    
    if len(args) == 1:
        await message.answer(
            f"<b>чтобы покрасить HUD-Элементы введи -</b> <code>/hp #FFFFFF</code>",
            reply_markup=get_hp_keyboard(),
            parse_mode=ParseMode.HTML
        )
        return
    
    progress_msg = await message.reply(f"<b>⏳ процесс идёт ок.</b>", parse_mode=ParseMode.HTML)
    
    try:
        color_hex = args[1].strip()
        ImageColor.getrgb(color_hex)
        
        zip_data = await process_hp_images(color_hex)
        
        if len(zip_data) == 0:
            raise ValueError("не удалось обработать ни одного изображения")
        
        result_file = BufferedInputFile(zip_data, filename=f"hp.zip")
        
        await message.reply_document(
            document=result_file,
            caption=f"<b>📊 файл готов</b>\n<b>📝 назва - hp.zip</b>",
            parse_mode=ParseMode.HTML
        )
        
    except ValueError as e:
        error_msg = f"<b>ошибко: {str(e)}</b>"
        await progress_msg.edit_text(error_msg, parse_mode=ParseMode.HTML)
        await asyncio.sleep(5)
    except Exception as e:
        error_msg = f"<b>произошла ошибко: {str(e)}</b>"
        await progress_msg.edit_text(error_msg, parse_mode=ParseMode.HTML)
        await asyncio.sleep(5)
    finally:
        try:
            await progress_msg.delete()
        except:
            pass

async def process_hp_images(color_hex: str) -> bytes:
    output_zip = BytesIO()
    processed_count = 0
    
    with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as zip_out:
        for hp_file in image:
            image_path = hp / hp_file
            if image_path.exists():
                try:
                    processed_data = await process_hp_image(image_path, color_hex)
                    zip_out.writestr(hp_file, processed_data)
                    processed_count += 1
                except Exception as e:
                    print(f"ошибко при обработке {hp_file}: {str(e)}")
                    continue
    
    if processed_count == 0:
        raise ValueError("не найдено файлов для обработки или все обработки завершились ошибкой")
    
    return output_zip.getvalue()