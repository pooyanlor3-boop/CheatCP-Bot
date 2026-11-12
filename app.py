# Wrapper for PaaS platforms that expect app.py (ParsPack / Liara Flask)
# Real logic lives in bot.py — this file starts both web + Telegram bot.

from bot import app_web as app  # for servers that import "app"
from bot import run_flask, run_bot
import threading
import time

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    time.sleep(2)
    run_bot()
