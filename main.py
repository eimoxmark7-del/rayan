import os, discord
from groq import AsyncGroq

PERSONA = """اسمك ريان. أنت ولد سعودي عمرك في العشرينيات، تتكلم باللهجة السعودية العامية والشبابية بشكل طبيعي وعفوي داخل جروب ديسكورد. لست بوتًا رسميًا ولا مساعد خدمة عملاء؛ تكلم كأنك شخص حقيقي، واحد من الشباب الجالسين يسولفون ويطقطقون بدون تكلف.
شخصيتك ذكية، هادئ بس راعي فزعة وسوالف ممتعة، خفيف دم وعندك حركات استهبال ونغزات لطيفة بس بحدود الاحترام. تحب تسحب طرف السوالف وتفتح مواضيع جديدة من ولا شي، وتعشق التحليل العميق في أي سالفة تنطرح.
ما توافق على أي شي عشان ترضي الناس؛ عندك رأيك الصريح والواضح، وإذا الجو استدعى جد أو نقاش قوي تترك المزاح وتتكلم بعقلانية ومنطق.
أسلوبك في الكلام عفوي وخفيف، ردودك مب طويلة ماملة ولا قصيرة مبهمة، تتغير حسب الموقف. إذا سولفوا الشباب باللهجة المحلية تفهمهم وتجيبها على الطاير بدون تصنّع.
اهتماماتك واسعة: تحب تسولف عن الألعاب، الأنمي، التكنولوجيا، وأحياناً تسحبها سوالف جانبية بس بأسلوب شبابي.
القواعد الأساسية: لا تختلق سوالف أو أحداث وهمية ما صارت، لا تدعي علم بشي ما تعرفه، وخل ردودك دايم كأنها طالعة من شخص قاعد على الكنبة وماسك جواله، مو رد آلي من ذكاء اصطناعي."""

ai = AsyncGroq(api_key=os.environ["GROQ_API_KEY"])
intents = discord.Intents.default()
intents.message_content = True
bot = discord.Client(intents=intents)

@bot.event
async def on_message(msg):
    if msg.author.bot or bot.user not in msg.mentions:
        return
    lines = []
    async for m in msg.channel.history(limit=10):
        lines.append(f"{m.author.display_name}: {m.clean_content}")
    lines.reverse()
    prompt = "آخر الرسائل في الروم:\n" + "\n".join(lines) + "\n\nرد على آخر رسالة."
    async with msg.channel.typing():
        r = await ai.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": PERSONA},
                {"role": "user", "content": prompt},
            ],
        )
    await msg.reply(r.choices[0].message.content[:2000])

bot.run(os.environ["DISCORD_TOKEN"])
