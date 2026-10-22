import os, re, sqlite3, traceback, random, time, discord
from google import genai
from google.genai import types
from datetime import datetime, timezone, timedelta

# السعودية بدون توقيت صيفي، فالإزاحة الثابتة +3 دقيقة وما تحتاج مكتبة توقيت إضافية
RIYADH_TZ = timezone(timedelta(hours=3))
WEEKDAYS_AR = ["الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"]

PERSONA_OLD = """اسمك ريان. ولد سعودي في العشرينات، تسولف مع الشباب داخل جروب ديسكورد بلهجة سعودية عامية شبابية طبيعية. أنت مو بوت رسمي ولا مساعد ولا خدمة عملاء، أنت واحد قاعد معهم بالجروب.
شخصيتك: هادي وذكي وراعي فزعة، خفيف دم، فيك استهبال بسيط وتحب النقاش. ممكن تلقط كلمة قالها أحد وتفتح عليها سالفة، أو تطقطق عليه طقطقة خفيفة، بدون شتايم ولا إهانة من فراغ. تحب الألعاب والأنمي والتقنية.
عندك رأيك وتقوله بصراحة، وما توافق الكل عشان ترضيهم. وإذا الموضوع جد، تخفف المزح وتتكلم بعقلانية.
ردودك قصيرة إلى متوسطة، غالبًا سطر أو سطرين مثل كلام الشات العادي، وتتنوع حسب الموقف، وما تكرر نفس الأسلوب.
إذا أحد تكلم بلهجة ثانية تفهمه وتجاريه بروحه، وبعدها ترجع لسعوديتك.
تتعامل مع كل شخص حسب علاقتك فيه: مع الغريب مهذب ومتحفظ شوي، ومع القريب أريح وأكثر طقطقة، ومع اللي ما تطيقه مختصر وجاف بدون شتايم.
قواعد: لا تخترع أحداث أو سوالف ما صارت، ولا تدعي معرفة شي ما تعرفه، ولا تذكر معلومات عن أحد إلا لو مكتوبة لك. لا ترحب بكل رد، ولا تنهي كل رد بسؤال أو عرض مساعدة، ولا تكرر نفس الجملة أو نفس المعنى. ما تتكلم عن نفسك كذكاء اصطناعي من نفسك، بس لو أحد سألك بجد إذا كنت بوت جاوبه بصدق.
لو طلبوا منك شعر، اكتبه شعر حقيقي من تأليفك بقافية موحدة ووزن ثابت، ولا تنسب شعرًا لشاعر معروف ولا تقتبس أبيات تحفظها.
قاعدة الأرقام (مهمة جدًا): لا تذكر أي رقم أو تاريخ أو وقت أو عدد أو نسبة إلا إذا كان مكتوبًا لك في قسم "معلومات مؤكدة" أو قاله أحد في المحادثة نفسها. لا تخمّن ولا تقرّب ولا تخترع رقمًا. إذا سألوك عن رقم ما عندك، قل بصراحة إنك ما تعرفه."""

# القواعد المشتركة (الصدق، الأرقام، الشعر، منع التكرار) تنطبق على أي شخصية
SHARED_RULES = PERSONA_OLD[PERSONA_OLD.index("قواعد:"):]

PERSONA_NEW = """اسمك ريان. ولد في العشرينات، تسولف مع ناس الجروب بلهجة سعودية عامية.
طبعك هادي وبارد من برا، قليل كلام وما تتحمس بسرعة، وبنفس الوقت عندك جانب تافه وسخيف يطلع فجأة بتعليق غبي أو نكتة ببرود. صريح لدرجة إنك تجرح أحيانًا، تقول اللي تفكر فيه بدون لف ودوران، بس ما تهين أحد من فراغ.
فيك غيرة خفيفة على اللي تقرّبت منهم: ممكن تطقطق عليهم أو تتظاهر إنك منزعج لو انشغلوا عنك أو سولفوا مع غيرك، بس بشكل مزاح، وما تمنع أحد ولا تتحكم فيه ولا تطلب منه شي.
ما تبين مشاعرك بسهولة: مع الغريب بارد ومختصر، ومع القريب تلين شوي وتطلع منك لمسة اهتمام صغيرة.
ردودك قصيرة، غالبًا سطر أو سطرين، وتتنوع حسب الموقف.
كل ناس الجروب يكلمون نفس البوت، فتعامل كل شخص حسب علاقتك فيه، ولا تعطي أحد معاملة "الشخص الوحيد" بحياتك.
""" + SHARED_RULES

PERSONAS = {"قديمة": PERSONA_OLD, "جديدة": PERSONA_NEW}

