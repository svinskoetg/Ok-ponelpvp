from aiogram import Router, types, Bot
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile, CallbackQuery
from aiogram.enums import ParseMode
from start.start import check_subscription


router = Router()

@router.message(Command("blood"))
async def blood(message: types.Message, bot: Bot):
    if not await check_subscription(message, bot):
        return
    if message.text is None:
        await message.answer("гондон, кинь команду текстовым сообщением окэй.")
        return
        
    name = message.from_user.first_name
    args = message.text.split()
    
    if len(args) == 1:
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🎨 палитра HEX цветов", url="https://csscolor.ru/")]
            ]
        )
        await message.answer(
            f"<b>чтоб создать партикл введи -</b> <code>/blood #FFFF00</code> | <code>/blood #FFFF00 1.5</code>",
            reply_markup=kb,
            parse_mode=ParseMode.HTML
        )
        return

    try:
        progress_msg = await message.reply(f"<b>⏳ процесс идёт ок.</b>", parse_mode=ParseMode.HTML)
        
        hex_color = args[1].lstrip('#')
        if len(hex_color) != 6:
            await message.answer(f"<b>Вводите #HEX цвет!</b>", parse_mode=ParseMode.HTML)
            await progress_msg.delete()
            return
        
        rgb = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        size = float(args[2]) if len(args) > 2 else 1.01

        config_path = 'Editing/isx/particle.cfg'
        
        with open(config_path, 'r') as f:
            cfg_lines = f.readlines()

        updated_lines = []
        found_blood = False

        for line in cfg_lines:
            if line.strip().startswith("BLOOD"):
                found_blood = True
                parts = [p for p in line.replace('\t', ' ').split(' ') if p]
                
                parts[1:4] = [str(rgb[0]), str(rgb[1]), str(rgb[2])]
                parts[9] = f"{size:.3f}"
                
                updated_line = "\t".join(parts) + "\n"
                updated_lines.append(updated_line)
            else:
                updated_lines.append(line)

        if not found_blood:
            await message.answer("<b>❌ ошибко:</b> Секция BLOOD не найдена в конфигурационном файле", parse_mode=ParseMode.HTML)
            await progress_msg.delete()
            return

        temp_config = "".join(updated_lines)
        temp_file = BufferedInputFile(temp_config.encode(), filename="particle.cfg")
        
        await message.reply_document(
            temp_file,
            caption=f"<b>📊 файл готов</b>\n<b>📝 назва - particle.cfg</b>",
            parse_mode=ParseMode.HTML
        )
        
        await progress_msg.delete()

    except ValueError:
        await message.answer(f"<b>кажется ты допустил ошибку в параметрах! гандон</b>", parse_mode=ParseMode.HTML)
        if 'progress_msg' in locals():
            await progress_msg.delete()