from aiogram import Bot, types, F, Router
from aiogram.filters import Command
from aiogram.types import Message, BufferedInputFile, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.enums import ParseMode
from PIL import Image, ImageOps
import io
import asyncio
from start.start import check_subscription

router = Router()

async def filters(img: Image.Image, filter_name: str) -> Image.Image:
    if filter_name == "red":
        r, g, b = img.split()
        r = r.point(lambda x: min(x * 1.5, 255))
        return Image.merge("RGB", (r, g, b))
    elif filter_name == "green":
        r, g, b = img.split()
        g = g.point(lambda x: min(x * 1.5, 255))
        return Image.merge("RGB", (r, g, b))
    elif filter_name == "blue":
        r, g, b = img.split()
        b = b.point(lambda x: min(x * 1.5, 255))
        return Image.merge("RGB", (r, g, b))
    elif filter_name == "grayscale":
        return img.convert("L").convert("RGB")
    elif filter_name == "negate":
        return ImageOps.invert(img.convert("RGB"))
    elif filter_name == "sepia":
        sepia = img.convert("RGB")
        pixels = sepia.load()
        for y in range(sepia.size[1]):
            for x in range(sepia.size[0]):
                r, g, b = pixels[x, y]
                tr = int(0.393 * r + 0.769 * g + 0.189 * b)
                tg = int(0.349 * r + 0.686 * g + 0.168 * b)
                tb = int(0.272 * r + 0.534 * g + 0.131 * b)
                pixels[x, y] = (min(tr, 255), min(tg, 255), min(tb, 255))
        return sepia
    elif filter_name == "solarize":
        return ImageOps.solarize(img.convert("RGB"), threshold=128)
    return img

@router.message(Command("filter"))
async def filter(message: Message, bot: Bot):
    if not await check_subscription(message, bot):
        return
    name = message.from_user.first_name
    
    if not (message.photo or (message.document and message.document.mime_type in ["image/jpeg", "image/png"])):
        await message.answer(
            f"<b>чтоб применить цветной фильтр к твоему изображению кидай -</b> "
            "<code>/filter grayscale</code> <b>+ PNG, JPG, JPEG</b>",
            parse_mode=ParseMode.HTML
        )
        return
        

    await process_filters(message, bot)

async def process_filters(message: Message, bot: Bot):
    name = message.from_user.first_name
    
    try:
        args = message.caption.split()
        if len(args) < 2:
            await message.reply(f"<b>Укажите Фильтр!</b>", parse_mode=ParseMode.HTML)
            return
            
        filter_name = args[1].lower()
        valid_filters = ["red", "green", "blue", "grayscale", "negate", "sepia", "solarize"]
        
        if filter_name not in valid_filters:
            await message.reply(f"<b>похоже вводишь неизвестный фильтр. Доступные фильтры - {', '.join(valid_filters)}</b>", parse_mode=ParseMode.HTML)
            return
        
        progress_msg = await message.reply(f"<b>⏳ процесс идёт ок.</b>", parse_mode=ParseMode.HTML)
        
        if message.photo:
            file_id = message.photo[-1].file_id
        else:
            file_id = message.document.file_id
        
        file = await bot.get_file(file_id)
        file_bytes = await bot.download_file(file.file_path)
        
        img = Image.open(io.BytesIO(file_bytes.read()))
        processed_img = await filters(img, filter_name)
        
        img_byte_arr = io.BytesIO()
        processed_img.save(img_byte_arr, format='PNG')
        img_byte_arr.seek(0)
        
        await message.reply_document(
            BufferedInputFile(img_byte_arr.getvalue(), filename=f"shouxs.{filter_name}.png"),
            caption=f"<b>📊 файл готов</b>\n<b>📝 назва - shouxs.{filter_name}.png</b>",
            parse_mode=ParseMode.HTML
        )
        
        await progress_msg.delete()
        
    except Exception as e:
        error_msg = await message.reply(f"<b>ошибко: {str(e)}</b>", parse_mode=ParseMode.HTML)
        await asyncio.sleep(5)
        await error_msg.delete()
        if 'progress_msg' in locals():
            await progress_msg.delete()