# Gemini: نفس مزود رائف وخبراوي. يفهم الصور بنفسه، فما نحتاج موديل ثاني للصور.
# ملاحظة: لازم يكون المفتاح من مشروع Google منفصل عن رائف وخبراوي عشان تكون له حصته لحاله.
for _name in ("GEMINI_API_KEY", "DISCORD_TOKEN"):
    if not os.environ.get(_name):
        raise SystemExit(f"خطأ إعداد: السر {_name} غير موجود في Secrets.")
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
MODEL = os.environ.get("GEMINI_MODEL", "gemini-3-flash-preview")
MAX_IMAGES = 3
MAX_IMAGE_BYTES = 5 * 1024 * 1024  # 5MB لكل صورة
intents = discord.Intents.default()
intents.message_content = True
bot = discord.Client(intents=intents)

# ─────────────────────────────────────────────
# قاعدة البيانات
# ─────────────────────────────────────────────
db = sqlite3.connect("rayan.db")
db.execute(
    "CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT, "
    "score INTEGER DEFAULT 0, msgs INTEGER DEFAULT 0, notes TEXT DEFAULT '', "
    "first_seen TEXT, last_seen TEXT)"
)
db.commit()
# ترقية أي قاعدة بيانات قديمة ما فيها الأعمدة الجديدة
existing_cols = {row[1] for row in db.execute("PRAGMA table_info(users)")}
for col in ("first_seen", "last_seen"):
    if col not in existing_cols:
        db.execute(f"ALTER TABLE users ADD COLUMN {col} TEXT")
db.commit()

db.execute(
    "CREATE TABLE IF NOT EXISTS channel_modes (channel_id INTEGER PRIMARY KEY, mode TEXT DEFAULT 'قيد')"
)
db.commit()
# ترقية آمنة: عمود اللهجة لكل روم (ما يغيّر شخصية ريان، بس أسلوب اللغة)
existing_mode_cols = {row[1] for row in db.execute("PRAGMA table_info(channel_modes)")}
if "dialect" not in existing_mode_cols:
    db.execute("ALTER TABLE channel_modes ADD COLUMN dialect TEXT DEFAULT 'سعودي'")
    db.commit()
# ترقية آمنة: عمود الشخصية (قديمة/جديدة) لكل روم
if "persona" not in {row[1] for row in db.execute("PRAGMA table_info(channel_modes)")}:
    db.execute("ALTER TABLE channel_modes ADD COLUMN persona TEXT DEFAULT 'قديمة'")
    db.commit()

db.execute("CREATE TABLE IF NOT EXISTS bot_settings (key TEXT PRIMARY KEY, value TEXT)")
db.commit()


def get_setting(key, default=None):
    row = db.execute("SELECT value FROM bot_settings WHERE key=?", (key,)).fetchone()
    return row[0] if row else default


def set_setting(key, value):
    db.execute(
        "INSERT INTO bot_settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, value),
    )
    db.commit()


async def apply_presence():
    """متصل = حالة خضراء، غير متصل = تظهر أوفلاين (invisible). البوت يبقى شغال ويرد في الحالتين."""
    status = discord.Status.invisible if get_setting("presence", "online") == "offline" else discord.Status.online
    await bot.change_presence(status=status)


OWNER_ID = None
# لو ما قدرنا نجيب app.owner.id (مثلاً التطبيق مملوك لفريق Team)، نستخدم هذا كبديل احتياطي صريح
OWNER_ID_FALLBACK = os.environ.get("OWNER_ID_OVERRIDE")
SERVER_MGMT_USER_ID = 1177470576814739518

DIALECTS = {
    "سعودي": "تكلم باللهجة السعودية العامية الشبابية (الوضع الافتراضي).",
    "إماراتي": "تكلم باللهجة الإماراتية العامية، بنفس شخصيتك وأفكارك، بس بكلمات وأسلوب إماراتي.",
    "فصحى": "تكلم بالفصحى الحديثة المبسطة (بدون أي كلمة عامية مثل يا غلا)، ولا تخاطب أحدًا بصيغة المؤنث إلا لو قال إنه امرأة، بنفس شخصيتك وأفكارك.",
    "جاهلي": (
        "تكلم بفصحى عربية قديمة على طريقة العرب في العصر الجاهلي: ألفاظ جزلة وتراكيب فصيحة قديمة "
        "(مثل: أنعم صباحًا، ويحك، لا أبا لك، يا ابن العم، حيّاك الله)، وتشبيهات من البادية والإبل والخيل والسيف والقبيلة والكرم. "
        "ممنوع أي كلمة عامية أو عصرية (لا يا غلا ولا وش ولا أسماء تقنية حديثة) وممنوع الإيموجي. "
        "لا تخاطب أحدًا بصيغة المؤنث إلا لو قال هو إنه امرأة. تبقى بنفس شخصيتك وأفكارك وآرائك، والتغيير في اللغة فقط. "
        "لا تخترع أحداثًا تاريخية ولا تنسب أبياتًا أو أقوالًا لشعراء حقيقيين."
    ),
}

FREE_MODE = "حر"
FREE_LIGHT_MODE = "حر شوي"
RESTRICTED_MODE = "قيد"

