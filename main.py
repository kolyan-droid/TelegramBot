import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import os
from psycopg2.pool import ThreadedConnectionPool

token = os.environ.get("BOT_TOKEN")
bot = telebot.TeleBot(token, threaded=True, num_threads=10)
db_url = os.environ.get("DATABASE_URL")
pool = ThreadedConnectionPool(1, 10, db_url)

def log_user_action(user_id, action_text):
    connection = pool.getconn()
    try:
        with connection.cursor() as cursor:
            sql_request = "INSERT INTO activity_log (user_id, action) VALUES (%s, %s)"
            cursor.execute(sql_request, (user_id, action_text))
            connection.commit()
    finally:
        pool.putconn(connection)
@bot.callback_query_handler(func=lambda call: True)
def answer_callback(call):
    bot.answer_callback_query(call.id)
    if call.data.startswith("season:"):
        num_season = call.data.split(":")[-1]
        user_id = call.message.chat.id
        log_user_action(user_id, f"open_season:{num_season}")
        cnt_episodes = get_episodes_keyboard(num_season)
        bot.edit_message_text(f"Вы открыли {num_season} сезон. Выберите серию", chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=cnt_episodes)
    elif call.data.startswith("play:"):
        user_id = call.message.chat.id
        season, seria = call.data.split(":")[1:]
        key_fo_db = season + ":" + seria
        connection = pool.getconn()
        try:
            with connection.cursor() as cursor:
                sql_request = "SELECT id_video FROM episodes WHERE episode=%s"
                cursor.execute(sql_request, (key_fo_db,))
                result = cursor.fetchone()
                target_value = result[0]
                sql_request = "SELECT video_id FROM last_video WHERE user_id=%s"
                cursor.execute(sql_request, (user_id,))
                result_last_video = cursor.fetchone()
                if result_last_video is not None:
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
                sql_request = ("INSERT INTO last_video (user_id, video_id)"
                               " VALUES (%s, %s)"
                               "ON CONFLICT (user_id)"
                               "DO UPDATE SET video_id = EXCLUDED.video_id")
                cursor.execute(sql_request, (user_id, video_id,))
                cursor.execute("INSERT INTO activity_log (user_id, action) VALUES (%s, %s)", (user_id, f"play_episode:{key_fo_db}"))
                connection.commit()
                bot.delete_message(chat_id=call.message.chat.id, message_id=call.message.message_id)
                bot.send_message(call.message.chat.id, f"Вы смотрите {season} сезон {seria} серию. Выберите серию",
                                 reply_markup=cnt_episodes)

        finally:
            pool.putconn(connection)
    elif call.data == "to_main":
        user_id = call.message.chat.id
        log_user_action(user_id, f"to_main_menu")
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
    log_user_action(message.chat.id, f"send_start_message")
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

@bot.message_handler(commands=['admin_stats'])
def admin_stats(message):
    user_id = message.chat.id
    if user_id == 701316676:
        connection = pool.getconn()
        try:
            total_users = 0
            with connection.cursor() as cursor:
                cursor.execute("SELECT COUNT(DISTINCT user_id) FROM activity_log")
                result = cursor.fetchone()
                if result is not None:
                    total_users = result[0]
                else:
                    pass
                cursor.execute("""SELECT action, COUNT(*) FROM activity_log
                               WHERE action LIKE 'play_episode:%'
                               GROUP BY action
                               ORDER BY COUNT(*)
                               DESC LIMIT 5""")
                result = cursor.fetchall()
                text_report = ""
                for row in result:
                    text_report += f"{row[0]} - {row[1]} раз(а)\n"
                bot.send_message(message.chat.id, f"Всего пользователей: {total_users}\nТоп серий: {text_report}")
        finally:
            pool.putconn(connection)
    else:
        return

class WebHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(b"Bot is alive!")
    def log_message(self, format, *args):
        return

def run_web_server():
    import os
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), WebHandler)
    server.serve_forever()


threading.Thread(target=run_web_server, daemon=True).start()

bot.infinity_polling()
