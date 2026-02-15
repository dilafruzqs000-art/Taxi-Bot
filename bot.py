import telebot
from telebot import types
import database as db
import requests
import time
import threading

# ============================================
# ТВОЙ ТОКЕН
# ============================================
TOKEN = "8280965284:AAEPBMWUmZQHfEA3rsJNlSfAznuHFJ02Crw"
bot = telebot.TeleBot(TOKEN)

# Временное хранилище заказов (пока не ушли в БД)
temp_order = {}

# ============================================
# ГЕОКОДИНГ (координаты → адрес)
# ============================================
def reverse_geocode(lat, lon):
    """Преобразует координаты в адрес через OpenStreetMap"""
    url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}&zoom=18&addressdetails=1"
    headers = {'User-Agent': 'TaxiBot/1.0 (samir@example.com)'}  # можно заменить email
    try:
        r = requests.get(url, headers=headers, timeout=5)
        if r.status_code == 200:
            data = r.json()
            return data.get('display_name', 'Неизвестный адрес')
    except:
        return None
    return None

# ============================================
# КОМАНДА /start
# ============================================
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    user = db.get_user(user_id)
    if user:
        main_menu(message, user[1])  # user[1] — роль
        return

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🚖 Клиент", "🚛 Водитель")
    bot.send_message(user_id, "Добро пожаловать! Кто вы?", reply_markup=markup)

# ============================================
# ВЫБОР РОЛИ И РЕГИСТРАЦИЯ
# ============================================
@bot.message_handler(func=lambda msg: msg.text in ["🚖 Клиент", "🚛 Водитель"])
def choose_role(message):
    user_id = message.from_user.id
    role = 'client' if message.text == "🚖 Клиент" else 'driver'
    bot.send_message(user_id, "Введите ваш номер телефона:")
    bot.register_next_step_handler(message, get_phone, role)

def get_phone(message, role):
    phone = message.text
    name = message.from_user.first_name or "Пользователь"
    db.add_user(message.from_user.id, role, phone, name)
    bot.send_message(message.from_user.id, f"✅ Вы зарегистрированы как {role}!")
    main_menu(message, role)

# ============================================
# ГЛАВНОЕ МЕНЮ
# ============================================
def main_menu(message, role):
    user_id = message.from_user.id
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    if role == 'client':
        markup.add("🚖 Вызвать такси", "📋 Мои поездки")
    else:  # driver
        # Проверяем статус водителя (is_active)
        user = db.get_user(user_id)
        if user and user[5]:  # user[5] — is_active (BOOLEAN)
            markup.add("🔴 Не на линии", "📦 Доступные заказы")
        else:
            markup.add("🟢 На линии", "📦 Доступные заказы")
    bot.send_message(user_id, "Главное меню:", reply_markup=markup)

# ============================================
# ЛОГИКА ВОДИТЕЛЯ (вкл/выкл линии)
# ============================================
@bot.message_handler(func=lambda msg: msg.text == "🟢 На линии")
def go_online(message):
    db.set_driver_active(message.from_user.id, True)
    bot.send_message(message.from_user.id, "✅ Вы на линии. Ждём заказы.")
    main_menu(message, 'driver')

@bot.message_handler(func=lambda msg: msg.text == "🔴 Не на линии")
def go_offline(message):
    db.set_driver_active(message.from_user.id, False)
    bot.send_message(message.from_user.id, "⏸ Вы не на линии.")
    main_menu(message, 'driver')

# ============================================
# ЛОГИКА КЛИЕНТА: ВЫЗОВ ТАКСИ
# ============================================
@bot.message_handler(func=lambda msg: msg.text == "🚖 Вызвать такси")
def ask_from(message):
    user_id = message.from_user.id
    temp_order[user_id] = {}
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("📍 Отправить геолокацию", request_location=True))
    markup.add(types.KeyboardButton("🔙 Отмена"))
    bot.send_message(user_id, "Откуда вас забрать? Отправьте геолокацию или напишите адрес текстом.", reply_markup=markup)
    bot.register_next_step_handler(message, ask_to)

