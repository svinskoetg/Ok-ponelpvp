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
from start.start import check_subscription

router = Router()

AIM_FOLDER = Path("painting/photo/aim")

def get_aim_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="🎨 палитра HEX цветов", url="https://csscolor.ru/")
    builder.adjust(1)
    return builder.as_markup()

def colar(image: Image.Image, color_hex: str) -> Image.Image:
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

async def process_aim_image(color_hex: str) -> bytes:
    for file in AIM_FOLDER.glob("*.png"):
        with Image.open(file) as img:
            colored_img = colar(img, color_hex)
            output = BytesIO()
            colored_img.save(output, format='PNG', optimize=True)
            return output.getvalue()
    raise FileNotFoundError("в папке aim/aim нет PNG файлов")

@router.message(Command("aim"))
async def aim(message: Message, bot: Bot):
    if not await check_subscription(message, bot):
        return
    args = message.text.split()
    name = message.from_user.first_name
    
    if len(args) == 1:
        await message.answer(
            "<b>чтобы покрасить прицел введи -</b> <code>/aim #FFFFFF</code>",
            reply_markup=get_aim_keyboard(),
            parse_mode=ParseMode.HTML
        )
        return

    try:
        progress_msg = await message.reply(f"<b>⏳ процесс идёт ок.</b>", parse_mode=ParseMode.HTML)
        
        color_hex = args[1].strip()
        ImageColor.getrgb(color_hex)
        
        image_data = await process_aim_image(color_hex)
        result_file = BufferedInputFile(image_data, filename="siteM16.png")
        
        await message.reply_document(
            document=result_file,
            caption=f"<b>📊 файл готов</b>\n<b>📝 назва - siteM16.png</b>",
            parse_mode=ParseMode.HTML
        )
        
    except ValueError:
        await progress_msg.edit_text(
            f"<b>похоже HEX-код неправильный, норм введи чтоб заработал.</b>",
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