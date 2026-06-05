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

button = Path("painting/photo/button")
image = [
    "accelerate.png", "baton_widget.png", "brake.png", "cam-toggle.png", 
    "crane_down.png", "crane_top.png", "fadeinbox.png", "handbrake.png", 
    "helpin_widget.png", "horn.png", "hud_bike.png", "hud_boat.png", 
    "hud_car.png", "hud_chopper.png", "hud_circle.png", "hud_dildo1.png", 
    "hud_dildo2.png", "hud_dive.png", "hud_left.png", "hud_lockon.png", 
    "hud_monstertruck.png", "hud_nitro.png", "hud_plane.png", "hud_right.png", 
    "hud_swim.png", "hud_tank_left.png", "hud_tank_right.png", "hud_trailer.png", 
    "hydraulicCar.png", "menu_down.png", "menu_up.png", "nbaton_widget.png", 
    "off_micro.png", "punch.png", "shoot.png", "speedo_lwidget.png", 
    "sprint.png", "WhiteCircle.png", "WidgetGetIn.png"
]

def colar2(image: Image.Image, color_hex: str) -> Image.Image:
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
        raise ValueError(f"произошла непредвиденная ошибко обработки изображения - {str(e)}")

async def process_button_image(image_path: Path, color_hex: str) -> bytes:
    try:
        with Image.open(image_path) as img:
            colored_img = colar2(img, color_hex)
            output = BytesIO()
            colored_img.save(output, format='PNG', optimize=True, compress_level=3)
            return output.getvalue()
    except Exception:
        with open(image_path, 'rb') as f:
            return f.read()

async def process_all_buttons(color_hex: str) -> bytes:
    output_zip = BytesIO()
    processed_files = 0
    
    with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as zip_out:
        for button_file in image:
            image_path = button / button_file
            if image_path.exists():
                try:
                    processed_data = await process_button_image(image_path, color_hex)
                    zip_out.writestr(button_file, processed_data)
                    processed_files += 1
                except Exception as e:
                    print(f"Ошибка обработки {button_file}: {str(e)}")
                    continue
    
    if processed_files == 0:
        raise ValueError("не удалось обработать ни одного файла")
    
    return output_zip.getvalue()

def get_button_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="🎨 палитра HEX цветов", url="https://csscolor.ru/")
    builder.adjust(1)
    return builder.as_markup()

@router.message(Command("button"))
async def button_command(message: Message, bot: Bot):
    if not await check_subscription(message, bot):
        return
    name = message.from_user.first_name
    args = message.text.split()
    
    if len(args) == 1:
        await message.reply(
            f"<b>чтоб покрасить кнопки введи -</b> <code>/button #FFFFFF</code>",
            reply_markup=get_button_keyboard(),
            parse_mode=ParseMode.HTML
        )
        return
    
    progress_msg = None
    try:
        progress_msg = await message.reply(f"<b>⏳ процесс идёт ок.</b>", parse_mode=ParseMode.HTML)
        
        color_hex = args[1].strip()
        ImageColor.getrgb(color_hex)
        
        zip_data = await process_all_buttons(color_hex)
        
        if len(zip_data) == 0:
            raise ValueError("не найдены файлы для обработки")
        
        result_file = BufferedInputFile(zip_data, filename=f"button.zip")
        
        await message.reply_document(
            document=result_file,
            caption=f"<b>📊 файл готов</b>\n<b>📝 назва - button.zip</b>",
            parse_mode=ParseMode.HTML
        )
        
    except ValueError as e:
        error_msg = f"<b>ошибко: {str(e)}</b>"
        if progress_msg:
            await progress_msg.edit_text(error_msg, parse_mode=ParseMode.HTML)
            await asyncio.sleep(5)
        else:
            await message.reply(error_msg, parse_mode=ParseMode.HTML)
    except Exception as e:
        error_msg = f"<b>произошла ошибко: {str(e)}</b>"
        print(f"ошибко в button_command: {e}")
        if progress_msg:
            await progress_msg.edit_text(error_msg, parse_mode=ParseMode.HTML)
            await asyncio.sleep(5)
        else:
            await message.reply(error_msg, parse_mode=ParseMode.HTML)
    finally:
        if progress_msg:
            try:
                await progress_msg.delete()
            except Exception as e:
                print(f"ошибко при удалении progress_msg: {e}")