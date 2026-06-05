from aiogram import Router, F, Bot
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters import Command, Filter
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
import logging

router = Router()
CHANNEL_IDS_1 = ["@shouxsmods"]
CHANNEL_IDS_2 = ["@twizzmods"]
ADMIN_IDS = [7848157643]

async def answer_callback_silently(callback: CallbackQuery, text: str = None, show_alert: bool = False):
    try:
        await callback.answer(text, show_alert=show_alert)
    except TelegramBadRequest as e:
        if "query is too old" not in str(e):
            logging.warning(f"Callback error: {e}")

class IsSubscribed(Filter):
    async def __call__(self, message: Message, bot: Bot) -> bool:
        try:
            user_id = message.from_user.id
            
            if user_id in ADMIN_IDS:
                return True
                
            for channel in CHANNEL_IDS_1:
                chat_member = await bot.get_chat_member(channel, user_id)
                if chat_member.status not in ['creator', 'administrator', 'member']:
                    return False
            return True
            for channel in CHANNEL_IDS_2:
                chat_member = await bot.get_chat_member(channel, user_id)
                if chat_member.status not in ['creator', 'administrator', 'member']:
                    return False
            return True
            
        except Exception as e:
            logging.error(f"ошибко при проверке подписки: {e}")
            return False

async def check_subscription(message: Message | CallbackQuery, bot: Bot) -> bool:
    try:
        user = message.from_user
        user_id = user.id
        
        if user_id in ADMIN_IDS:
            return True
            
        for channel in CHANNEL_IDS_1:
            chat_member = await bot.get_chat_member(channel, user_id)
            if chat_member.status not in ['creator', 'administrator', 'member']:
                await show_subscription_request(message)
                return False
        return True
        for channel in CHANNEL_IDS_2:
            chat_member = await bot.get_chat_member(channel, user_id)
            if chat_member.status not in ['creator', 'administrator', 'member']:
                await show_subscription_request(message)
                return False
        return True
    except Exception as e:
        logging.error(f"ошибко проверки подписки: {e}")
        await show_subscription_request(message)
        return False

async def show_subscription_request(message: Message | CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="shouxs mods", url="https://t.me/shouxsmods")
    )
    builder.row(
        InlineKeyboardButton(text="проверить сабку", callback_data="check_subscription")
    )
    
    name = message.from_user.first_name
    text = (f"ничос, {name}! на онал сабнись ебать")

    if isinstance(message, CallbackQuery):
        try:
            await message.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode=ParseMode.HTML)
        except TelegramBadRequest:
            pass
    else:
        await message.answer(text, reply_markup=builder.as_markup(), parse_mode=ParseMode.HTML)

@router.message(F.text == "/start")
async def start(message: Message, bot: Bot):
    name = message.from_user.first_name
    is_subscribed = await IsSubscribed()(message, bot)
    
    if not is_subscribed:
        await show_subscription_request(message)
        return
    
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="конвертация", callback_data="conversion"),
        InlineKeyboardButton(text="редакторы", callback_data="editors")
    )
    builder.row(
        InlineKeyboardButton(text="покраска", callback_data="painting"),
        InlineKeyboardButton(text="нарезка", callback_data="cutting")
    )
    builder.row(
        InlineKeyboardButton(text="копирование", callback_data="copying")
    )
    
    text = (
        f"<b>ничос, {name}!</b>\n\n"
        f"<b>нах мне это надо бля, функции крч -</b>\n\n"
        f"<blockquote><b>конверт крч BTX                  конверт крч DFF</b></blockquote>\n"
        f"<blockquote><b>распаковкачэк TXD</b></blockquote>\n"
        f"<blockquote><b>можно открыть common BPC     конверт генрла крч BPCMETA</b></blockquote>\n"
        f"<blockquote><b>конверт крч DAT</b></blockquote>\n\n"
        f"<b>жми ниже чтоб узнать все о боте (порно контент)</b>"
    )
    
    await message.answer(
        text,
        reply_markup=builder.as_markup(),
        parse_mode=ParseMode.HTML
    )