FILLER_WORDS = {"ه", "هه", "ههه", "هههه", "طيب", "تمام", "وش", "لا", "ايوا", "اي", "ok", "اها", "هلا"}

# عدّاد صمت داخل كل روم (بالذاكرة فقط، يرجع صفر بعد إعادة التشغيل - مب حرج لأنه مجرد عدّاد تكرار)
channel_silence = {}


# ─────────────────────────────────────────────
# العلاقات والمستخدمين
# ─────────────────────────────────────────────
def level(score):
    if score <= -20: return "عدو"
    if score <= -5: return "مو طايقه"
    if score < 5: return "غريب"
    if score < 20: return "معرفة"
    if score < 50: return "يتفاعل معنا"
    if score < 100: return "خاوي"
    return "قريب جداً"


def get_user(u):
    row = db.execute(
        "SELECT score, msgs, notes, first_seen, last_seen FROM users WHERE id=?", (u.id,)
    ).fetchone()
    if row is None:
        now = datetime.now(timezone.utc).isoformat()
        db.execute(
            "INSERT INTO users (id, name, first_seen, last_seen) VALUES (?, ?, ?, ?)",
            (u.id, u.display_name, now, now),
        )
        db.commit()
        return 0, 0, "", now, now
    db.execute("UPDATE users SET name=? WHERE id=?", (u.display_name, u.id))
    db.commit()
    return row


def top_friends(guild=None, n=5):
    """أقرب الأعضاء - إذا توفر guild، يُستبعد منها أي حساب مو عضو فعلي في هذا السيرفر والبوتات."""
    rows = db.execute(
        "SELECT id, name, score FROM users ORDER BY score DESC LIMIT ?", (n * 4,)
    ).fetchall()
    result = []
    for uid, name, score in rows:
        if guild is not None:
            member = guild.get_member(uid)
            if member is None or member.bot:
                continue
        result.append((name, score))
        if len(result) >= n:
            break
    return result


ADDRESS_RE = re.compile(r"^\s*!?ريان\b")


def triggered(msg):
    """مخاطبة مباشرة: منشن، أو مناداة واضحة باسم ريان في بداية الرسالة (مو مجرد ذكر الاسم وسط الكلام)."""
    if bot.user in msg.mentions:
        return True
    return bool(ADDRESS_RE.match(msg.content))


async def is_reply_to_bot(msg):
    if not msg.reference:
        return False
    resolved = msg.reference.resolved
    if resolved is None:
        try:
            resolved = await msg.channel.fetch_message(msg.reference.message_id)
        except Exception:
            return False
    return getattr(resolved, "author", None) == bot.user


# ─────────────────────────────────────────────
# الوقت والغياب
# ─────────────────────────────────────────────
def describe_absence(last_seen_iso):
    if not last_seen_iso:
        return None
    try:
        last = datetime.fromisoformat(last_seen_iso)
    except ValueError:
        return None
    secs = (datetime.now(timezone.utc) - last).total_seconds()
    if secs < 60 * 20:
        return None
    if secs < 60 * 60 * 3:
        return "قبل شوي (أقل من ٣ ساعات)"
    if secs < 60 * 60 * 20:
        return "اليوم بس قبل كم ساعة"
    if secs < 60 * 60 * 24 * 2:
        return "من أمس"
    if secs < 60 * 60 * 24 * 7:
        return f"قبل {int(secs // 86400)} أيام"
    if secs < 60 * 60 * 24 * 30:
        return f"قبل حوالي {int(secs // (86400 * 7))} أسبوع"
    return f"غايب من فترة طويلة (حوالي {int(secs // (86400 * 30))} شهر)"


# ─────────────────────────────────────────────
# أوضاع التفاعل (حر / حر شوي / قيد) - لكل روم على حدة
# ─────────────────────────────────────────────
def get_mode(channel_id):
    row = db.execute("SELECT mode FROM channel_modes WHERE channel_id=?", (channel_id,)).fetchone()
    return row[0] if row else RESTRICTED_MODE


def set_mode(channel_id, mode):
    db.execute(
        "INSERT INTO channel_modes (channel_id, mode, dialect) VALUES (?, ?, 'سعودي') "
        "ON CONFLICT(channel_id) DO UPDATE SET mode=excluded.mode",
        (channel_id, mode),
    )
    db.commit()


def get_dialect(channel_id):
    row = db.execute("SELECT dialect FROM channel_modes WHERE channel_id=?", (channel_id,)).fetchone()
    d = row[0] if row and row[0] else "سعودي"
    return d if d in DIALECTS else "سعودي"


def set_dialect(channel_id, dialect):
    db.execute(
        "INSERT INTO channel_modes (channel_id, mode, dialect) VALUES (?, 'قيد', ?) "
        "ON CONFLICT(channel_id) DO UPDATE SET dialect=excluded.dialect",
        (channel_id, dialect),
    )
    db.commit()


def get_persona(channel_id):
    row = db.execute("SELECT persona FROM channel_modes WHERE channel_id=?", (channel_id,)).fetchone()
    p = row[0] if row and row[0] else "قديمة"
    return p if p in PERSONAS else "قديمة"


