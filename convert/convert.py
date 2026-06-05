import os
import zipfile
import tempfile
import asyncio
import re
import subprocess
import shutil
import concurrent.futures
import struct
import binascii
import random
import json
import numpy as np
import librosa
import lameenc
from pathlib import Path
from shutil import rmtree
from aiogram import Bot, types, Router, F
from aiogram.types import FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile, Message, InputMediaDocument, CallbackQuery
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.enums import ParseMode
from typing import Dict, List, Optional, Set
from PIL import Image
from start.start import check_subscription
from aiogram.utils.markdown import html_decoration as hd
from mutagen.id3 import ID3, TPE1, TIT2


def setup_converter(bot: Bot):
    router = Router(name="converter")
    file_lock = asyncio.Lock()
    
    temp_dir = Path(__file__).parent / "temp"
    temp_dir.mkdir(exist_ok=True)
    
    pvrtex_tool = Path(__file__).parent / "exe" / "PVRTexToolCLI.exe"
    thread_pool = concurrent.futures.ThreadPoolExecutor(max_workers=os.cpu_count())
    
    supported_formats = {
        '.png', '.jpg', '.jpeg', '.zip', '.btx', '.dds', 
        '.ifp', '.ani', '.mod', '.dff', '.dat', '.json', '.mp3'
    }

    async def process_mp3_file(input_path: Path, output_path: Path) -> bool:
        temp_path = None
        try:
            y, sr = librosa.load(
                str(input_path),
                sr=None,
                mono=True,
            dtype=np.float32,
                res_type='soxr_hq'
            )

            def process_audio():
                y_processed = y * 1.2
                np.clip(y_processed, -1.0, 1.0, out=y_processed)
                return (y_processed * 32767).astype(np.int16).tobytes()

            loop = asyncio.get_running_loop()
            audio_data = await loop.run_in_executor(thread_pool, process_audio)

            encoder = lameenc.Encoder()
            encoder.set_bit_rate(192)
            encoder.set_in_sample_rate(sr)
            encoder.set_channels(1)
            encoder.set_quality(2)

            temp_path = temp_dir / f"temp_{random.randint(1000,9999)}.mp3"
            with open(temp_path, 'wb') as f:
                chunk_size = 8192
                for i in range(0, len(audio_data), chunk_size):
                    chunk = audio_data[i:i+chunk_size]
                    mp3_chunk = encoder.encode(chunk)
                    if mp3_chunk:
                        f.write(mp3_chunk)
                final_chunk = encoder.flush()
                if final_chunk:
                    f.write(final_chunk)

            audio = ID3()
            audio.add(TPE1(encoding=3, text="@shouxs_bot"))
            audio.add(TIT2(encoding=3, text="by @shouxs_bot"))
            audio.save(temp_path, v2_version=3)

            await safe_move(temp_path, output_path)
            return True

        except Exception as e:
            if temp_path:
                await safe_delete(temp_path)
            return False
    
    async def safe_delete(file_path: Path, max_attempts=3):
        for attempt in range(max_attempts):
            try:
                if file_path.exists():
                    if file_path.is_dir():
                        shutil.rmtree(file_path, ignore_errors=True)
                    else:
                        file_path.unlink(missing_ok=True)
                    return True
            except Exception:
                await asyncio.sleep(0.5 * (attempt + 1))
        return False

    async def safe_move(src: Path, dst: Path, max_attempts=3):
        for attempt in range(max_attempts):
            try:
                if src.exists():
                    shutil.move(str(src), str(dst))
                    return True
                return False
            except:
                await asyncio.sleep(0.5 * (attempt + 1))
        return False

    async def create_compressed_zip(files: List[Path], zip_name: str) -> Optional[Path]:
        zip_path = temp_dir / zip_name
        try:
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as zipf:
                for file in files:
                    if file.exists():
                        arcname = file.relative_to(temp_dir)
                        zipf.write(file, arcname)
            return zip_path
        except:
            await safe_delete(zip_path)
            return None

    async def cleanup_files(files: List[Path]) -> None:
        await asyncio.gather(*[safe_delete(file) for file in files])

    def read_file_bytes(file_path):
        with open(file_path, 'rb') as f:
            return bytearray(f.read())

    def write_bytes_to_file(file_path, data):
        with open(file_path, 'wb') as f:
            f.write(data)

    def convert_ifp_to_ani(orig_path):
        with open(orig_path, 'rb') as f:
            bytes_data = bytearray(f.read())
        
        bytes_data[28] = bytes_data[32]
        bytes_data[29] = bytes_data[33]
        bytes_data[32] = bytes_data[4]
        bytes_data[33] = bytes_data[5]
        bytes_data[34] = bytes_data[6]
        bytes_data[35] = bytes_data[7]

        bytes_data[4] = bytes_data[8]
        bytes_data[5] = bytes_data[9]
        bytes_data[6] = bytes_data[10]

        bytes_data[8] = 0
        bytes_data[9] = 0
        bytes_data[10] = 0

        new_path = str(orig_path).replace('.ifp', '.ani')
        with open(new_path, 'wb') as f:
            f.write(bytes_data)
        
        return Path(new_path)

    def convert_ani_to_ifp(orig_path):
        with open(orig_path, 'rb') as f:
            bytes_data = bytearray(f.read())
        
        bytes_data[32] = bytes_data[28]
        bytes_data[33] = bytes_data[29]
        bytes_data[4] = bytes_data[32]
        bytes_data[5] = bytes_data[33]
        bytes_data[6] = bytes_data[34]
        bytes_data[7] = bytes_data[35]

        bytes_data[8] = bytes_data[4]
        bytes_data[9] = bytes_data[5]
        bytes_data[10] = bytes_data[6]

        bytes_data[28] = 0
        bytes_data[29] = 0

        new_path = str(orig_path).replace('.ani', '.ifp')
        with open(new_path, 'wb') as f:
            f.write(bytes_data)
        
        return Path(new_path)

    def ror32(x: int, r: int) -> int:
        return ((x >> r) | (x << (32 - r))) & 0xFFFFFFFF

    def tea_decrypt_block(data: bytearray, key: list[int], rounds: int = 8) -> None:
        delta = 0x61C88647
        for offset in range(0, len(data), 8):
            if offset + 8 > len(data):
                break
            v0, v1 = struct.unpack_from('<II', data, offset)
            sum_val = (-delta * rounds) & 0xFFFFFFFF
            for _ in range(rounds):
                v1 = (v1 - ((v0 + sum_val) ^ (key[3] + (v0 >> 5)) ^ (key[2] + (v0 << 4)))) & 0xFFFFFFFF
                new_sum = (sum_val + v1) & 0xFFFFFFFF
                sum_val = (sum_val + delta) & 0xFFFFFFFF
                v0 = (v0 - (new_sum ^ (key[0] + (v1 << 4)) ^ (key[1] + (v1 >> 5)))) & 0xFFFFFFFF
            struct.pack_into('<II', data, offset, v0, v1)

    def patch_dff_header(dff_data: bytearray) -> bytearray:
        if len(dff_data) < 12:
            return dff_data
        real_size = len(dff_data) - 12
        return dff_data[:4] + struct.pack('<I', real_size) + dff_data[8:]

    def clean_dff_data(dff_data: bytearray) -> bytearray:
        end = len(dff_data)
        while end > 0 and dff_data[end - 1] == 0:
            end -= 1
        return dff_data[:end]

    def process_mod_file(mod_bytes: bytes) -> bytes:
        try:
            if len(mod_bytes) < 28:
                return None
            
            magic, length, num_blocks = struct.unpack_from('<III', mod_bytes, 0)
            
            if magic == 0x00000010:
                return mod_bytes
            
            if magic != 0xAB921033:
                return None

            base_key = [0x6ED9EE7A, 0x930C666B, 0x930E166B, 0x4709EE79]
            key = [ror32(k ^ 0x12913AFB, 19) for k in base_key]

            data = bytearray(mod_bytes)
            offset = 28
            for _ in range(num_blocks):
                if offset + 0x800 > len(data):
                    return None
                block = data[offset:offset + 0x800]
                tea_decrypt_block(block, key)
                data[offset:offset + 0x800] = block
                offset += 0x800

            actual_length = min(length, len(data) - 28)
            dff = bytearray(data[28:28 + actual_length])
            dff = patch_dff_header(dff)
            dff = clean_dff_data(dff)
            return bytes(dff)
        except:
            return None

    async def convert_png_to_btx_pvr(input_path: Path, temp_ktx: Path) -> bool:
        try:
            cmd = [
                str(pvrtex_tool),
                "-i", str(input_path),
                "-o", str(temp_ktx),
                "-f", "ASTC_8x8,UBN,sRGB",
                "-ics", "srgb",
                "-silent"
            ]
            process = await asyncio.create_subprocess_exec(*cmd)
            await process.wait()
            return temp_ktx.exists()
        except:
            return False

    async def convert_btx_to_png_pvr(temp_ktx: Path, output_path: Path) -> bool:
        try:
            cmd = [
                str(pvrtex_tool),
                "-i", str(temp_ktx),
                "-d", str(output_path),
                "-f", "r8g8b8a8",
                "-ics", "srgb",
                "-silent"
            ]
            process = await asyncio.create_subprocess_exec(*cmd)
            await process.wait()
            return output_path.exists()
        except:
            return False

    async def convert_png_to_btx(input_path: Path, original_filename: str) -> Optional[Path]:
        output_filename = Path(original_filename).stem + '.btx'
        output_path = temp_dir / output_filename
        temp_ktx = temp_dir / f"temp_{random.randint(1000,9999)}.ktx"

        if not await convert_png_to_btx_pvr(input_path, temp_ktx):
            return None

        try:
            btx_data = b'\x02\x00\x00\x00' + temp_ktx.read_bytes()
            output_path.write_bytes(btx_data)
            return output_path
        finally:
            await safe_delete(temp_ktx)

    async def convert_btx_to_png(input_path: Path, original_filename: str) -> Optional[Path]:
        output_filename = Path(original_filename).stem + '.png'
        output_path = temp_dir / output_filename
        temp_ktx = temp_dir / f"temp_{random.randint(1000,9999)}.ktx"

        try:
            ktx_data = await asyncio.to_thread(input_path.read_bytes)
            await asyncio.to_thread(temp_ktx.write_bytes, ktx_data[4:])

            if not await convert_btx_to_png_pvr(temp_ktx, output_path):
                return None

            return output_path
        finally:
            await safe_delete(temp_ktx)

    async def convert_dds_to_png(input_path: Path, original_filename: str) -> Optional[Path]:
        output_filename = Path(original_filename).stem + '.png'
        output_path = temp_dir / output_filename

        try:
            with Image.open(input_path) as img:
                img.save(output_path, "PNG")
            return output_path
        except:
            return None

    async def convert_ifp_ani(input_path: Path, original_filename: str) -> Optional[Path]:
        if input_path.suffix.lower() == '.ifp':
            return convert_ifp_to_ani(input_path)
        else:
            return convert_ani_to_ifp(input_path)

    async def convert_mod_dff(input_path: Path, original_filename: str) -> Optional[Path]:
        try:
            with open(input_path, 'rb') as f:
                file_bytes = f.read()
            
            output_bytes = None
            output_ext = None
            
            if input_path.suffix.lower() == '.mod':
                output_bytes = process_mod_file(file_bytes)
                output_ext = '.dff'
            else:
                output_bytes = file_bytes
                output_ext = '.mod'
            
            if output_bytes is None:
                return None
            
            output_name = input_path.stem + output_ext
            output_path = temp_dir / output_name
            
            with open(output_path, 'wb') as f:
                f.write(output_bytes)
            
            return output_path
        except:
            return None

    async def convert_timecyc_dat_to_json(input_path: Path, original_filename: str) -> Optional[Path]:
        try:
            with open(input_path, 'r', encoding='utf-8') as f:
                content = f.read()

            entries = []
            current_entry = None
            
            for line in content.splitlines():
                line = line.strip()
                if not line or line.startswith(';'):
                    continue
                
                parts = re.split(r'\s+', line)
                if len(parts) < 48:
                    continue
                
                entry = {
                    "AmbientRGB": [int(parts[0]), int(parts[1]), int(parts[2])],
                    "AmbientPhysicalRGB": [int(parts[3]), int(parts[4]), int(parts[5])],
                    "DirectionalRGB": [int(parts[6]), int(parts[7]), int(parts[8])],
                    "SkyTopRGB": [int(parts[9]), int(parts[10]), int(parts[11])],
                    "SkyBottomRGB": [int(parts[12]), int(parts[13]), int(parts[14])],
                    "SunCoreRGB": [int(parts[15]), int(parts[16]), int(parts[17])],
                    "SunCoronaRGB": [int(parts[18]), int(parts[19]), int(parts[20])],
                    "SunSize": float(parts[21]),
                    "SpriteSize": float(parts[22]),
                    "SpriteBrght": float(parts[23]),
                    "Shad": int(parts[24]),
                    "LightShad": int(parts[25]),
                    "PoleShad": int(parts[26]),
                    "FarClip": float(parts[27]),
                    "FogStart": float(parts[28]),
                    "LightGnd": float(parts[29]),
                    "FluffyBottomRGB": [int(parts[30]), int(parts[31]), int(parts[32])],
                    "CloudRGB": [int(parts[33]), int(parts[34]), int(parts[35])],
                    "WaterRGBA": [int(parts[36]), int(parts[37]), int(parts[38]), int(parts[39])],
                    "PostFX1ARGB": [int(parts[40]), int(parts[41]), int(parts[42]), int(parts[43])],
                    "PostFX2ARGB": [int(parts[44]), int(parts[45]), int(parts[46]), int(parts[47])],
                    "CloudAlpha": int(parts[48]) if len(parts) > 48 else 200
                }
                entries.append(entry)

            json_data = json.dumps(entries, indent=2)
            
            output_filename = Path(original_filename).stem + '.json'
            output_path = temp_dir / output_filename
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(json_data)
            
            return output_path
        except Exception as e:
            print(f"Error converting DAT to JSON: {e}")
            return None

    async def convert_timecyc_json_to_dat(input_path: Path, original_filename: str) -> Optional[Path]:
        try:
            with open(input_path, 'r', encoding='utf-8') as f:
                entries = json.load(f)

            output_lines = [
                "; Amb         Amb_Obj    Dir         Sky top     Sky bot     SunCore     SunCorona   SunSz   SprSz   SprBght  Shdw  LightShd  PoleShd  FarClp  FogSt  LightOnGround  LowCloudsRGB  BottomCloudRGB  WaterRGBA        Alpha1    RGB1        Alpha2    RGB2        CloudAlpha",
                ""
            ]
            
            time_labels = ["Midnight", "5AM", "6AM", "7AM", "Midday", "7PM", "8PM", "10PM"]
            
            for i, entry in enumerate(entries):
                if i < len(time_labels):
                    output_lines.append(f"; {time_labels[i]}")
                
                line_parts = [
                    f"{entry['AmbientRGB'][0]} {entry['AmbientRGB'][1]} {entry['AmbientRGB'][2]}",
                    f"{entry['AmbientPhysicalRGB'][0]} {entry['AmbientPhysicalRGB'][1]} {entry['AmbientPhysicalRGB'][2]}",
                    f"{entry['DirectionalRGB'][0]} {entry['DirectionalRGB'][1]} {entry['DirectionalRGB'][2]}",
                    f"{entry['SkyTopRGB'][0]} {entry['SkyTopRGB'][1]} {entry['SkyTopRGB'][2]}",
                    f"{entry['SkyBottomRGB'][0]} {entry['SkyBottomRGB'][1]} {entry['SkyBottomRGB'][2]}",
                    f"{entry['SunCoreRGB'][0]} {entry['SunCoreRGB'][1]} {entry['SunCoreRGB'][2]}",
                    f"{entry['SunCoronaRGB'][0]} {entry['SunCoronaRGB'][1]} {entry['SunCoronaRGB'][2]}",
                    f"{entry['SunSize']:.2f} {entry['SpriteSize']:.2f} {entry['SpriteBrght']:.2f}",
                    f"{entry['Shad']} {entry['LightShad']} {entry['PoleShad']}",
                    f"{entry['FarClip']:.2f} {entry['FogStart']:.2f} {entry['LightGnd']:.2f}",
                    f"{entry['FluffyBottomRGB'][0]} {entry['FluffyBottomRGB'][1]} {entry['FluffyBottomRGB'][2]}",
                    f"{entry['CloudRGB'][0]} {entry['CloudRGB'][1]} {entry['CloudRGB'][2]}",
                    f"{entry['WaterRGBA'][0]} {entry['WaterRGBA'][1]} {entry['WaterRGBA'][2]} {entry['WaterRGBA'][3]}",
                    f"{entry['PostFX1ARGB'][0]} {entry['PostFX1ARGB'][1]} {entry['PostFX1ARGB'][2]} {entry['PostFX1ARGB'][3]}",
                    f"{entry['PostFX2ARGB'][0]} {entry['PostFX2ARGB'][1]} {entry['PostFX2ARGB'][2]} {entry['PostFX2ARGB'][3]}",
                    str(entry.get('CloudAlpha', 200))
                ]
                
                output_lines.append("\t".join(line_parts))

            output_filename = Path(original_filename).stem + '.dat'
            output_path = temp_dir / output_filename
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write("\n".join(output_lines))
            
            return output_path
        except Exception as e:
            print(f"Error converting JSON to DAT: {e}")
            return None

    async def process_mp3(input_path: Path, original_filename: str) -> Optional[Path]:
        output_filename = Path(original_filename).stem + '.mp3'
        output_path = temp_dir / output_filename
        
        if await process_mp3_file(input_path, output_path):
            return output_path
        return None

    async def handle_zip_conversion(message: Message, zip_path: Path, original_name: str) -> List[Path]:
        lower_name = original_name.lower()
        if 'common' in lower_name and zip_path.suffix.lower() == '.zip':
            await message.reply("<b>NET</b>", parse_mode="HTML")
            return []
        
        extract_dir = temp_dir / f"extract_{message.from_user.id}_{random.randint(1000,9999)}"
        
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                extract_dir.mkdir(parents=True, exist_ok=True)
                zip_ref.extractall(extract_dir)

            converted_files = []
            for file_path in extract_dir.rglob('*'):
                if not file_path.is_file():
                    continue

                file_ext = file_path.suffix.lower()
                if file_ext not in supported_formats:
                    continue

                rel_path = file_path.relative_to(extract_dir)
                new_filename = rel_path.stem + (
                    '.btx' if file_ext in {'.png', '.jpg', '.jpeg'} 
                    else '.png' if file_ext in {'.btx', '.dds'}
                    else '.ani' if file_ext == '.ifp'
                    else '.ifp' if file_ext == '.ani'
                    else '.dff' if file_ext == '.mod'
                    else '.mod' if file_ext == '.dff'
                    else '.json' if file_ext == '.dat'
                    else '.dat' if file_ext == '.json'
                    else '.mp3' if file_ext == '.mp3'
                    else file_ext
                )
                output_path = temp_dir / rel_path.with_name(new_filename)

                try:
                    converted_path = None
                    
                    if file_ext in {'.png', '.jpg', '.jpeg'}:
                        converted_path = await convert_png_to_btx(file_path, rel_path.name)
                    elif file_ext == '.btx':
                        converted_path = await convert_btx_to_png(file_path, rel_path.name)
                    elif file_ext == '.dds':
                        converted_path = await convert_dds_to_png(file_path, rel_path.name)
                    elif file_ext in {'.ifp', '.ani'}:
                        converted_path = await convert_ifp_ani(file_path, rel_path.name)
                    elif file_ext in {'.mod', '.dff'}:
                        converted_path = await convert_mod_dff(file_path, rel_path.name)
                    elif file_ext == '.dat':
                        converted_path = await convert_timecyc_dat_to_json(file_path, rel_path.name)
                    elif file_ext == '.json':
                        converted_path = await convert_timecyc_json_to_dat(file_path, rel_path.name)
                    elif file_ext == '.mp3':
                        converted_path = await process_mp3(file_path, rel_path.name)
                    else:
                        continue

                    if converted_path:
                        output_path.parent.mkdir(parents=True, exist_ok=True)
                        if await safe_move(converted_path, output_path):
                            converted_files.append(output_path)
                        else:
                            await safe_delete(converted_path)

                except:
                    continue

            return converted_files

        except:
            return []
        finally:
            await safe_delete(extract_dir)
            await safe_delete(zip_path)

    async def send_converted_files(chat_id: int, files: List[Path], user_name: str, is_from_zip: bool = False) -> None:
        if not files:
            return

        if is_from_zip:
            zip_name = "wirhub.convert.zip"
            zip_path = await create_compressed_zip(files, zip_name)
            if zip_path:
                try:
                    await bot.send_document(
                        chat_id=chat_id,
                        document=BufferedInputFile(await asyncio.to_thread(zip_path.read_bytes), zip_name),
                        caption=f"<b>📊 файл готов</b>\n<b>📝 назва - convert.zip</b>",
                        parse_mode=ParseMode.HTML
                    )
                finally:
                    await safe_delete(zip_path)
        else:
            for file_path in files:
                try:
                    file_data = await asyncio.to_thread(file_path.read_bytes)
                    await bot.send_document(
                        chat_id=chat_id,
                        document=BufferedInputFile(file_data, filename=file_path.name),
                        caption=f"<b>📊 файл готов</b>\n<b>📝 назва - {file_path.name}</b>",
                        parse_mode="HTML"
                    )
                except:
                    continue
        
        await cleanup_files(files)

    async def process_files(message: types.Message, files: List[types.Message]) -> None:
        try:
            name = message.from_user.first_name
            tasks = []
            original_names = []
            is_zip_conversion = False
            
            for msg in files:
                if msg.document:
                    file = msg.document
                    ext = Path(file.file_name).suffix.lower()
                    filename = file.file_name
                    original_names.append(filename)
                    if ext == '.zip':
                        is_zip_conversion = True
                elif msg.photo:
                    file = msg.photo[-1]
                    ext = '.png'
                    filename = f"photo_{file.file_id}.png"
                    original_names.append(filename)
                else:
                    continue

                if ext not in supported_formats:
                    continue

                input_path = temp_dir / filename
                try:
                    file_info = await bot.get_file(file.file_id)
                    await bot.download_file(file_info.file_path, str(input_path))

                    if ext == '.zip':
                        task = handle_zip_conversion(message, input_path, filename)
                    elif ext == '.dds':
                        task = convert_dds_to_png(input_path, filename)
                    elif ext in {'.png', '.jpg', '.jpeg'}:
                        task = convert_png_to_btx(input_path, filename)
                    elif ext == '.btx':
                        task = convert_btx_to_png(input_path, filename)
                    elif ext in {'.ifp', '.ani'}:
                        task = convert_ifp_ani(input_path, filename)
                    elif ext in {'.mod', '.dff'}:
                        task = convert_mod_dff(input_path, filename)
                    elif ext == '.dat':
                        task = convert_timecyc_dat_to_json(input_path, filename)
                    elif ext == '.json':
                        task = convert_timecyc_json_to_dat(input_path, filename)
                    elif ext == '.mp3':
                        task = process_mp3(input_path, filename)
                    else:
                        continue

                    tasks.append(task)
                except:
                    continue

            results = await asyncio.gather(*tasks, return_exceptions=True)
            result_files = []
            
            for result in results:
                if isinstance(result, Exception):
                    continue
                if result:
                    if isinstance(result, list):
                        result_files.extend(result)
                    else:
                        result_files.append(result)   

            if not result_files:
                await message.reply(f"<b>Поддерживаются только - PNG, JPG, JPEG, DFF, MOD, IFP, ANI, BTX, ZIP, DAT, JSON, MP3 файлы</b>", parse_mode=ParseMode.HTML)
                return

            await send_converted_files(message.chat.id, result_files, name, is_zip_conversion)

        except:
            await message.reply(f"⚠️ ошибко при обработке файлов")
        finally:
            if 'result_files' in locals():
                await cleanup_files(result_files)

    @router.message(Command("convert"))
    async def convert_command(message: types.Message, bot: Bot):
        if not await check_subscription(message, bot):
            return
            
        await message.answer(
            f"<b>конверт файлов :</b>\n\n"
            f"<b>📦 PNG, JPG, JPEG ⇄ BTX</b>\n"
            f"<b>📥 IFP ⇄ ANI</b>\n"
            f"<b>🧰 MOD ⇄ DFF</b>\n"
            f"<b>☁ DAT ⇄ JSON</b>\n"
            f"<b>✅ конверт поддерживается с ZIP архивами!</b>\n"
            f"<b>🗂 прост кидай мне файлы (кучка говна), а я конвертирую.</b>",
            parse_mode=ParseMode.HTML
        )

    @router.message(F.document & F.document.file_name.endswith(tuple(supported_formats)))
    async def handle_conversion(message: types.Message, bot: Bot):
        if not await check_subscription(message, bot):
            return

        if message.caption and any(word.startswith('/') for word in message.caption.split()):
            return

        name = message.from_user.first_name
    
        progress_msg = await message.reply(f"<b>⏳ конверт идёт ок..</b>", parse_mode="HTML")

        try:
            await process_files(message, [message])
        except:
            await progress_msg.edit_text(f"<b>произошла ошибко при конвертации</b>", parse_mode="HTML")
        finally:
            await asyncio.sleep(5)
            try:
                await progress_msg.delete()
            except:
                pass   

    return router