@router.callback_query(F.data == "check_subscription")
async def check_subscription_callback(callback: CallbackQuery, bot: Bot):
    name = callback.from_user.first_name
    try:
        user_id = callback.from_user.id
        
        if user_id in ADMIN_IDS:
            await answer_callback_silently(callback, "одмин ок", show_alert=True)
            await callback.message.delete()
            
            builder = InlineKeyboardBuilder()
            builder.row(
                InlineKeyboardButton(text="конвертация", callback_data="conversion"),
                InlineKeyboardButton(text="редакторы", callback_data="editors")
            )
            builder.row(
                InlineKeyboardButton(text="покраска", callback_data="painting"),
                InlineKeyboardButton(text="нарезка", callback_data="cuting")
            )
            builder.row(
                InlineKeyboardButton(text="копирование", callback_data="copying")
            )
            
            text = (
                f"<b>ничос, {name}!</b>\n\n"
                f"<b>нах мне это надо бля, функции крч -</b>\n\n"
                f"<blockquote><b>конверт крч BTX    конверт крч DFF</b></blockquote>\n"
                f"<blockquote><b>конверт крч MP3     распаковкачэк TXD</b></blockquote>\n"
                f"<blockquote><b>можно открыть common BPC     конверт крч BPCMETA</b></blockquote>\n"
                f"<blockquote><b>конверт крч DAT</b></blockquote>\n\n"
                f"<b>жми ниже чтоб узнать все о боте (порно контент)</b>"
            )
            
            await callback.message.answer(text, reply_markup=builder.as_markup(), parse_mode=ParseMode.HTML)
            return
            
        not_subscribed = []
        for channel in CHANNEL_IDS:
            chat_member = await bot.get_chat_member(channel, user_id)
            if chat_member.status not in ['creator', 'administrator', 'member']:
                not_subscribed.append(channel)
        
        if not not_subscribed:
            await answer_callback_silently(callback, "ебать на онал сабнулся браточэк", show_alert=True)
            await callback.message.delete()
            
            builder = InlineKeyboardBuilder()
            builder.row(
                InlineKeyboardButton(text="конвертация", callback_data="conversion"),
                InlineKeyboardButton(text="редакторы", callback_data="editors")
            )
            builder.row(
                InlineKeyboardButton(text="покраска", callback_data="painting"),
                InlineKeyboardButton(text="нарезка", callback_data="cutting")
            )
            builder.row(
                InlineKeyboardButton(text="копирование", callback_data="copying")
            )
            
            await callback.message.answer(
                f"<b>ничос, {name}!</b>\n\n"
                f"<b>нах мне надо бля, функции крч -</b>\n\n"
                f"<blockquote><b>конверт крч BTX    конверт крч DFF</b></blockquote>\n"
                f"<blockquote><b>конверт крч MP3     распаковкачэк TXD</b></blockquote>\n"
                f"<blockquote><b>можно открыть common BPC     конверт генрла крч BPCMETA</b></blockquote>\n"
                f"<blockquote><b>конверт крч DAT</b></blockquote>\n\n"
                f"<b>жми ниже чтоб узнать все о боте (порно контент)</b>",
                reply_markup=builder.as_markup(),
                parse_mode=ParseMode.HTML
            )
        else:
            await answer_callback_silently(callback, "если не сабнулся, сабнис нах", show_alert=True)
            await show_subscription_request(callback)
            
    except Exception as e:
        logging.error(f"ошибко при проверке подписки: {e}")
        await answer_callback_silently(callback, "cнова старт нажми.", show_alert=True)

@router.callback_query(F.data == "conversion")
async def conversion_menu(callback: CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔙 назад", callback_data="back_start")
    )
    
    await callback.message.edit_text(
        f"<b>конверт :</b>\n\n"
        f"<b>❌ BTX ⇄ PNG</b>\n"
        f"<b>🚶‍♂️ IFP ⇄ ANI</b>\n"
        f"<b>🕴 MOD ⇄ DFF</b>\n"
        f"<b>💭 DAT ⇄ JSON</b>\n"
        f"<b>✅ конвертация поддерживается с ZIP архивами!</b>\n"
        f"<b>🗂 прост кидай мне файлы (кучка говна), а я конвертирую</b>",
        reply_markup=builder.as_markup(),
        parse_mode=ParseMode.HTML
    )
    await answer_callback_silently(callback)