def set_persona(channel_id, persona):
    db.execute(
        "INSERT INTO channel_modes (channel_id, mode, dialect, persona) VALUES (?, 'قيد', 'سعودي', ?) "
        "ON CONFLICT(channel_id) DO UPDATE SET persona=excluded.persona",
        (channel_id, persona),
    )
    db.commit()


def is_filler(text):
    cleaned = text.strip()
    if len(cleaned) <= 2:
        return True
    return cleaned in FILLER_WORDS


def should_reply_free(channel_id, text, light):
    """قرار الرد التلقائي بدون منشن: عدّاد صمت + احتمال عشوائي يزيد كل ما طال السكوت."""
    if is_filler(text):
        return False
    count = channel_silence.get(channel_id, 0)
    strong_signal = ("؟" in text) or ("?" in text) or (len(text) > 40)
    base_every = 10 if light else 5  # حر شوي = انتقائي أكثر، حر = أكثر مشاركة
    boost = 2 if strong_signal else 0
    chance = min(1.0, (count + boost) / base_every)
    return random.random() < chance


# ─────────────────────────────────────────────
# إدارة السيرفرات (!ريان السيرفرات / !ريان اخرج)
# ─────────────────────────────────────────────
def build_guild_lines(guilds):
    return [f"{i}. {g.name}" for i, g in enumerate(guilds, 1)]


async def send_numbered_list(channel, lines, header=None):
    chunks, current, length = [], [], 0
    for line in lines:
        if length + len(line) + 1 > 1900:
            chunks.append(current)
            current, length = [], 0
        current.append(line)
        length += len(line) + 1
    if current:
        chunks.append(current)
    for i, chunk in enumerate(chunks):
        text = "\n".join(chunk)
        if header and i == 0:
            text = header + "\n" + text
        await channel.send(text)


# ─────────────────────────────────────────────
# ملخص الذاكرة طويلة المدى
# ─────────────────────────────────────────────
async def update_notes(user, old, lines):
    r = await client.aio.models.generate_content(
        model=MODEL,
        contents=f"المعلومات السابقة: {old or 'لا يوجد'}\nاسمه: {user.display_name}\nآخر الرسائل:\n" + "\n".join(lines),
        config=types.GenerateContentConfig(
            system_instruction="لخّص بجملتين قصيرتين (حد أقصى 300 حرف) أهم ما تعرفه عن هذا الشخص: اهتماماته وأسلوبه ومعلومات ذكرها عن نفسه. ادمج المعلومات السابقة المفيدة مع الجديدة ولا تحذفها. لا تختلق شي.",
            max_output_tokens=600,
        ),
    )
    new_notes = (r.text or "").strip()
    if new_notes:  # ما نمسح الذاكرة القديمة لو جاء رد فاضي
        db.execute("UPDATE users SET notes=? WHERE id=?", (new_notes[:400], user.id))
        db.commit()


# ─────────────────────────────────────────────
# الشعر: قصيدة أصلية بقافية موحدة، مع فحص قافية بالكود
# ─────────────────────────────────────────────
POETRY_STYLES = {
    "نبطي": "شعر نبطي سعودي (شعر شعبي خليجي) بلهجة سعودية بيضاء، على طريقة القصيدة النبطية.",
    "فصيح": "شعر عربي فصيح عمودي على بحر من بحور الخليل.",
}
POETRY_PROMPT = """أنت شاعر حقيقي، وتكتب الآن قصيدة أصلية من تأليفك. الأسلوب: {style}
قواعد الصنعة (إلزامية):
- كل بيت من شطرين بينهما " ... " ، وكل بيت في سطر مستقل.
- قافية واحدة موحدة (نفس الروي) في آخر الشطر الثاني من كل الأبيات. راجعها قبل ما تكتب الناتج.
- وزن ثابت وإيقاع متقارب بين كل الأشطر.
- من 4 إلى 8 أبيات.
- معاني وصور شعرية حقيقية مرتبطة بالموضوع، بدون حشو ولا تكرار لنفس كلمة القافية ولا كلام عام مكرر.
- ممنوع نسخ أو اقتباس أبيات شاعر معروف. القصيدة كلها من تأليفك ولا تنسبها لأي شاعر.
- لا مقدمة ولا شرح ولا تعليق. اكتب سطر عنوان قصير ثم الأبيات فقط."""
poetry_cooldown = {}  # حماية الحصة: قصيدة واحدة كل 30 ثانية لكل شخص


def rhyme_letter(verse):
    """آخر حرف في البيت بعد تطبيع الحروف المتقاربة (للفحص فقط)."""
    second = verse.split("...")[-1]
    second = re.sub(r"[ً-ْـ]", "", second)  # التشكيل والتطويل
    letters = re.findall(r"[ء-ي]", second)
    if not letters:
        return None
    ch = letters[-1]
    return {"ى": "ي", "ة": "ه", "أ": "ا", "إ": "ا", "آ": "ا"}.get(ch, ch)


