import numpy as np
from PIL import Image
import zipfile
import io
import random
from aiogram import Router, types, F, Bot
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.filters import Command
from aiogram.enums import ParseMode
import asyncio
from concurrent.futures import ThreadPoolExecutor
from start.start import check_subscription

router = Router()
executor = ThreadPoolExecutor(max_workers=4)

async def process_image(file: io.BytesIO):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(executor, _process_image_sync, file)

def _process_image_sync(file: io.BytesIO):
    img = Image.open(file).convert("RGBA")
    data = np.array(img)
    alpha = data[:, :, 3]

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5,5))
    alpha = cv2.morphologyEx(alpha, cv2.MORPH_CLOSE, kernel)
    alpha = cv2.morphologyEx(alpha, cv2.MORPH_OPEN, kernel)

    binary = cv2.threshold(alpha, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]
    
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(binary, connectivity=8)
    
    objects = []
    min_pixels = 500
    padding = 10
    
    for i in range(1, num_labels):
        x, y, w, h, area = stats[i]
        
        if area < min_pixels:
            continue
            
        x1 = max(0, x - padding)
        y1 = max(0, y - padding)
        x2 = min(data.shape[1], x + w + padding)
        y2 = min(data.shape[0], y + h + padding)
        
        object_mask = (labels[y1:y2, x1:x2] == i).astype(np.uint8) * 255
        
        object_mask = cv2.morphologyEx(object_mask, cv2.MORPH_CLOSE, kernel)
        
        object_img = np.zeros((y2-y1, x2-x1, 4), dtype=np.uint8)
        object_img[:, :, :3] = data[y1:y2, x1:x2, :3]
        object_img[:, :, 3] = object_mask
        
        objects.append((area, object_img))
    
    objects.sort(reverse=True, key=lambda x: x[0])
    
    if len(objects) == 6:
        prefixes = ['hud_back', 'hud_down', 'hud_up', 'hud_center', 'hud_menu', 'hud_donat_store']
    elif len(objects) == 5:
        prefixes = ['hud_down', 'hud_up', 'hud_center', 'hud_menu', 'hud_donat_store']
    else:
        prefixes = [f'hud_part_{i+1}' for i in range(len(objects))]
    
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for i, (_, img) in enumerate(objects):
            img_pil = Image.fromarray(img)
            with io.BytesIO() as img_buffer:
                img_pil.save(img_buffer, format='PNG')
                filename = f"{prefixes[i]}.png" if i < len(prefixes) else f"hud_extra_{i+1}.png"
                zip_file.writestr(filename, img_buffer.getvalue())
    
    zip_buffer.seek(0)
    return zip_buffer, len(objects)

@router.message(Command("hudcut"))
async def hudcut(message: Message, bot: Bot):
    if not await check_subscription(message, bot):
        return
    name = message.from_user.first_name
    
    if not (message.document and message.document.mime_type == "image/png"):
        await message.answer(
            f"<b>чтоб разрезать HUD на части кидай -</b> <code>/hudcut</code> <b>+ PNG файл</b>",
            parse_mode=ParseMode.HTML
        )
        return

    progress_msg = await message.reply(f"<b>⏳ процесс идёт ок.</b>", parse_mode="HTML")
    
    try:
        file = await message.bot.get_file(message.document.file_id)
        file_bytes = await message.bot.download_file(file.file_path)
        zip_buffer, count = await process_image(file_bytes)
        zip_filename = f"hudcut.zip"
        
        await message.reply_document(
            BufferedInputFile(zip_buffer.getvalue(), filename=zip_filename),
            caption=f"<b>📊 файл готов</b>\n<b>📝 назва - hudcut.zip</b>", 
            parse_mode=ParseMode.HTML
        )

    except Exception as e:
        error_message = str(e).replace("<", "&lt;").replace(">", "&gt;")
        await progress_msg.edit_text(f"<b>произошла ошибко: {error_message}</b>", parse_mode="HTML")
    finally:
        await asyncio.sleep(5)
        try:
            await progress_msg.delete()
        except:
            pass