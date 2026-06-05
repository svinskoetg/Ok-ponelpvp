from aiogram import Router, Bot
from aiogram.types import Message, InlineKeyboardButton, FSInputFile, CallbackQuery
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types.web_app_info import WebAppInfo
from aiogram.enums.parse_mode import ParseMode
import tempfile
import os
from start.start import check_subscription

router = Router()

@router.message(Command("timecyc"))
async def timecyc(message: Message, bot: Bot):
    if not await check_subscription(message, bot):
        return
    name = message.from_user.first_name
    if message.text == "/timecyc":
        kb = InlineKeyboardBuilder()
        kb.row(InlineKeyboardButton(text="🎨 палитра HEX цветов", url="https://csscolor.ru"))
        
        msg = await message.answer(
            f"<b>Чтобы создать цвета неба введите -</b> <code>/timecyc #FFFF00 #FFFFFF #FF7642 #FFFF74</code>",
            parse_mode=ParseMode.HTML,
            reply_markup=kb.as_markup()
        )
        return

    try:
        progress_msg = await message.reply(f"<b>⏳ процесс идёт ок.</b>", parse_mode=ParseMode.HTML)
        colors = message.text.split()[1:]
        if len(colors) != 4:
            await message.reply(f"<b>введи ток 4 HEX цвета!</b>", parse_mode="HTML")
            return
        
        color_values = []
        for clr in colors:
            if not clr.startswith("#") or len(clr) != 7:
                await message.reply(f"Неправильный HEX цвет - {clr}</b>", parse_mode="HTML")
                return
            try:
                int(clr[1:], 16)
                color_values.append(tuple(int(clr[i:i+2], 16) for i in (1, 3, 5)))
            except ValueError:
                await message.reply(f"<b>цвет {clr} содержит недопустимые символы (только 0-9, A-F)!</b>", parse_mode="HTML")
                return
        
        with open('Editing/isx/timecyc.json', 'r', encoding='utf-8') as f:
            tmpl = f.read()
        
        replacements = {
            'skbr': color_values[0][0], 'skbg': color_values[0][1], 'skbb': color_values[0][2],
            'sktr': color_values[1][0], 'sktg': color_values[1][1], 'sktb': color_values[1][2],
            'scr': color_values[2][0], 'scg': color_values[2][1], 'scb': color_values[2][2],
            'clr': color_values[3][0], 'clg': color_values[3][1], 'clb': color_values[3][2]
        }
        
        for k, v in replacements.items():
            tmpl = tmpl.replace(k, str(v))
        
        with tempfile.NamedTemporaryFile(mode='w+', suffix='.json', delete=False, encoding='utf-8') as tmp:
            tmp.write(tmpl)
            tmp_path = tmp.name
        
        await message.reply_document(
            FSInputFile(tmp_path, filename='timecyc.json'),
            caption=f'<b>📊 файл готов</b>\n<b>📝 назва - timecyc.json</b>',
            parse_mode=ParseMode.HTML
        )
        await progress_msg.delete()
        os.remove(tmp_path)
        
    except Exception as e:
        await message.reply(
            f"произошла непредвиденная ошибко - </b>\n<code>{str(e)}</code>",
            parse_mode=ParseMode.HTML
        )