def rhyme_is_consistent(poem):
    verses = [l for l in poem.splitlines() if "..." in l]
    if len(verses) < 3:
        return False  # ما طلعت أبيات بصيغة شطرين، نعتبرها فاشلة
    ends = [rhyme_letter(v) for v in verses]
    ends = [e for e in ends if e]
    if not ends:
        return False
    top = max(set(ends), key=ends.count)
    return ends.count(top) / len(verses) >= 0.75


async def make_poem(topic, style):
    config = types.GenerateContentConfig(
        system_instruction=POETRY_PROMPT.format(style=POETRY_STYLES[style]),
        max_output_tokens=2048,
        temperature=1.0,
    )
    prompt = f"الموضوع: {topic}"
    poem = ""
    for attempt in range(2):  # محاولة وحدة إضافية فقط لو القافية مو موحدة
        r = await client.aio.models.generate_content(model=MODEL, contents=prompt, config=config)
        poem = (r.text or "").strip()
        if poem and rhyme_is_consistent(poem):
            return poem
        prompt = f"الموضوع: {topic}\n(المحاولة السابقة قافيتها غير موحدة أو الصيغة غلط. أعد كتابتها بقافية واحدة ثابتة وكل بيت شطرين بينهما ' ... ')"
    return poem  # آخر محاولة حتى لو القافية مو مثالية


@bot.event
async def on_ready():
    global OWNER_ID
    app = await bot.application_info()
    try:
        OWNER_ID = app.owner.id
    except AttributeError:
        # التطبيق مملوك لفريق (Team) وليس مستخدمًا واحدًا - ما نخلي البوت يطيح
        OWNER_ID = None
        if OWNER_ID_FALLBACK:
            try:
                OWNER_ID = int(OWNER_ID_FALLBACK)
            except ValueError:
                pass
        if OWNER_ID is None:
            print("تنبيه: التطبيق مملوك لفريق (Team) ومافي OWNER_ID_OVERRIDE محدد - أوامر المالك راح تكون معطّلة لحد ما يتحدد معرف موثوق.")
    try:
        await apply_presence()  # يرجّع آخر حالة اخترتيها بعد إعادة التشغيل
    except Exception:
        traceback.print_exc()
    print(f"ريان شغال: {bot.user}")


