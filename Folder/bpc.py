import os
import zipfile
import tempfile
import asyncio
import re
from shutil import rmtree
from aiogram import Bot, types, Router, F
from aiogram.types import FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.enums import ParseMode
from start.start import check_subscription


def setup_bpc(bot: Bot):
    router = Router(name="bpc")
    file_lock = asyncio.Lock()

    def read_file_bytes(file_path):
        with open(file_path, 'rb') as f:
            return bytearray(f.read())

    def write_bytes_to_file(file_path, data):
        with open(file_path, 'wb') as f:
            f.write(data)

    def detect_key_pattern(encrypted_data):
        signatures = {
            'ZIP': b'PK',
            'PNG': b'\x89PNG',
            'JPEG': b'\xFF\xD8\xFF',
            'GIF': b'GIF',
            'PDF': b'%PDF'
        }
        
        for key_len in [20, 16, 32, 8, 4]:
            test_key = bytearray()
            for i in range(key_len):
                for sig_type, sig_bytes in signatures.items():
                    if i < len(sig_bytes):
                        test_key.append(encrypted_data[i] ^ sig_bytes[i])
            
            if test_key:
                test_decrypted = bytes([encrypted_data[i] ^ test_key[i % len(test_key)] 
                                     for i in range(min(100, len(encrypted_data)))])
                
                for sig_type, sig_bytes in signatures.items():
                    if test_decrypted.startswith(sig_bytes):
                        return test_key
        
        return bytes.fromhex('31 63 4b 31 61 35 55 46 32 74 55 38 2a 47 32 6c 57 23 26 25')

    def is_valid_filename(filename):
        pattern = r'(common|wirhub\.common|common\s*\(\d+\))'
        return (
            re.search(pattern, filename, re.IGNORECASE) is not None and
            filename.lower().endswith(('.zip', '.bpc'))
        )

    @router.message(F.document & F.document.file_name.func(is_valid_filename))
    async def handle_valid_files(message: types.Message, bot: Bot):
        if not await check_subscription(message, bot):
            return
        name = message.from_user.first_name

        progress_msg = await message.reply(f"<b>⏳ конверт идет ок.</b>", parse_mode="HTML")
        
        try:
            if message.document.file_name.lower().endswith('.bpc'):
                await process_bpc_file(message.document, message)
            elif message.document.file_name.lower().endswith('.zip'):
                await process_zip_file(message.document, message)
        except Exception as e:
            name = message.from_user.first_name
            await progress_msg.edit_text(f"<b>Произошла ошибко: {str(e)}</b>")
        finally:
            await asyncio.sleep(5)
            try:
                await progress_msg.delete()
            except:
                pass

    async def process_bpc_file(file: types.Document, message: types.Message):
        async with file_lock:
            temp_dir = os.path.join(tempfile.gettempdir(), f"bpc_{message.from_user.id}")
            os.makedirs(temp_dir, exist_ok=True)
            
            try:
                file_path = os.path.join(temp_dir, file.file_name)
                await bot.download(file, destination=file_path)
                
                decrypted_file = os.path.join(temp_dir, "decrypted_file")
                encrypted = read_file_bytes(file_path)
                xor_key = detect_key_pattern(encrypted)
                
                decrypted = bytearray()
                for i in range(len(encrypted)):
                    decrypted.append(encrypted[i] ^ xor_key[i % len(xor_key)])
                
                write_bytes_to_file(decrypted_file, decrypted)
                
                if zipfile.is_zipfile(decrypted_file):
                    content_dir = os.path.join(temp_dir, "content")
                    os.makedirs(content_dir, exist_ok=True)
                    
                    with zipfile.ZipFile(decrypted_file, 'r') as zip_ref:
                        zip_ref.extractall(content_dir)
                    
                    zip_filename = f"common.zip"
                    zip_path = os.path.join(temp_dir, zip_filename)
                    
                    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                        for root, _, files in os.walk(content_dir):
                            for file in files:
                                file_path = os.path.join(root, file)
                                arcname = os.path.relpath(file_path, content_dir)
                                zipf.write(file_path, arcname)
                    
                    name = message.from_user.first_name            
                    await message.answer_document(
                        FSInputFile(zip_path),
                        caption=f"<b>📊 все норм с файлом</b>\n<b>📝 название - common.zip</b>",
                        parse_mode=ParseMode.HTML
                    )
                    name = message.from_user.first_name                
                else:
                    await message.answer_document(
                        FSInputFile(decrypted_file),
                        caption=f"<b>📊 все норм с файлом</b>\n<b>📝 название - common.zip</b>",
                        parse_mode=ParseMode.HTML
                    )
                    
            finally:
                if os.path.exists(temp_dir):
                    rmtree(temp_dir, ignore_errors=True)

    async def process_zip_file(file: types.Document, message: types.Message):
        async with file_lock:
            temp_dir = os.path.join(tempfile.gettempdir(), f"bpc_{message.from_user.id}")
            os.makedirs(temp_dir, exist_ok=True)
            
            try:
                file_path = os.path.join(temp_dir, file.file_name)
                await bot.download(file, destination=file_path)
                
                encrypted_file = os.path.join(temp_dir, "common.bpc")
                original_data = read_file_bytes(file_path)
                xor_key = bytes.fromhex('31 63 4b 31 61 35 55 46 32 74 55 38 2a 47 32 6c 57 23 26 25')
                
                encrypted = bytearray()
                for i in range(len(original_data)):
                    encrypted.append(original_data[i] ^ xor_key[i % len(xor_key)])
                
                write_bytes_to_file(encrypted_file, encrypted)
                
                name = message.from_user.first_name            
                await message.answer_document(
                    FSInputFile(encrypted_file),
                    caption=f"<b>📊 файл готов</b>\n<b>📝 назва - common.bpc</b>",
                    parse_mode=ParseMode.HTML
                )
                    
            finally:
                if os.path.exists(temp_dir):
                    rmtree(temp_dir, ignore_errors=True)

    @router.message(Command("bpc"))
    async def bpc_command(message: types.Message, bot: Bot):
        if not await check_subscription(message, bot):
            return
        name = message.from_user.first_name
        
        await message.answer(
            f"<b>чтоб сделать конверт файла (кучка говна) BPC в ZIP и наоборот кидай - файл BPC или ZIP с назвой common.zip или common.bpc</b>\n",
            parse_mode=ParseMode.HTML
        )

    return router