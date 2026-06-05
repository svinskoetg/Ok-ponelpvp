import os
import shutil
import aiohttp
import aiofiles
import tempfile
import asyncio
import zipfile
from io import BytesIO
from pathlib import Path
from aiogram import F, Router, types, Bot
from aiogram.types import BufferedInputFile
from aiogram.enums import ParseMode
from start.start import check_subscription


router = Router()

async def fetch_server_names():
    url = "https://api.blackrussia.online/servers.json"
    headers = {"User-Agent": "MOl9ISIvsVFgqqVgDIBpVmf"}
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            if response.status == 200:
                data = await response.json()
                return [f"logobr{server.get('firstname', '').lower()}.btx" for server in data if server.get("firstname")]
            raise Exception("<b>⚠️ ошибка при получении данных серверов</b>")

@router.message(F.text == "/logo")
async def logo_command(message: types.Message, bot: Bot):
    if not await check_subscription(message, bot):
        return
    name = message.from_user.first_name
    msg = await message.answer(
        f"<b>чтоб создать кастомные логотипы кидай - <code>/logo</code> + BTX файл</b>",
        parse_mode=ParseMode.HTML
    )

async def create_zip(input_file_path: str, server_names: list) -> bytes:
    zip_buffer = BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
        async with aiofiles.open(input_file_path, 'rb') as f:
            content = await f.read()
            for server_name in server_names:
                zipf.writestr(server_name, content)
    
    return zip_buffer.getvalue()

@router.message(F.document & F.caption == "/logo")
async def logo_xyina(message: types.Message, bot: Bot):
    if not await check_subscription(message, bot):
        return
    name = message.from_user.first_name

    if not message.document.file_name.lower().endswith('.btx'):
        return await message.reply("<b>❌ нужен файл формата .btx!</b>", parse_mode=ParseMode.HTML)

    temp_dir = tempfile.mkdtemp(prefix="logo_")
    try:
        progress_msg = await message.reply(f"<b>⏳ процесс идет ок.</b>", parse_mode=ParseMode.HTML)
        file = await bot.get_file(message.document.file_id)
        input_file = os.path.join(temp_dir, "input.btx")
        
        file_content = await bot.download_file(file.file_path)
        async with aiofiles.open(input_file, 'wb') as f:
            await f.write(file_content.read()) 
        
        server_names = await fetch_server_names()
        
        zip_data = await create_zip(input_file, server_names)
        
        await message.reply_document(
            BufferedInputFile(zip_data, "logo.zip"),
            caption=f"<b>📊 файл готов</b>\n<b>📝 назва - logo.zip</b>",
            parse_mode=ParseMode.HTML
        )
        await progress_msg.delete()
            
    except Exception as e:
        await message.reply(f"<b>⚠️ ошибко:</b> {str(e)}", parse_mode=ParseMode.HTML)
    finally:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)

async def cleanup_temp_dirs():
    temp_dir = Path(tempfile.gettempdir())
    for dir_path in temp_dir.glob("logo_*"):
        try:
            shutil.rmtree(dir_path, ignore_errors=True)
        except Exception:
            pass