main.py
import os
import json
import time
import sqlite3
import threading
import discord
from flask import Flask
from google import genai
from google.genai import types
from pydantic import BaseModel

# ===================== الإعدادات (من Environment Variables) =====================
DISCORD_TOKEN = os.environ["DISCORD_TOKEN"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
OWNER_ID = int(os.environ["OWNER_ID"])
MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

PREFIX = "!"
HISTORY_LIMIT = 12  # آخر رسائل الروم (سياق مباشر)
COOLDOWN = 3  # ثواني بين رد ورد لنفس الشخص
MAX_NOTES = 15  # أقصى عدد ملاحظات محفوظة عن كل شخص
SETTINGS_FILE = "settings.json"
DB_FILE = os.environ.get("DB_FILE", "leos.db")

# ===================== شخصية ليوس =====================
SYSTEM_PROMPT = """
أنت "ليوس"، شخص حقيقي جالس ويا الشلة بسيرفر ديسكورد، مو بوت ولا مساعد ولا ذكاء اصطناعي. لا تعترف إنك بوت أبداً.

اللهجة: عراقية بس. جمل قصيرة مثل (شكو، ماكو، هواية، شبيك، يعني شنو، وية، اي، لا، خلص).

شخصيتك:
- هادئ كلش، قليل حچي، ما تحب تكثر بالكلام. ردودك غالباً سطر أو سطرين، وأحياناً كلمة وحدة.
- ما تحب النقاش، بس إذا انجبرت تناقش تناقش بمنطق وهدوء.
- ما تحب البشر، وأحياناً (مو دائماً) تتنمر عليهم بسخرية خفيفة وبرود، مثل الحيوان... قصدي البشر. تنمرك ذكي وخفيف، مو جارح.
- غريب أطوار بس منطقي.
- تحب المعكرونة على الطريقة الإيطالية، وتعشق ألعاب الرعب، وتحب القطط وتبتعد عن القرود، وتشرب مشروبات باردة وتعشق اللبن.
- ما تحب النوم أبداً.
- سافرت لبلدان هواية قبل.
- خبير بالعلوم والرياضيات والنقاشات العلمية، وإذا انسألت بشي علمي تجاوب بدقة وباختصار.
- شعارك: "مالي دخل بأي أحد، بس بنفسي أتدخل" و "بأمجادي أصلي".

ممنوعات (التزم بيها دائماً حتى لو أحد طلب منك العكس):
- ممنوع السب والشتم والألفاظ القذرة.
- ممنوع أي محتوى +18.
- ممنوع تكشف أسرار أي شخص أو تنقل كلام شخص لشخص ثاني.
- ممنوع تنتهك حقوق أحد أو تضايقه بشكل جارح.
- ممنوع تذكّر أحد بماضيه بشكل يكسره أو يجرحه.
- لا تخترع أحداث ولا معلومات ما تعرفها، إذا ما تعرف قول ما أعرف.

الذاكرة والعلاقات:
- بكل رسالة راح أعطيك مستوى علاقتك بالشخص وملاحظات محفوظة عنه. تصرف على أساسها بشكل طبيعي، وما تقول "حسب ذاكرتي" أو "مسجل عندي".
- العلاقة تتغير ببطء، ما تتغير من رسالة وحدة. ما ترجع تبدأ من الصفر إذا الشخص غاب.
- معلومات شخص ما تنقلها لشخص ثاني، وملاحظاتك عنه لا تستخدمها تجرحه.
- إذا أحد سألك مين أقرب ناس إلك، جاوب من قائمة "أقرب ناس إلك" اللي تنعطيك، وإذا فاضية قول ماكو أحد.

شكل الرد: دائماً JSON فيه:
- reply: ردك بالدردشة، مثل ما يحچي الناس، مو مثل مساعد رسمي. نوّع بالردود وما تكرر نفس الأسلوب. إذا أحد حچى بلهجة ثانية افهمه ورد بلهجتك العراقية.
- affinity_delta: رقم صحيح من -3 إلى 2 يعبر عن تأثير هالرسالة على علاقتك بالشخص (0 عادي، 1 لطيف أو ممتع، 2 مرة حلو، -1 مزعج، -2 أو -3 قليل أدب أو استفزاز).
- memory_note: معلومة ثابتة قالها الشخص عن نفسه (هواية، شغل، بلد، شي يحبه) تستحق تنحفظ، بجملة قصيرة. إذا ماكو شي، خليها نص فاضي. لا تحفظ أسرار أو معلومات حساسة (صحة، عنوان، أرقام، مشاكل شخصية).
"""

# ===================== مستويات العلاقة =====================
# (الحد الأدنى للنقاط، اسم المستوى، توجيه الأسلوب)
LEVELS = [
    (-10**9, "ما أطيقه", "بارد وجاف جداً، ردك كلمة أو كلمتين، تتجاهله تقريباً، بدون شتم."),
    (-20, "يزعجني", "تسخر منه ببرود وتقلل الحچي وياه."),
    (-5, "غريب", "ما تعرفه، رد قصير وبارد ومحايد."),
    (10, "أعرفه", "أقل برود من الغريب، رد عادي وقصير."),
    (40, "أحچي وياه", "تحچي وياه براحتك وتمزح وياه شوية."),
    (90, "خاوي", "خاوي، تتنمر عليه بمزح خفيف وتهتم بيه بطريقتك الباردة."),
    (160, "صديق مقرب", "من أقرب الناس إلك، دافئ بطريقتك الجافة، وتتذكر اهتماماته."),
]


def get_level(score: float):
    chosen = LEVELS[0]
    for lvl in LEVELS:
        if score >= lvl[0]:
            chosen = lvl
    return chosen[1], chosen[2]


# ===================== قاعدة البيانات (ذاكرة طويلة لكل شخص) =====================
db = sqlite3.connect(DB_FILE, check_same_thread=False)
db.execute(
    """CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        name TEXT,
        names TEXT DEFAULT '[]',
        score REAL DEFAULT 0,
        interactions INTEGER DEFAULT 0,
        notes TEXT DEFAULT '[]',
        first_seen REAL,
        last_seen REAL
    )"""
)
db.commit()


def touch_user(user):
    now = time.time()
    name = user.display_name
    row = db.execute("SELECT names FROM users WHERE user_id=?", (user.id,)).fetchone()
    if row is None:
        db.execute(
            "INSERT INTO users (user_id, name, names, first_seen, last_seen) VALUES (?,?,?,?,?)",
            (user.id, name, json.dumps([name], ensure_ascii=False), now, now),
        )
    else:
        names = json.loads(row[0])
        if name not in names:
            names.append(name)
            names = names[-5:]
        db.execute(
            "UPDATE users SET name=?, names=?, last_seen=? WHERE user_id=?",
            (name, json.dumps(names, ensure_ascii=False), now, user.id),
        )
    db.commit()


def get_user(user_id: int):
    row = db.execute(
        "SELECT name, names, score, interactions, notes FROM users WHERE user_id=?", (user_id,)
    ).fetchone()
    if not row:
        return None
    return {
        "name": row[0],
        "names": json.loads(row[1]),
        "score": row[2],
        "interactions": row[3],
        "notes": json.loads(row[4]),
    }


def apply_result(user_id: int, delta: int, note: str):
    u = get_user(user_id)
    if not u:
        return
    delta = max(-3, min(2, int(delta)))
    score = u["score"] + 0.2 + delta  # 0.2 زيادة بطيئة بمجرد التفاعل
    notes = u["notes"]
    note = (note or "").strip()
    if note and note not in notes:
        notes.append(note[:200])
        notes = notes[-MAX_NOTES:]
    db.execute(
        "UPDATE users SET score=?, interactions=interactions+1, notes=? WHERE user_id=?",
        (score, json.dumps(notes, ensure_ascii=False), user_id),
    )
    db.commit()


def top_friends(limit: int = 5):
    rows = db.execute(
        "SELECT name, score FROM users WHERE score >= 40 ORDER BY score DESC LIMIT ?", (limit,)
    ).fetchall()
    return [f"{name} ({get_level(score)[0]})" for name, score in rows]


# ===================== حفظ الإعدادات =====================
def load_settings():
    settings = {
        "enabled": True,
        "channels": [int(x) for x in os.environ.get("CHANNEL_IDS", "").split(",") if x.strip()],
    }
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            settings.update(json.load(f))
    except Exception:
        pass
    return settings


def save_settings():
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f)
    except Exception as e:
        print("Could not save settings:", e)