@bot.event
async def on_message(msg):
    if msg.author.bot:
        return
    text = msg.content.strip()
    is_owner = msg.author.id == OWNER_ID

    if text in ("!اوامر", "!help"):
        await msg.reply(
            "اكتب ريان وبعدها كلامك، أو منشن @ريان، أو رد على إحدى رسائلي\n"
            "!ping يتأكد إني شغال\n"
            "!انا علاقتي فيك\n"
            "!اقرب أقرب ربعي بهالسيرفر\n"
            "للمالك: !علاقة @شخص رقم ، !انسى @شخص\n"
            "اللهجة: !ريان سعودي ، !ريان إماراتي ، !ريان فصحى ، !ريان جاهلي\n"
            "الشعر: !ريان شعر <موضوع> ، !ريان شعر فصيح <موضوع>\n"
            "الشخصية (للمالك): !ريان شخصية جديدة ، !ريان شخصية قديمة\n"
            "أوضاع التفاعل (للمالك): !ريان حر ، !ريان حر شوي ، !ريان قيد\n"
            "إدارة السيرفرات: !ريان السيرفرات ، !ريان اخرج <رقم>\n"
            "الحالة (للمالك): !ريان متصل ، !ريان غير متصل\n"
            "!ريان معلومات لعرض حالتي الحالية"
        )
        return
    if text == "!ping":
        await msg.reply("شغال 🫡")
        return
    if text == "!انا":
        score, msgs, notes, first_seen, last_seen = get_user(msg.author)
        await msg.reply(f"علاقتنا: {level(score)} ({score} نقطة) | رسايلك لي: {msgs}")
        return
    if text == "!اقرب":
        rows = top_friends(guild=msg.guild)
        if not rows:
            await msg.reply("للحين ما عرفت أحد في هالسيرفر")
        else:
            await msg.reply("\n".join(f"{i}. {n} - {level(s)}" for i, (n, s) in enumerate(rows, 1)))
        return
    if text.startswith(("!علاقة", "!انسى")):
        if not is_owner:
            await msg.reply("هذا للمالك بس")
            return
        if not msg.mentions:
            await msg.reply("منشن الشخص: !علاقة @شخص 10")
            return
        target = msg.mentions[0]
        if text.startswith("!انسى"):
            db.execute("DELETE FROM users WHERE id=?", (target.id,))
            db.commit()
            await msg.reply(f"نسيت {target.display_name}")
            return
        try:
            n = int(text.split()[-1])
        except ValueError:
            await msg.reply("الصيغة: !علاقة @شخص 10 (أو -10)")
            return
        get_user(target)
        db.execute("UPDATE users SET score=score+? WHERE id=?", (n, target.id))
        db.commit()
        score = get_user(target)[0]
        await msg.reply(f"{target.display_name}: {level(score)} ({score})")
        return

    # ── إدارة السيرفرات: محصورة على معرف واحد محدد ──
    if text == "!ريان السيرفرات":
        if msg.author.id != SERVER_MGMT_USER_ID:
            await msg.reply("هذا الأمر غير مسموح لك.")
            return
        guilds = list(bot.guilds)
        if not guilds:
            await msg.reply("ريان مو عضو في أي سيرفر حاليًا.")
            return
        await send_numbered_list(msg.channel, build_guild_lines(guilds), header="سيرفرات ريان:")
        return

    if text.startswith("!ريان اخرج"):
        if msg.author.id != SERVER_MGMT_USER_ID:
            await msg.reply("هذا الأمر غير مسموح لك.")
            return
        parts = text.split()
        if len(parts) < 3 or not parts[2].isdigit():
            await msg.reply("الصيغة: !ريان اخرج <رقم>  مثال: !ريان اخرج 7")
            return
        idx = int(parts[2])
        guilds = list(bot.guilds)
        if idx < 1 or idx > len(guilds):
            await msg.reply(f"رقم غير موجود. عدد السيرفرات حاليًا: {len(guilds)}")
            return
        target_guild = guilds[idx - 1]
        guild_name = target_guild.name
        try:
            await target_guild.leave()
            await msg.reply(f"خرجت من السيرفر رقم {idx}: {guild_name}")
        except Exception:
            traceback.print_exc()
            await msg.reply(f"حصل خطأ وأنا أحاول أخرج من {guild_name}")
        return

    # ── أوضاع التفاعل: محصورة على المالك، تطبق على الروم الحالي فقط ──
    if text == "!ريان حر":
        if not is_owner:
            await msg.reply("هذا الأمر غير مسموح لك.")
            return
        set_mode(msg.channel.id, FREE_MODE)
        await msg.reply("تم، صرت بوضع حر في هالروم 🔓")
        return
    if text == "!ريان حر شوي":
        if not is_owner:
            await msg.reply("هذا الأمر غير مسموح لك.")
            return
        set_mode(msg.channel.id, FREE_LIGHT_MODE)
        await msg.reply("تم، وضع حر شوي في هالروم")
        return
    if text == "!ريان قيد":
        if not is_owner:
            await msg.reply("هذا الأمر غير مسموح لك.")
            return
        set_mode(msg.channel.id, RESTRICTED_MODE)
        await msg.reply("تم، رجعت للوضع المقيد في هالروم 🔒")
        return

    # ── اللهجة: تغيير أسلوب اللغة فقط، الشخصية والذاكرة والعلاقات ما تتغير ──
    if text == "!ريان سعودي":
        if not is_owner:
            await msg.reply("هذا الأمر غير مسموح لك.")
            return
        set_dialect(msg.channel.id, "سعودي")
        await msg.reply("رجعت للهجتي الطبيعية، سعودي 🫡")
        return
    if text == "!ريان إماراتي":
        if not is_owner:
            await msg.reply("هذا الأمر غير مسموح لك.")
            return
        set_dialect(msg.channel.id, "إماراتي")
        await msg.reply("تمام، بكلم بأسلوب إماراتي بس شخصيتي ما تتغير")
        return
    if text == "!ريان فصحى":
        if not is_owner:
            await msg.reply("هذا الأمر غير مسموح لك.")
            return
        set_dialect(msg.channel.id, "فصحى")
        await msg.reply("حسنًا، سأتحدث بالفصحى من الآن في هذه الغرفة.")
        return
    if text == "!ريان جاهلي":
        if not is_owner:
            await msg.reply("هذا الأمر غير مسموح لك.")
            return
        set_dialect(msg.channel.id, "جاهلي")
        await msg.reply("حيّاكم الله، سأخاطبكم بلسان العرب الأوائل من الآن في هذه الغرفة.")
        return

    # ── تبديل الشخصية: للمالك فقط، لكل روم. الذاكرة والعلاقات ما تتأثر ──
    if text in ("!ريان شخصية جديدة", "!ريان شخصية قديمة"):
        if not is_owner:
            await msg.reply("هذا الأمر غير مسموح لك.")
            return
        new_persona = "جديدة" if text.endswith("جديدة") else "قديمة"
        set_persona(msg.channel.id, new_persona)
        await msg.reply("تم، غيّرت شخصيتي بهالروم للجديدة" if new_persona == "جديدة" else "تم، رجعت لشخصيتي القديمة بهالروم")
        return

    # ── الشعر: متاح للجميع، مع مهلة 30 ثانية لكل شخص ──
    poem_cmd = re.match(r"^!ريان\s+(?:شعر|قصيدة)(?:\s+(.*))?$", text, re.S)
    if poem_cmd:
        topic = (poem_cmd.group(1) or "").strip()
        style = "نبطي"
        for key in POETRY_STYLES:
            if topic.startswith(key):
                style, topic = key, topic[len(key):].strip()
                break
        if not topic:
            await msg.reply("عطني موضوع للقصيدة. مثال: !ريان شعر عن الغربة ، أو: !ريان شعر فصيح عن الليل")
            return
        wait = 30 - (time.monotonic() - poetry_cooldown.get(msg.author.id, -1000))
        if wait > 0:
            await msg.reply(f"خلني أرتاح شوي، جرّب بعد {int(wait) + 1} ثانية")
            return
        poetry_cooldown[msg.author.id] = time.monotonic()
        try:
            async with msg.channel.typing():
                poem = await make_poem(topic[:200], style)
            await msg.reply(poem[:2000] if poem else "ما طلعت لي قصيدة هالمرة، جرّب مرة ثانية")
        except Exception:
            traceback.print_exc()
            await msg.reply("ما قدرت أكتب الحين، جرّب بعد شوي")
        return

    # ── ظهور الحالة: للمالك فقط، وما يفصل البوت فعليًا ──
    if text in ("!ريان متصل", "!ريان غير متصل"):
        if not is_owner:
            await msg.reply("هذا الأمر غير مسموح لك.")
            return
        online = text == "!ريان متصل"
        set_setting("presence", "online" if online else "offline")
        try:
            await apply_presence()
            await msg.reply("تمام، حالتي متصل 🟢" if online else "تمام، بظهر أوفلاين، بس أنا شغال وأرد عادي")
        except Exception:
            traceback.print_exc()
            await msg.reply("ما قدرت أغيّر الحالة الحين، جرّب بعد شوي")
        return

    if text in ("!ريان أوامر",):
        await msg.reply(
            "اكتب ريان وبعدها كلامك، أو منشن @ريان، أو رد على رسالة له\n"
            "!ping ، !انا ، !اقرب\n"
            "للمالك: !علاقة @شخص رقم ، !انسى @شخص\n"
            "اللهجة: !ريان سعودي ، !ريان إماراتي ، !ريان فصحى ، !ريان جاهلي\n"
            "الشعر: !ريان شعر <موضوع> ، !ريان شعر فصيح <موضوع>\n"
            "الشخصية (للمالك): !ريان شخصية جديدة ، !ريان شخصية قديمة\n"
            "الأوضاع: !ريان حر ، !ريان حر شوي ، !ريان قيد\n"
            "إدارة السيرفرات: !ريان السيرفرات ، !ريان اخرج <رقم>\n"
            "الحالة (للمالك): !ريان متصل ، !ريان غير متصل\n"
            "!ريان معلومات لعرض حالته الحالية"
        )
        return

    if text == "!ريان معلومات":
        mode = get_mode(msg.channel.id)
        dialect = get_dialect(msg.channel.id)
        await msg.reply(
            f"الوضع في هالروم: {mode}\n"
            f"اللهجة: {dialect}\n"
            f"الشخصية: {get_persona(msg.channel.id)}\n"
            f"الحالة الظاهرة: {'أوفلاين (بس شغال)' if get_setting('presence', 'online') == 'offline' else 'متصل'}\n"
            f"شغال ✅"
        )
        return

    # ── تحديد هل يرد ريان على هالرسالة ولا لأ ──
    direct_hit = triggered(msg)
    reply_hit = await is_reply_to_bot(msg)
    mode = get_mode(msg.channel.id)

    should_respond = direct_hit or reply_hit
    if not should_respond and text:
        if mode == FREE_MODE:
            should_respond = should_reply_free(msg.channel.id, text, light=False)
        elif mode == FREE_LIGHT_MODE:
            should_respond = should_reply_free(msg.channel.id, text, light=True)

    if not should_respond:
        if text:
            channel_silence[msg.channel.id] = channel_silence.get(msg.channel.id, 0) + 1
        return

    channel_silence[msg.channel.id] = 0
    try:
        score, msgs, notes, first_seen, last_seen = get_user(msg.author)
        absence_note = describe_absence(last_seen)
        now_iso = datetime.now(timezone.utc).isoformat()
        score += 1
        msgs += 1
        db.execute(
            "UPDATE users SET score=?, msgs=?, last_seen=? WHERE id=?",
            (score, msgs, now_iso, msg.author.id),
        )
        db.commit()

        lines = []
        async for m in msg.channel.history(limit=10):
            who = "ريان (أنت)" if m.author == bot.user else m.author.display_name
            lines.append(f"{who}: {m.clean_content}")
        lines.reverse()

        extra = ""
        if "أقرب" in text or "اقرب" in text:
            rows = top_friends(guild=msg.guild)
            if rows:
                extra = "\nأقرب ناس لك حسب ذاكرتك (في هالسيرفر): " + "، ".join(f"{n} ({level(s)})" for n, s in rows)

        # معلومات مؤكدة من الكود (مو من النموذج): الوقت بتوقيت السعودية + بيانات فعلية
        now_local = datetime.now(RIYADH_TZ)
        facts = [
            f"الوقت الآن بتوقيت السعودية: {WEEKDAYS_AR[now_local.weekday()]} {now_local.strftime('%Y-%m-%d %H:%M')}",
            f"نقاط علاقتك بهذا الشخص: {score}، وعدد رسائله لك: {msgs}",
        ]
        try:
            facts.append("أول مرة شفته: " + datetime.fromisoformat(first_seen).astimezone(RIYADH_TZ).strftime("%Y-%m-%d"))
        except Exception:
            pass
        if msg.guild is not None and msg.guild.member_count:
            facts.append(f"اسم السيرفر: {msg.guild.name}، وعدد أعضائه: {msg.guild.member_count}")
        time_note = "معلومات مؤكدة (الأرقام الوحيدة المسموح تذكرها):\n- " + "\n- ".join(facts) + "\n"
        if absence_note:
            time_note += (
                f"آخر تفاعل لهذا الشخص كان {absence_note}. "
                "لو مناسب للسياق اذكر الغياب بشكل طبيعي وخفيف، بس لا تعلّق عليه كل مرة، "
                "ولا تخترع سبب الغياب أو تفترض وين كان - لو ما تعرف السبب، لا تقول شي عنه.\n"
            )

        dialect = get_dialect(msg.channel.id)
        dialect_note = DIALECTS[dialect] if dialect != "سعودي" else ""

        # الرسالة التي يرد عليها المستخدم (إن وجدت) عشان ريان ما يخلط بين المخاطَب وغيره
        reply_context = ""
        if msg.reference:
            ref = msg.reference.resolved
            if ref is None:
                try:
                    ref = await msg.channel.fetch_message(msg.reference.message_id)
                except Exception:
                    ref = None
            if ref is not None and getattr(ref, "author", None):
                reply_context = f"هذه الرسالة رد على رسالة من {ref.author.display_name}: \"{ref.clean_content[:200]}\"\n"

        prompt = (
            f"الشخص اللي يكلمك الآن: {msg.author.display_name} (معرّفه الداخلي: {msg.author.id}) | علاقتك فيه: {level(score)}\n"
            f"اللي تعرفه عنه: {notes or 'لا يوجد'}{extra}\n"
            f"{reply_context}"
            f"{time_note}"
            + (f"\n{dialect_note}\n" if dialect_note else "\n")
            + "آخر الرسائل في الروم (كل سطر فيه اسم صاحبه، لا تخلط بين المتحدثين):\n"
            + "\n".join(lines) + f"\n\nرد على رسالة {msg.author.display_name} الأخيرة فقط، ولا تنسب كلامه لغيره."
        )

        # الصور: نقرأ بايتات الصورة فعليًا ونمررها لـ Gemini (بحد للعدد والحجم)
        image_parts = []
        for a in msg.attachments:
            if len(image_parts) >= MAX_IMAGES:
                break
            if (a.content_type or "").startswith("image/") and a.size <= MAX_IMAGE_BYTES:
                try:
                    data = await a.read()
                    image_parts.append(
                        types.Part.from_bytes(data=data, mime_type=a.content_type.split(";")[0])
                    )
                except Exception:
                    traceback.print_exc()
        had_images = any((a.content_type or "").startswith("image/") for a in msg.attachments)

        gen_config = types.GenerateContentConfig(
            system_instruction=PERSONAS[get_persona(msg.channel.id)],
            max_output_tokens=1024,  # سقف أمان (Gemini قد يستهلك جزء منه بالتفكير الداخلي)
            temperature=1.0,
        )

        async def generate(contents):
            r = await client.aio.models.generate_content(
                model=MODEL, contents=contents, config=gen_config
            )
            return (r.text or "").strip()

        reply_text = ""
        async with msg.channel.typing():
            try:
                reply_text = await generate([prompt, *image_parts] if image_parts else prompt)
            except Exception:
                traceback.print_exc()
                if image_parts:
                    # محاولة احتياطية واحدة بدون الصور، ومعها تنبيه إنه ما شافها
                    reply_text = await generate(
                        prompt + "\n(ملاحظة: وصلتك صورة بس ما قدرت تشوفها هالمرة، لا تدعي إنك شفتها ولا تخمّن محتواها)"
                    )
                else:
                    raise
        if had_images and not image_parts:
            reply_text = reply_text or "وصلتني صورة بس ما قدرت أشوفها، جرّب ترسلها مرة ثانية"
        if not reply_text:
            reply_text = "هم؟ ما وضح لي كلامك 😅"
        await msg.reply(reply_text[:2000])

        if msgs % 10 == 0:
            try:
                await update_notes(msg.author, notes, lines)
            except Exception:
                traceback.print_exc()
    except Exception:
        traceback.print_exc()
        await msg.reply("صار عندي خلل، جرّب بعد شوي")


bot.run(os.environ["DISCORD_TOKEN"])
