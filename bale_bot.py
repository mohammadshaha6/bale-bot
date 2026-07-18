# -*- coding: utf-8 -*-
"""
منشی خودکار بله برای کسب‌وکار توریسم
قابلیت‌ها:
  1) پاسخ خودکار به سوالات متداول (قیمت، تور، ساعت کاری)
  2) گرفتن اطلاعات رزرو از مشتری (نام، تاریخ، تعداد نفرات) و ذخیره در فایل CSV
  3) ارسال خودکار فایل کاتالوگ

نحوه اجرا:
  1) pip install flask requests
  2) مقادیر بخش "تنظیمات" پایین رو با اطلاعات خودت پر کن
  3) python bale_bot.py
  4) با ابزاری مثل ngrok یا روی هاست (Railway/Render) این آدرس رو در دسترس اینترنت بذار
  5) وبهوک بله رو به آدرس عمومی سرور + /webhook ست کن (دقیقاً مثل کاری که با Make کردیم)
"""

import csv
import os
import requests
from flask import Flask, request, jsonify

# ============ تنظیمات (این بخش رو با اطلاعات خودت پر کن) ============

BOT_TOKEN = "TOKEN_ربات_خودت_رو_اینجا_بذار"
API_URL = f"https://tapi.bale.ai/bot{BOT_TOKEN}/"

# مسیر فایل کاتالوگ که می‌خوای خودکار ارسال بشه (باید کنار همین فایل پایتون باشه)
CATALOG_FILE_PATH = "catalog.pdf"

# فایلی که رزروها توش ذخیره می‌شه
BOOKINGS_CSV = "bookings.csv"

# پاسخ‌های آماده به سوالات متداول — کلیدها رو خودت متناسب با کسب‌وکارت تغییر بده
FAQ_RESPONSES = {
    "قیمت": "قیمت تورها بسته به مقصد و مدت زمان متفاوته. برای دریافت قیمت دقیق، مقصد و تاریخ موردنظرت رو بگو.",
    "تور": "تورهای فعلی ما شامل [اینجا لیست تورهاتو بنویس] هستن. برای اطلاعات بیشتر بگو کدوم مقصد مدنظرته.",
    "ساعت": "ساعت پاسخگویی ما هر روز از ساعت ۹ صبح تا ۹ شب هست.",
}

# کلماتی که تشخیص می‌ده مشتری می‌خواد رزرو کنه
BOOKING_KEYWORDS = ["رزرو", "می‌خوام بیام", "میخوام بیام", "ثبت نام"]

# کلماتی که تشخیص می‌ده مشتری کاتالوگ می‌خواد
CATALOG_KEYWORDS = ["کاتالوگ", "فایل", "معرفی", "بروشور"]

# ============ حافظه موقت مکالمه (برای گرفتن رزرو چندمرحله‌ای) ============
# ساختار: { chat_id: {"step": "name" یا "date" یا "count", "name": ..., "date": ..., "count": ...} }
booking_sessions = {}

app = Flask(__name__)


def send_message(chat_id, text):
    """ارسال یک پیام متنی به مشتری"""
    url = API_URL + "sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    requests.post(url, json=payload)


def send_document(chat_id, file_path):
    """ارسال یک فایل (مثلاً کاتالوگ PDF) به مشتری"""
    url = API_URL + "sendDocument"
    if not os.path.exists(file_path):
        send_message(chat_id, "متأسفانه فایل کاتالوگ فعلاً در دسترس نیست.")
        return
    with open(file_path, "rb") as f:
        files = {"document": f}
        data = {"chat_id": chat_id}
        requests.post(url, data=data, files=files)


def save_booking(chat_id, name, date, count):
    """ذخیره اطلاعات رزرو در فایل CSV"""
    file_exists = os.path.exists(BOOKINGS_CSV)
    with open(BOOKINGS_CSV, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["chat_id", "نام", "تاریخ", "تعداد نفرات"])
        writer.writerow([chat_id, name, date, count])


def handle_booking_flow(chat_id, text):
    """مدیریت مکالمه چندمرحله‌ای رزرو"""
    session = booking_sessions.get(chat_id)

    if session is None:
        # شروع فرآیند رزرو
        booking_sessions[chat_id] = {"step": "name"}
        send_message(chat_id, "عالیه! لطفاً اسم و فامیلت رو بنویس:")
        return

    step = session["step"]

    if step == "name":
        session["name"] = text
        session["step"] = "date"
        send_message(chat_id, "تاریخ موردنظر برای تور رو بنویس:")

    elif step == "date":
        session["date"] = text
        session["step"] = "count"
        send_message(chat_id, "تعداد نفرات چند نفره؟")

    elif step == "count":
        session["count"] = text
        save_booking(chat_id, session["name"], session["date"], session["count"])
        send_message(
            chat_id,
            f"رزرو تو ثبت شد ✅\nنام: {session['name']}\nتاریخ: {session['date']}\nتعداد: {session['count']}\nبه‌زودی باهات تماس می‌گیریم.",
        )
        del booking_sessions[chat_id]  # پایان مکالمه رزرو


@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()

    message = data.get("message")
    if not message:
        return jsonify({"ok": True})

    chat_id = message["chat"]["id"]
    text = message.get("text", "").strip()

    # اگه مشتری وسط فرآیند رزرو باشه، ادامه بده به همون فرآیند
    if chat_id in booking_sessions:
        handle_booking_flow(chat_id, text)
        return jsonify({"ok": True})

    # تشخیص قصد پیام
    if any(word in text for word in BOOKING_KEYWORDS):
        handle_booking_flow(chat_id, text)
        return jsonify({"ok": True})

    if any(word in text for word in CATALOG_KEYWORDS):
        send_document(chat_id, CATALOG_FILE_PATH)
        return jsonify({"ok": True})

    for keyword, answer in FAQ_RESPONSES.items():
        if keyword in text:
            send_message(chat_id, answer)
            return jsonify({"ok": True})

    # اگه هیچ‌کدوم تشخیص داده نشد
    send_message(
        chat_id,
        "سلام! می‌تونی درباره «قیمت»، «تور»، «ساعت کاری» بپرسی، بگی «رزرو» می‌خوای، یا بخوای «کاتالوگ» رو برات بفرستم.",
    )
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