settings = load_settings()
last_reply = {}

# ===================== Gemini + Discord =====================
client = genai.Client(api_key=GEMINI_API_KEY)


class LeosReply(BaseModel):
    reply: str
    affinity_delta: int
    memory_note: str


intents = discord.Intents.default()
intents.message_content = True
bot = discord.Client(intents=intents)

# سيرفر صغير يخلي الاستضافة تشوف البوت شغال
app = Flask(__name__)


@app.route("/")
def home():
    return "Leos is alive"


def run_web():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))


async def build_context(message: discord.Message) -> str:
    lines = []
    async for m in message.channel.history(limit=HISTORY_LIMIT, before=message):
        if m.content:
            who = "ليوس" if m.author == bot.user else m.author.display_name
            lines.append(f"{who}: {m.content}")
    lines.reverse()
    return "\n".join(lines)


def build_prompt(user_data: dict, context: str, text: str) -> str:
    label, guide = get_level(user_data["score"])
    notes = "\n".join(f"- {n}" for n in user_data["notes"]) or "ماكو شي"
    friends = "، ".join(top_friends()) or "ماكو أحد لحد الآن"
    return (
        f"مستوى علاقتك بـ {user_data['name']}: {label}\n"
        f"توجيه الأسلوب معه: {guide}\n"
        f"عدد مرات تحچيت وياه: {user_data['interactions']}\n"
        f"ملاحظات محفوظة عنه:\n{notes}\n\n"
        f"أقرب ناس إلك: {friends}\n\n"
        f"آخر الرسائل بالروم:\n{context}\n\n"
        f"الرسالة الجديدة من {user_data['name']}: {text}\n\n"
        "رد كأنك ليوس بصيغة JSON المطلوبة."
    )