@router.callback_query(F.data == "editors")
async def editors_menu(callback: CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔙 назад", callback_data="back_start")
    )
    
    await callback.message.edit_text(
        f"<b>редактор файлов :</b>\n\n"
        f"<b>⛅ /timecyc - редактор таймкук</b>\n"
        f"<b>🌑 /colorcyc - редактор колоркук</b>\n"
        f"<b>🩸 /blood - редактор партикла</b>\n"
        f"<b>🔫 /weapon - редактор веапона. (p.s устарел)</b>\n"
        f"<b>📤 /id - получить name, id, texture, mod (p.s не работает)</b>\n"
        f"<b>🗂 просто кидай мне файл (кучка говна) с описанием команды, а я конвертирую</b>",
        reply_markup=builder.as_markup(),
        parse_mode=ParseMode.HTML
    )
    await answer_callback_silently(callback)

@router.callback_query(F.data == "painting")
async def painting_menu(callback: CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔙 назад", callback_data="back_start")
    )
    
    await callback.message.edit_text(
        f"<b>🎨 покраска файлов :</b>\n\n"
        f"<b>🖌 /hp - покраска HUD-Элементов</b>\n"
        f"<b>🖌 /hud - покраска HUD</b>\n"
        f"<b>🕸 /button - покраска кнопок</b>\n"
        f"<b>🌲 /listva - покрасить листву</b>\n"
        f"<b>🚘 /autohud - покрасить HUD-Авто</b>\n"
        f"<b>🖌 /hudnew -покрасить новый HUD</b>\n"
        f"<b>🛑 /roadsigns - покраска дорожных знаков</b>\n"
        f"<b>🎯 /aim - покраска прицела</b>\n"
        f"<b>🌃 /filter - применение фильтра</b>\n"
        f"<b>🪄 /color - покраска изображений</b>\n"
        f"<b>🗂 прост кидай мне файл (кучка говна) с описанием команды, а я конвертирую</b>",
        reply_markup=builder.as_markup(),
        parse_mode=ParseMode.HTML
    )
    await answer_callback_silently(callback)

@router.callback_query(F.data == "cutting")
async def cutting_menu(callback: CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔙 назад", callback_data="back_start")
    )
    
    await callback.message.edit_text(
        f"<b>✂️ нарезка файлов :</b>\n\n"
        f"<b>🔪 /hudcut - нарезать HUD</b>\n"
        f"<b>🗂 прост кидай мне файл (кучка говна) с описанием /hudcut, а я конвертирую</b>",
        reply_markup=builder.as_markup(),
        parse_mode=ParseMode.HTML
    )
    await answer_callback_silently(callback)

@router.callback_query(F.data == "copying")
async def copying_menu(callback: CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔙 назад", callback_data="back_start")
    )
    
    await callback.message.edit_text(
        f"<b>🗳 копирование файлов :</b>\n\n"
        f"<b>🧰 /bild - копирование билдбордов</b>\n"
        f"<b>🧰 /logo - копирование логотипов</b>\n"
        f"<b>🗂 прост кидай мне файл (кучка говна) с описанием /logo или /bild, а я конвертирую</b>",
        reply_markup=builder.as_markup(),
        parse_mode=ParseMode.HTML
    )
    await answer_callback_silently(callback)

@router.callback_query(F.data == "back_start")
async def back_to_start(callback: CallbackQuery, bot: Bot):
    name = callback.from_user.first_name
    is_subscribed = await IsSubscribed()(callback, bot)
    
    if not is_subscribed:
        await show_subscription_request(callback)
        return
    
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="конвертация", callback_data="conversion"),
        InlineKeyboardButton(text="редакторы", callback_data="editors")
    )
    builder.row(
        InlineKeyboardButton(text="покраска", callback_data="painting"),
        InlineKeyboardButton(text="нарезка", callback_data="cutting")
    )
    builder.row(
        InlineKeyboardButton(text="копирование", callback_data="copying")
    )
    
    text = (
        f"<b>ничос, {name}!</b>\n\n"
        f"<b>нах мне это надо бля, функции крч -</b>\n\n"
        f"<blockquote><b>конверт крч BTX (p.s не работает)                  конверт крч DFF</b></blockquote>\n"
        f"<blockquote><b>распаковкачэк TXD</b></blockquote>\n"
        f"<blockquote><b>можно открыть common BPC     конверт крч генрла BPCMETA</b></blockquote>\n"
        f"<blockquote><b>конверт крч DAT</b></blockquote>\n\n"
        f"<b>жми ниже чтоб узнать все о боте (порно контент)</b>"
    )
    
    await callback.message.edit_text(
        text,
        reply_markup=builder.as_markup(),
        parse_mode=ParseMode.HTML
    )
    await answer_callback_silently(callback)