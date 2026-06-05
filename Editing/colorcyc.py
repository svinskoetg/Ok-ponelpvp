from aiogram import Router, Bot
from aiogram.types import Message, InlineKeyboardButton, FSInputFile, CallbackQuery
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.enums.parse_mode import ParseMode
import os
from start.start import check_subscription

router = Router()

def get_main_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="🎨 палитра HEX цветов",
        url="http://csscolor.ru"
    ))
    return builder.as_markup()

async def send_error_message(message: Message):
    name = message.from_user.first_name
    await message.answer(
        f"<b>неправильный формат ввода!</b>",
        reply_markup=get_main_keyboard(),
        parse_mode=ParseMode.HTML
    )

@router.message(Command("colorcyc")) 
async def colorcyc(message: Message, bot: Bot):
    if not await check_subscription(message, bot):
        return
    name = message.from_user.first_name
    
    if len(message.text.split()) < 2:
        await message.answer(
            f"<b>чтоб создать колоркук, введите -</b> <code>/colorcyc #FFFFFF</code> <b>|</b> <code>/colorcyc 0.9</code>",
            reply_markup=get_main_keyboard(),
            parse_mode=ParseMode.HTML
        )
        return

    color_param = message.text.split()[1]
    
    if color_param.startswith('#'):
        if len(color_param) != 7:
            await send_error_message(message)
            return
            
        try:
            hex_color = color_param[1:]
            rgb = (
                int(hex_color[0:2], 16) / 255,
                int(hex_color[2:4], 16) / 255,
                int(hex_color[4:6], 16) / 255
            )
            rgb_values = [round(val, 3) for val in rgb]
            
        except ValueError:
            await send_error_message(message)
            return
            
    elif color_param.replace('.', '').isdigit() or '/' in color_param:
        try:
            if '/' in color_param:
                num1, num2 = color_param.split('/')
                value1 = float(num1)
                value2 = float(num2)
                rgb_values = [value1, value2, value2]
            else:
                value = float(color_param)
                rgb_values = [value, value, value]
                
        except (ValueError, IndexError):
            await send_error_message(message)
            return
            
    else:
        await send_error_message(message)
        return
        
    dat = "colorcycle.dat"        
    
    try:
        progress_msg = await message.reply(f"<b>⏳ процесс идёт ок.</b>", parse_mode=ParseMode.HTML)
        with open('Editing/isx/colorcyc.dat', 'r') as file:
            data = file.read()
            data = data.replace('r', str(rgb_values[0])) \
                      .replace('g', str(rgb_values[1])) \
                      .replace('b', str(rgb_values[2]))
            
            with open(dat, 'w') as file:
                file.write(data)
                
        await message.reply_document(
            FSInputFile(dat),
            caption=f"<b>📊 файл готов</b>\n<b>📝 назва - colorcycle.dat</b>",
            parse_mode=ParseMode.HTML
        )
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
        if os.path.exists(dat):
            os.remove(dat)