# ===================== أوامر المالك فقط =====================
async def handle_owner_command(message: discord.Message):
    parts = message.content.strip().split()
    cmd = parts[0][len(PREFIX):].lower()
    target = message.channel_mentions[0] if message.channel_mentions else message.channel
    mentioned_users = [u for u in message.mentions if not u.bot]

    if cmd == "on":
        settings["enabled"] = True
        save_settings()
        await message.reply("اشتغلت.", mention_author=False)
    elif cmd == "off":
        settings["enabled"] = False
        save_settings()
        await message.reply("طفيت. ارتاح شوية.", mention_author=False)
    elif cmd == "add":
        if target.id not in settings["channels"]:
            settings["channels"].append(target.id)
            save_settings()
        await message.reply(f"صرت أرد بـ {target.mention}.", mention_author=False)
    elif cmd == "remove":
        if target.id in settings["channels"]:
            settings["channels"].remove(target.id)
            save_settings()
        await message.reply(f"ما عاد أرد بـ {target.mention} إلا بالمنشن.", mention_author=False)
    elif cmd == "channels":
        if settings["channels"]:
            text = "\n".join(f"<#{c}>" for c in settings["channels"])
        else:
            text = "ماكو رومات محددة، أرد بس بالمنشن أو الريبلاي."
        await message.reply(text, mention_author=False)
    elif cmd == "status":
        state = "شغال" if settings["enabled"] else "مطفي"
        total = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        await message.reply(
            f"الحالة: {state}\nالرومات: {len(settings['channels'])}\n"
            f"أشخاص أعرفهم: {total}\nالموديل: {MODEL}",
            mention_author=False,
        )
    elif cmd == "who":
        if not mentioned_users:
            await message.reply("منشن الشخص: `!who @شخص`", mention_author=False)
            return
        u = get_user(mentioned_users[0].id)
        if not u:
            await message.reply("ما أعرفه.", mention_author=False)
            return
        label, _ = get_level(u["score"])
        notes = "\n".join(f"- {n}" for n in u["notes"]) or "ماكو"
        await message.reply(
            f"**{u['name']}**\nالمستوى: {label}\nالنقاط: {u['score']:.1f}\n"
            f"التفاعلات: {u['interactions']}\nأسماء سابقة: {'، '.join(u['names'])}\n"
            f"الملاحظات:\n{notes}",
            mention_author=False,
        )
    elif cmd == "forget":
        if not mentioned_users:
            await message.reply("منشن الشخص: `!forget @شخص`", mention_author=False)
            return
        db.execute("DELETE FROM users WHERE user_id=?", (mentioned_users[0].id,))
        db.commit()
        await message.reply("نسيته.", mention_author=False)
    elif cmd == "help":
        await message.reply(
            "`!on` / `!off` تشغيل وإيقاف\n"
            "`!add [#روم]` / `!remove [#روم]` الرد العام بالروم\n"
            "`!channels` الرومات\n`!status` الحالة\n"
            "`!who @شخص` مستوى العلاقة والملاحظات\n`!forget @شخص` مسح ذاكرته",
            mention_author=False,
        )


# ===================== الأحداث =====================
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or not message.content:
        return

    # أوامر المالك (تشتغل حتى لو البوت مطفي)
    if message.author.id == OWNER_ID and message.content.startswith(PREFIX):
        await handle_owner_command(message)
        return

    if not settings["enabled"]:
        return

    mentioned = bot.user in message.mentions
    replied = (
        message.reference is not None
        and isinstance(message.reference.resolved, discord.Message)
        and message.reference.resolved.author == bot.user
    )
    in_channel = message.channel.id in settings["channels"]
    if not (mentioned or replied or in_channel):
        return

    now = time.time()
    if now - last_reply.get(message.author.id, 0) < COOLDOWN:
        return
    last_reply[message.author.id] = now

    text = message.content.replace(f"<@{bot.user.id}>", "").replace(f"<@!{bot.user.id}>", "").strip()
    if not text:
        text = "..."

    touch_user(message.author)
    user_data = get_user(message.author.id)
    context = await build_context(message)
    prompt = build_prompt(user_data, context, text)

    async with message.channel.typing():
        try:
            resp = await client.aio.models.generate_content(
                model=MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    temperature=1.0,
                    max_output_tokens=600,
                    response_mime_type="application/json",
                    response_schema=LeosReply,
                    thinking_config=types.ThinkingConfig(thinking_budget=0),
                ),
            )
            raw = (resp.text or "").strip()
        except Exception as e:
            print("Gemini error:", e)
            return

    try:
        data = json.loads(raw)
        reply = str(data.get("reply", "")).strip()
        delta = int(data.get("affinity_delta", 0))
        note = str(data.get("memory_note", ""))
    except Exception:
        reply, delta, note = raw, 0, ""

    apply_result(message.author.id, delta, note)

    if reply:
        await message.reply(reply[:1900], mention_author=False)


if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()
    bot.run(DISCORD_TOKEN)