def ask_to(message):
    user_id = message.from_user.id
    if message.location:
        lat = message.location.latitude
        lon = message.location.longitude
        address = reverse_geocode(lat, lon)
        if address:
            temp_order[user_id]['from'] = address
            bot.send_message(user_id, f"✅ Откуда: {address}")
        else:
            temp_order[user_id]['from'] = f"{lat},{lon}"
            bot.send_message(user_id, "📍 Местоположение получено (координаты).")
    elif message.text and message.text != "🔙 Отмена":
        temp_order[user_id]['from'] = message.text
        bot.send_message(user_id, f"✅ Откуда: {message.text}")
    else:
        bot.send_message(user_id, "❌ Отмена заказа.", reply_markup=types.ReplyKeyboardRemove())
        return

    # Спрашиваем "Куда"
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("📍 Отправить геолокацию", request_location=True))
    markup.add(types.KeyboardButton("🔙 Отмена"))
    bot.send_message(user_id, "Куда едем? Отправьте геолокацию или напишите адрес.", reply_markup=markup)
    bot.register_next_step_handler(message, ask_price)

def ask_price(message):
    user_id = message.from_user.id
    if message.location:
        lat = message.location.latitude
        lon = message.location.longitude
        address = reverse_geocode(lat, lon)
        if address:
            temp_order[user_id]['to'] = address
            bot.send_message(user_id, f"✅ Куда: {address}")
        else:
            temp_order[user_id]['to'] = f"{lat},{lon}"
            bot.send_message(user_id, "📍 Местоположение получено (координаты).")
    elif message.text and message.text != "🔙 Отмена":
        temp_order[user_id]['to'] = message.text
        bot.send_message(user_id, f"✅ Куда: {message.text}")
    else:
        bot.send_message(user_id, "❌ Отмена заказа.", reply_markup=types.ReplyKeyboardRemove())
        return

    bot.send_message(user_id, "💰 Предложите цену за поездку (в рублях):", reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(message, confirm_order)

def confirm_order(message):
    user_id = message.from_user.id
    try:
        price = int(message.text)
        from_addr = temp_order[user_id]['from']
        to_addr = temp_order[user_id]['to']
        order_id = db.create_order(user_id, from_addr, to_addr, price)
        bot.send_message(user_id, f"✅ Заказ #{order_id} создан. Ищем водителя...")

        # Уведомляем всех активных водителей
        drivers = db.get_active_drivers()
        for driver_id in drivers:
            try:
                bot.send_message(
                    driver_id,
                    f"🚖 **Новый заказ #{order_id}**\n"
                    f"📍 От: {from_addr}\n"
                    f"🏁 До: {to_addr}\n"
                    f"💰 Цена: {price} руб.\n\n"
                    f"Чтобы принять, отправьте /accept_{order_id}",
                    parse_mode="Markdown"
                )
            except:
                pass
    except ValueError:
        bot.send_message(user_id, "❌ Цена должна быть числом. Попробуйте снова.")
    finally:
        del temp_order[user_id]
        # Возвращаем в меню (нужно узнать роль)
        user = db.get_user(user_id)
        if user:
            main_menu(message, user[1])

# ============================================
# ПРИНЯТИЕ ЗАКАЗА ВОДИТЕЛЕМ
# ============================================
@bot.message_handler(func=lambda msg: msg.text and msg.text.startswith('/accept_'))
def accept_order(message):
    try:
        order_id = int(message.text.split('_')[1])
        driver_id = message.from_user.id

        # Проверяем, что водитель активен
        user = db.get_user(driver_id)
        if not user or user[1] != 'driver' or not user[5]:
            bot.send_message(driver_id, "❌ Вы не на линии или не водитель.")
            return

        # Назначаем водителя в БД
        db.assign_driver(order_id, driver_id)

        bot.send_message(driver_id, f"✅ Вы приняли заказ #{order_id}. Скоро с вами свяжется клиент.")

        # Уведомить клиента (нужно получить client_id из заказа)
        # В БД нужно добавить функцию get_order(order_id) – оставим на следующий этап
        # Пока просто шлём водителю
    except Exception as e:
        bot.send_message(message.from_user.id, "❌ Ошибка при принятии заказа.")

# ============================================
# ЗАПУСК БОТА
# ============================================
if __name__ == "__main__":
    print("🚖 Бот такси запущен!")
    print(f"🤖 @{bot.get_me().username}")
    while True:
        try:
            bot.polling(none_stop=True, interval=0, timeout=20)
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            time.sleep(5)