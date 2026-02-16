import telebot
from telebot import types
import database as db
import requests
import time
import threading
from flask import Flask

# ===== Flask для Render (обязательно) =====
app = Flask(__name__)
# ===== ФУНКЦИЯ ДЛЯ ГЕНЕРАЦИИ ССЫЛКИ НА ОПЛАТУ =====
YOOMONEY_WALLET = "4100119475243191"

def get_payment_link(order_id, amount):
    desc = f"Заказ такси №{order_id}"
    label = f"order_{order_id}"
    url = (f"https://yoomoney.ru/quickpay/confirm.xml?"
           f"receiver={YOOMONEY_WALLET}&"
           f"quickpay-form=shop&"
           f"targets={desc}&"
           f"paymentType=AC&"
           f"sum={amount}&"
           f"label={label}&"
           f"successURL=https://t.me/my_taxi_333_bot")
    return url
@app.route('/')
def home():
    return "Бот такси работает!"

def run_flask():
    app.run(host='0.0.0.0', port=10000)

# Запускаем Flask в отдельном потоке
flask_thread = threading.Thread(target=run_flask, daemon=True)
flask_thread.start()

# ===== Твой токен =====
TOKEN = "8280965284:AAEPBMWUmZQHfEA3rsJNlSfAznuHFJ02Crw"
bot = telebot.TeleBot(TOKEN)

# Временное хранилище заказов
temp_order = {}

# ===== Геокодинг =====
def reverse_geocode(lat, lon):
    url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}&zoom=18&addressdetails=1"
    headers = {'User-Agent': 'TaxiBot/1.0 (samir@example.com)'}
    try:
        r = requests.get(url, headers=headers, timeout=5)
        if r.status_code == 200:
            data = r.json()
            return data.get('display_name', 'Неизвестный адрес')
    except:
        return None
    return None

# ===== Команда /start =====
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    user = db.get_user(user_id)
    if user:
        main_menu(message, user[1])
        return
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🚖 Клиент", "🚛 Водитель")
    bot.send_message(user_id, "Добро пожаловать! Кто вы?", reply_markup=markup)

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

# ===== Главное меню =====
def main_menu(message, role):
    user_id = message.from_user.id
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    if role == 'client':
        markup.add("🚖 Вызвать такси", "📋 Мои поездки")
    else:
        user = db.get_user(user_id)
        if user and user[5]:
            markup.add("🔴 Не на линии", "📦 Доступные заказы")
        else:
            markup.add("🟢 На линии", "📦 Доступные заказы")
    bot.send_message(user_id, "Главное меню:", reply_markup=markup)

# ===== Водитель: вкл/выкл линии =====
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

# ===== Клиент: создание заказа =====
@bot.message_handler(func=lambda msg: msg.text == "🚖 Вызвать такси")
def ask_from(message):
    user_id = message.from_user.id
    temp_order[user_id] = {}
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("📍 Отправить геолокацию", request_location=True))
    markup.add(types.KeyboardButton("🔙 Отмена"))
    bot.send_message(user_id, "Откуда вас забрать? Отправьте геолокацию или напишите адрес.", reply_markup=markup)
    bot.register_next_step_handler(message, ask_to)

def ask_to(message):
    user_id = message.from_user.id
    if message.location:
        lat, lon = message.location.latitude, message.location.longitude
        address = reverse_geocode(lat, lon)
        temp_order[user_id]['from'] = address or f"{lat},{lon}"
        bot.send_message(user_id, f"✅ Откуда: {temp_order[user_id]['from']}")
    elif message.text and message.text != "🔙 Отмена":
        temp_order[user_id]['from'] = message.text
        bot.send_message(user_id, f"✅ Откуда: {message.text}")
    else:
        bot.send_message(user_id, "❌ Отмена.", reply_markup=types.ReplyKeyboardRemove())
        return

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("📍 Отправить геолокацию", request_location=True))
    markup.add(types.KeyboardButton("🔙 Отмена"))
    bot.send_message(user_id, "Куда едем?", reply_markup=markup)
    bot.register_next_step_handler(message, ask_price)

def ask_price(message):
    user_id = message.from_user.id
    if message.location:
        lat, lon = message.location.latitude, message.location.longitude
        address = reverse_geocode(lat, lon)
        temp_order[user_id]['to'] = address or f"{lat},{lon}"
        bot.send_message(user_id, f"✅ Куда: {temp_order[user_id]['to']}")
    elif message.text and message.text != "🔙 Отмена":
        temp_order[user_id]['to'] = message.text
        bot.send_message(user_id, f"✅ Куда: {message.text}")
    else:
        bot.send_message(user_id, "❌ Отмена.", reply_markup=types.ReplyKeyboardRemove())
        return

    bot.send_message(user_id, "💰 Предложите цену в рублях:", reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(message, confirm_order)

def confirm_order(message):
    user_id = message.from_user.id
    try:
        price = int(message.text)
        from_addr = temp_order[user_id]['from']
        to_addr = temp_order[user_id]['to']
        order_id = db.create_order(user_id, from_addr, to_addr, price)
        bot.send_message(user_id, f"✅ Заказ #{order_id} создан. Ищем водителя...")
        drivers = db.get_active_drivers()
        for d in drivers:
            try:
                bot.send_message(d,
                    f"🚖 **Новый заказ #{order_id}**\n"
                    f"📍 От: {from_addr}\n"
                    f"🏁 До: {to_addr}\n"
                    f"💰 Цена: {price} руб.\n\n"
                    f"/accept_{order_id} – принять",
                    parse_mode="Markdown")
            except:
                pass
    except ValueError:
        bot.send_message(user_id, "❌ Цена должна быть числом.")
    finally:
        del temp_order[user_id]
        user = db.get_user(user_id)
        if user:
            main_menu(message, user[1])

# ===== Принятие заказа водителем =====
@bot.message_handler(func=lambda msg: msg.text and msg.text.startswith('/accept_'))
def accept_order(message):
    try:
        order_id = int(message.text.split('_')[1])
        driver_id = message.from_user.id
        user = db.get_user(driver_id)
        if not user or user[1] != 'driver' or not user[5]:
            bot.send_message(driver_id, "❌ Вы не на линии или не водитель.")
            return
        
        db.assign_driver(order_id, driver_id)
        bot.send_message(driver_id, f"✅ Вы приняли заказ #{order_id}. Ожидаем оплату от клиента.")

        # ---- НОВЫЙ КОД: отправка ссылки клиенту ----
        # Нужно получить client_id и price из базы
        order_info = db.get_order_info(order_id)  # эту функцию добавим в database.py
        if order_info:
            client_id = order_info['client_id']
            price = order_info['price']
            pay_url = get_payment_link(order_id, price)
            bot.send_message(
                client_id,
                f"✅ Водитель найден!\n"
                f"Для подтверждения заказа оплатите {price} руб.\n"
                f"Ссылка для оплаты:\n{pay_url}"
            )
        # ---------------------------------------------

    except Exception as e:
        bot.send_message(message.from_user.id, "❌ Ошибка при принятии заказа.")
# ===== Запуск =====
if __name__ == "__main__":
    print("✅ Бот с Flask запущен!")
    print(f"🤖 @{bot.get_me().username}")
    while True:
        try:
            bot.polling(none_stop=True, interval=0, timeout=20)
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            time.sleep(5)