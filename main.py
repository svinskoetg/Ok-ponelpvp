from aiogram import Bot, Dispatcher, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
import asyncio


import Editing.timecyc
import Editing.colorcyc
import Editing.blood
import painting.hud
import painting.hp
import painting.button
import copyy.logo
import copyy.bild
import painting.color
import painting.cover
import txd.txd
import convert.bpc
import convert.convert
import start.start
import painting.listva
import painting.autohud
import convert.bpcmeta
import painting.hudnew
import painting.aim
import painting.filter
import painting.roadsigns
import slicing.hudcut

TOKEN = "1212121"

async def main():
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()

    dp.include_router(convert.bpcmeta.setup_bpcmeta(bot))
    dp.include_router(painting.roadsigns.router)
    dp.include_router(start.start.router)
    dp.include_router(painting.aim.router)
    dp.include_router(painting.filter.router)
    dp.include_router(copyy.logo.router)
    dp.include_router(painting.hudnew.router)
    dp.include_router(copyy.bild.router)
    dp.include_router(painting.color.router)
    dp.include_router(painting.cover.router)
    dp.include_router(painting.autohud.router)
    dp.include_router(Editing.weapon.router)
    dp.include_router(Editing.timecyc.router)
    dp.include_router(Editing.colorcyc.router)
    dp.include_router(Editing.blood.router)
    dp.include_router(painting.hud.router)
    dp.include_router(painting.hp.router)
    dp.include_router(painting.button.router)
    dp.include_router(painting.listva.router)
    dp.include_router(txd.txd.router)
    dp.include_router(slicing.hudcut.router)
    dp.include_router(convert.bpc.setup_bpc(bot))
    dp.include_router(convert.convert.setup_converter(bot))
    
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())