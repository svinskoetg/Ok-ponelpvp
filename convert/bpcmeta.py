import os
import zipfile
import struct
import io
import re
from typing import List, Tuple
from aiogram import Bot, Router, F
from aiogram.types import Message, BufferedInputFile, CallbackQuery
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from start.start import check_subscription


def setup_bpcmeta(bot: Bot):
    router = Router(name="bpcmeta")

    def is_valid_bpc(filename: str) -> bool:
        return bool(re.fullmatch(r'GENERIC( \(\d+\))?\.bpc', filename, re.IGNORECASE))

    @router.message(Command("bpcmeta"))
    async def bpcmeta_command(message: Message, bot: Bot):
        if not await check_subscription(message, bot):
            return
            
        await message.answer(
            f"<b>чтоб сделать конверт файла BPC в BPCMETA кидай - файл GENERIC.BPC</b>"
        )

    @router.message(F.document & F.document.file_name.func(is_valid_bpc))
    async def bpc_xyina(message: Message, bot: Bot):
        if not await check_subscription(message, bot):
            return

        try:
            progress_msg = await message.reply(f"<b>⏳ конверт идет ок.</b>")
            
            doc = await bot.get_file(message.document.file_id)
            file_data = await bot.download_file(doc.file_path)
            zip_data = file_data.read()
            
            meta_data = BpcMetaGenerator.build_from_bytes(zip_data)
            output_filename = re.sub(r'\.bpc$', '.bpcmeta', message.document.file_name, flags=re.IGNORECASE)
            result_file = BufferedInputFile(meta_data, filename=output_filename)
            
            await message.answer_document(
                result_file,
                caption=f"<b>📊 файл готов</b>\n<b>📝 назва - GENERIC.bpcmeta</b>"
            )
            
        except Exception as e:
            await message.answer(f"<b>ошибко при обработке файла:</b> {str(e)}")
        finally:
            if 'progress_msg' in locals():
                try:
                    await progress_msg.delete()
                except:
                    pass

    class BpcMetaGenerator:
        @staticmethod
        def build_from_bytes(zip_data: bytes) -> bytes:
            with io.BytesIO(zip_data) as zip_buffer:
                with zipfile.ZipFile(zip_buffer, 'r') as zip_file:
                    entries: List[Tuple[int, int, int, str]] = []
                    
                    for file_info in zip_file.infolist():
                        if file_info.is_dir():
                            continue
                            
                        filename = file_info.filename.lower()
                        if not (filename.endswith('.mp3') or filename.endswith('.wav') or filename.endswith('.ogg')):
                            continue
                        
                        extra = len(file_info.extra) if hasattr(file_info, 'extra') else 0
                        data_offset = (file_info.header_offset + 30 + 
                                     len(file_info.filename.encode('utf-8')) + 
                                     extra)
                        
                        is_mp3 = 1 if filename.endswith('.mp3') else 0
                        
                        entries.append((
                            data_offset,
                            file_info.file_size,
                            is_mp3,
                            file_info.filename
                        ))
                    
                    total_size = 4 + sum(4 + 4 + 1 + 2 + len(name.encode('utf-8')) for _, _, _, name in entries)
                    
                    buffer = bytearray(total_size)
                    
                    struct.pack_into('<I', buffer, 0, len(entries))
                    pos = 4
                    
                    for offset, size, is_mp3, name in entries:
                        struct.pack_into('<I', buffer, pos, offset)
                        pos += 4
                        
                        struct.pack_into('<I', buffer, pos, size)
                        pos += 4
                        
                        buffer[pos] = is_mp3
                        pos += 1
                        
                        name_bytes = name.encode('utf-8')
                        struct.pack_into('<H', buffer, pos, len(name_bytes))
                        pos += 2
                        
                        buffer[pos:pos+len(name_bytes)] = name_bytes
                        pos += len(name_bytes)
                    
                    return bytes(buffer)

    return router