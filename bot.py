import asyncio
import os
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
import vk_api

# Логирование для отладки ошибок в Railway
logging.basicConfig(level=logging.INFO)

TG_TOKEN = os.getenv("TG_TOKEN")
TG_CHANNEL_ID = int(os.getenv("TG_CHANNEL_ID"))
VK_TOKEN = os.getenv("VK_TOKEN")
VK_GROUP_ID = int(os.getenv("VK_GROUP_ID"))

bot = Bot(token=TG_TOKEN)
dp = Dispatcher()
vk_session = vk_api.VkApi(token=VK_TOKEN)
vk = vk_session.get_api()

class PostStates(StatesGroup):
    waiting_for_post = State()
    waiting_for_confirmation = State()

def get_platform_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="ТГ + ВК", callback_data="post_all")],
        [InlineKeyboardButton(text="Только ТГ", callback_data="post_tg")],
        [InlineKeyboardButton(text="Только ВК", callback_data="post_vk")],
        [InlineKeyboardButton(text="Отмена", callback_data="cancel")]
    ])

def upload_to_vk(text, photo_path=None):
    attachments = []
    if photo_path:
        upload = vk_api.VkUpload(vk_session)
        photo = upload.photo_wall(photos=photo_path)[0]
        attachments.append(f"photo{photo['owner_id']}_{photo['id']}")
    vk.wall.post(owner_id=VK_GROUP_ID, from_group=1, message=text, attachments=','.join(attachments) if attachments else None)

@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await message.answer("Пришли пост:")
    await state.set_state(PostStates.waiting_for_post)

@dp.message(PostStates.waiting_for_post, F.text | F.photo)
async def catch_post(message: Message, state: FSMContext):
    if message.photo:
        file = await bot.get_file(message.photo[-1].file_id)
        path = f"{message.photo[-1].file_id}.jpg"
        await bot.download_file(file.file_path, path)
        await state.update_data(text=message.caption or "", photo=path)
    else:
        await state.update_data(text=message.text, photo=None)
    await message.answer("Куда постим?", reply_markup=get_platform_kb())
    await state.set_state(PostStates.waiting_for_confirmation)

@dp.callback_query(PostStates.waiting_for_confirmation)
async def process_pub(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    text, photo = data.get("text"), data.get("photo")
    
    if call.data != "cancel":
        if call.data in ["post_all", "post_tg"]:
            if photo: await bot.send_photo(TG_CHANNEL_ID, photo=open(photo, 'rb'), caption=text)
            else: await bot.send_message(TG_CHANNEL_ID, text=text)
        if call.data in ["post_all", "post_vk"]:
            await asyncio.to_thread(upload_to_vk, text, photo)
        await call.message.edit_text("✅ Опубликовано!")
    else:
        await call.message.edit_text("❌ Отмена.")
    
    if photo and os.path.exists(photo): os.remove(photo)
    await state.clear()

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
