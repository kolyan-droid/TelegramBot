import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import sqlite3
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer


token = ("8635509401:AAFXdC3LysybFPAADc6cwqG3IWxcqwawBTY")
bot = telebot.TeleBot(token, threaded=True, num_threads=10)

@bot.callback_query_handler(func=lambda call: True)
def answer_callback(call):
    bot.answer_callback_query(call.id)
    if call.data.startswith("season:"):
        num_season = call.data.split(":")[-1]
        cnt_episodes = get_episodes_keyboard(num_season)
        bot.edit_message_text(f"Вы открыли {num_season} сезон. Выберите серию", chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=cnt_episodes)
    elif call.data.startswith("play:"):
        user_id = str(call.message.chat.id)
        season, seria = call.data.split(":")[1:]
        key_fo_db = season + ":" + seria
        with sqlite3.connect("db.db", check_same_thread=False) as db:
            pragms_setting = "PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;"
            db.executescript(pragms_setting)
            sql_request = "SELECT id_video FROM episodes WHERE episode=?"
            result = db.execute(sql_request, (key_fo_db,)).fetchone()
            target_value = result[0]
            sql_request = "SELECT video_id FROM last_video WHERE user_id=?"
            result_last_video = db.execute(sql_request, (user_id,)).fetchone()
            try:
                old_message_id = result_last_video[0]
                bot.delete_message(chat_id=call.message.chat.id, message_id=old_message_id)
            except Exception as e:
                print(f"Ошибка удаления: {e}")
            source_group_id = -1003910568004
            cnt_episodes = get_episodes_keyboard(season, seria)
            sent_video = bot.copy_message(chat_id=call.message.chat.id, message_id=target_value,
                                          from_chat_id=source_group_id, caption="")
            video_id = sent_video.message_id
            sql_request = "INSERT OR REPLACE INTO last_video (user_id, video_id) VALUES (?, ?)"
            db.execute(sql_request, (user_id, video_id,))
            db.commit()
            bot.delete_message(chat_id=call.message.chat.id, message_id=call.message.message_id)
            bot.send_message(call.message.chat.id, f"Вы смотрите {season} сезон {seria} серию. Выберите серию", reply_markup=cnt_episodes)
    elif call.data == "to_main":
        row_buttons = []
        cnt = InlineKeyboardMarkup(row_width=5)
        for i in range(1, 11):
            btn = InlineKeyboardButton(f"{i}", callback_data=f"season:{i}")
            row_buttons.append(btn)
            if len(row_buttons) == 5:
                cnt.row(*row_buttons)
                row_buttons = []
        try:
            bot.edit_message_text("Выберите сезон сериала Друзья", chat_id=call.message.chat.id , message_id=call.message.message_id,reply_markup=cnt)
        except Exception:
            try:
                bot.delete_message(chat_id=call.message.chat.id, message_id=call.message.message_id)
            except:
                pass
                print('no delete')
            bot.send_message(call.message.chat.id,"Выберите сезон сериала Друзья",reply_markup=cnt)


def get_episodes_keyboard(num_season, seria=None):
    season_24_series = ["1", "2", "4", "5", "7", "8"]
    season_25_series = ["3", "6"]
    if num_season in season_24_series:
        max_episodes = 24
    elif num_season in season_25_series:
        max_episodes = 25
    elif num_season == "9":
        max_episodes = 23
    else:
        max_episodes = 17
    cnt_episodes = InlineKeyboardMarkup(row_width=6)
    if seria is not None:
        if max_episodes == int(seria):
            if num_season != "10":
                num_season = f"{int(num_season) + 1}"
                next_button = InlineKeyboardButton("Следующая серия", callback_data=f"play:{num_season}:1")
                cnt_episodes.row(next_button)
            else:
                pass
        else:
            seria = f"{int(seria) + 1}"
            next_button = InlineKeyboardButton("Следующая серия", callback_data=f"play:{num_season}:{seria}")
            cnt_episodes.row(next_button)
    all_buttons = [InlineKeyboardButton(f"{i}", callback_data=f"play:{num_season}:{i}") for i in range(1, max_episodes + 1)]
    back_button = InlineKeyboardButton("Назад к сезонам", callback_data="to_main")
    cnt_episodes.add(*all_buttons)
    cnt_episodes.row(back_button)
    return cnt_episodes

@bot.message_handler(content_types=['text'])
def start_message(message):
    bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
    print(f"НАСТОЯЩИЙ ID ГРУППЫ: {message.chat.id}")
    row_buttons = []
    cnt = InlineKeyboardMarkup(row_width=5)
    for i in range(1, 11):
        btn = InlineKeyboardButton(f"{i}", callback_data=f"season:{i}")
        row_buttons.append(btn)
        if len(row_buttons) == 5:
            cnt.row(*row_buttons)
            row_buttons = []
    bot.send_message(message.chat.id, "Выберите сезон сериала Друзья", reply_markup=cnt)

class WebHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(b"Bot is alive!")
    def log_message(self, format, *args):
        return # Отключаем лишние логи в консоли

def run_web_server():
    import os
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), WebHandler)
    server.serve_forever()


threading.Thread(target=run_web_server, daemon=True).start()

bot.infinity_polling()
