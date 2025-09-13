# bot.py  - Reemplaza tu archivo actual por este
import os
import logging
from dotenv import load_dotenv
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes

import db
import roulette

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
ROUND_INTERVAL_SECONDS = int(os.getenv("ROUND_INTERVAL_SECONDS", "120"))

# Logging básico (útil para depurar)
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


# -------------------------
# Helpers
# -------------------------
def get_color_and_symbol(number: int):
    """Devuelve (símbolo, nombre) para el color del número."""
    if number == 0:
        return "🟢", "Verde"
    if roulette.is_red(number):
        return "♦️", "Rojo"
    return "♠️", "Negro"


async def es_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """True si el usuario que llamó el comando es admin/creator en el grupo."""
    try:
        chat = update.effective_chat
        user = update.effective_user
        if chat is None or user is None:
            return False
        if chat.type not in ("group", "supergroup"):
            return False
        try:
            admins = await context.bot.get_chat_administrators(chat.id)
            admin_ids = {a.user.id for a in admins}
            return user.id in admin_ids
        except Exception:
            # fallback
            try:
                member = await context.bot.get_chat_member(chat.id, user.id)
                return getattr(member, "status", None) in ("administrator", "creator")
            except Exception:
                return False
    except Exception:
        return False


# -------------------------
# Comandos básicos
# -------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db.init_db()
    user = update.effective_user
    db.ensure_user(user.id, user.first_name or "")
    await update.message.reply_text(f"🎰 Bienvenido {user.first_name}! Usa /saldo para ver tus fichas.")


async def saldo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db.init_db()
    user = update.effective_user
    db.ensure_user(user.id, user.first_name or "")
    bal = db.get_balance(user.id)
    await update.message.reply_text(f"💰 {user.first_name}, tu saldo es {bal} fichas.")


async def listar_admins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        chat = update.effective_chat
        if chat.type not in ("group", "supergroup"):
            await update.message.reply_text("Este comando sólo funciona en grupos.")
            return
        admins = await context.bot.get_chat_administrators(chat.id)
        lines = []
        for a in admins:
            uname = f" (@{a.user.username})" if getattr(a.user, "username", None) else ""
            lines.append(f"{a.user.id} — {a.user.first_name}{uname} — {a.status}")
        await update.message.reply_text("Admins:\n" + "\n".join(lines))
    except Exception as e:
        logger.exception("listar_admins error")
        await update.message.reply_text(f"Error al listar admins: {e}")


# -------------------------
# Reglas (sin etiquetas problemáticas)
# -------------------------
async def reglas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Mensaje de reglas. Evitamos usar caracteres '<' '>' sin escapar para que
    Telegram no intente parsear etiquetas HTML inválidas.
    """
    msg = (
        "📜 <b>Reglas de la Ruleta</b>\n\n"
        "🎰 <b>Cómo apostar</b>:\n"
        "Usa: /apostar &lt;cantidad&gt; &lt;tipo&gt;\n\n"
        "✅ <b>Ejemplos</b>:\n"
        "• /apostar 100 rojo\n"
        "• /apostar 50 par\n"
        "• /apostar 20 17\n"
        "• /apostar 10 1-2   (split de 2 números)\n"
        "• /apostar 15 docena2\n\n"
        "🎲 <b>Apuestas válidas (resumen)</b>:\n"
        "- Número único (straight) — paga 35:1\n"
        "- Split (2 números con '-') — paga 17:1\n"
        "- Street (3 números) — paga 11:1\n"
        "- Corner (4 números) — paga 8:1\n"
        "- Línea (6 números) — paga 5:1\n"
        "- Docenas: docena1 (1-12), docena2 (13-24), docena3 (25-36) — paga 2:1\n"
        "- Columnas: columna1/2/3 — paga 2:1\n"
        "- Bajo (1-18) / Alto (19-36) — paga 1:1\n"
        "- Rojo / Negro, Par / Impar — paga 1:1\n\n"
        "📝 Usa /saldo para ver tu saldo, /ranking para ver el top y /regalar para transferir fichas a otro jugador.\n"
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)


# -------------------------
# Apostar (soporta muchos tipos)
# -------------------------
async def apostar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db.init_db()
    chat = update.effective_chat
    user = update.effective_user
    db.ensure_user(user.id, user.first_name or "")

    # Comprobar ruleta activa
    try:
        jobs = context.job_queue.get_jobs_by_name(f'ruleta:{chat.id}')
    except Exception:
        jobs = []
    if not jobs:
        await update.message.reply_text("⛔ La ruleta está apagada. No se aceptan apuestas ahora.")
        return

    if len(context.args) < 2:
        await update.message.reply_text("Uso: /apostar <cantidad> <tipo>  — usa /reglas para ejemplos.")
        return

    # parse amount
    try:
        amount = int(context.args[0])
        if amount <= 0:
            raise ValueError()
    except Exception:
        await update.message.reply_text("❌ La cantidad debe ser un número entero mayor a 0.")
        return

    bet_token = context.args[1].lower().strip()

    # Validación de token
    valid = False
    if bet_token in ("rojo", "negro", "par", "impar", "bajo", "alto",
                     "docena1", "docena2", "docena3",
                     "columna1", "columna2", "columna3"):
        valid = True
    elif "-" in bet_token:
        parts = bet_token.split("-")
        if 2 <= len(parts) <= 6 and all(p.isdigit() and 0 <= int(p) <= 36 for p in parts):
            valid = True
    else:
        if bet_token.isdigit():
            n = int(bet_token)
            if 0 <= n <= 36:
                valid = True

    if not valid:
        await update.message.reply_text("❌ Apuesta no válida. Revisa /reglas para los tipos permitidos.")
        return

    balance = db.get_balance(user.id)
    if amount > balance:
        await update.message.reply_text("❌ Saldo insuficiente.")
        return

    # Registrar apuesta
    chat_id = chat.id
    round_id = db.get_or_open_round(chat_id)
    db.add_balance(user.id, -amount)
    db.place_bet(chat_id, round_id, user.id, bet_token, amount)

    display_name = user.first_name or f"Jugador-{user.id}"
    await update.message.reply_text(f'✅ {display_name} apostó {amount} a {bet_token}. (Ronda #{round_id})')


# -------------------------
# Dar fichas (admins)
# -------------------------
async def dar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db.init_db()
    if not await es_admin(update, context):
        await update.message.reply_text("⛔ Solo los administradores pueden usar este comando.")
        return

    # Responder al mensaje -> /dar 500
    if update.message.reply_to_message and len(context.args) == 1:
        target_user = update.message.reply_to_message.from_user

        # 🔒 Bloquear si es un bot
        if getattr(target_user, "is_bot", False):
            await update.message.reply_text("❌ No puedes dar fichas a bots.")
            return

        try:
            amount = int(context.args[0])
            if amount <= 0:
                raise ValueError()
        except Exception:
            await update.message.reply_text("Uso: responde con /dar <cantidad> (cantidad válida).")
            return
        db.ensure_user(target_user.id, target_user.first_name or "")
        db.add_balance(target_user.id, amount)
        await update.message.reply_text(f"✅ {target_user.first_name} recibió {amount} fichas.")
        return

    # /dar <user_id> <cantidad>
    if len(context.args) >= 2:
        try:
            target_id = int(context.args[0])
            amount = int(context.args[1])
            if amount <= 0:
                raise ValueError()
        except Exception:
            await update.message.reply_text("Uso: /dar <user_id> <cantidad> (valores válidos).")
            return

        # 🔒 Bloquear si es el bot
        me = await context.bot.get_me()
        if target_id == me.id:
            await update.message.reply_text("❌ No puedes dar fichas al bot.")
            return

        db.ensure_user(target_id, "")
        db.add_balance(target_id, amount)
        await update.message.reply_text(f"✅ Usuario {target_id} recibió {amount} fichas.")
        return

    await update.message.reply_text("Uso: responde con /dar <cantidad> o /dar <user_id> <cantidad>")



# -------------------------
# Regalar fichas (usuarios)
# -------------------------
async def regalar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db.init_db()
    giver = update.effective_user
    db.ensure_user(giver.id, giver.first_name or "")
    balance = db.get_balance(giver.id)

    # Responder a mensaje: /regalar 50
    if update.message.reply_to_message and len(context.args) == 1:
        target_user = update.message.reply_to_message.from_user

        # 🔒 Bloquear si el destinatario es un bot
        if getattr(target_user, "is_bot", False):
            await update.message.reply_text("❌ No puedes regalar fichas a bots.")
            return

        try:
            amount = int(context.args[0])
            if amount <= 0:
                raise ValueError()
        except Exception:
            await update.message.reply_text("Uso: responde al mensaje con /regalar <cantidad> (entero positivo).")
            return

        if amount > balance:
            await update.message.reply_text("❌ No tienes saldo suficiente para regalar esa cantidad.")
            return

        db.ensure_user(target_user.id, target_user.first_name or "")
        db.add_balance(giver.id, -amount)
        db.add_balance(target_user.id, amount)
        await update.message.reply_text(f"🎁 {giver.first_name} regaló {amount} fichas a {target_user.first_name}.")
        return

    # Forma alternativa no implementada: por user_id (podría añadirse)
    await update.message.reply_text("Uso: responde al mensaje del usuario con /regalar <cantidad>")



# -------------------------
# Ejecutar ruleta y liquidar
# -------------------------
async def spin_and_settle(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    chat_id = job.chat_id
    db.init_db()
    result = roulette.spin()
    round_id = db.close_round(chat_id, str(result))
    if not round_id:
        db.get_or_open_round(chat_id)
        return

    bets = db.get_bets(round_id)
    winners = []  # (user_id, premio)

    for user_id, bet_type, amount in bets:
        win = 0
        # Even-money bets (1:1 -> multiplier 2)
        if bet_type == "rojo" and roulette.is_red(result):
            win = amount * 2
        elif bet_type == "negro" and (not roulette.is_red(result)) and result != 0:
            win = amount * 2
        elif bet_type == "par" and result != 0 and result % 2 == 0:
            win = amount * 2
        elif bet_type == "impar" and result % 2 == 1:
            win = amount * 2
        elif bet_type == "bajo" and 1 <= result <= 18:
            win = amount * 2
        elif bet_type == "alto" and 19 <= result <= 36:
            win = amount * 2

        # Docenas (paga 2:1 -> multiplier 3)
        elif bet_type.startswith("docena"):
            if bet_type == "docena1" and 1 <= result <= 12:
                win = amount * 3
            if bet_type == "docena2" and 13 <= result <= 24:
                win = amount * 3
            if bet_type == "docena3" and 25 <= result <= 36:
                win = amount * 3

        # Columnas (paga 2:1 -> multiplier 3)
        elif bet_type.startswith("columna"):
            if result != 0:
                col = ((result - 1) % 3) + 1
                if bet_type == f"columna{col}":
                    win = amount * 3

        # Split/Street/Corner/Line (usando '-' y tamaño de lista)
        elif "-" in bet_type:
            try:
                nums = [int(n) for n in bet_type.split("-") if n.isdigit()]
                if result in nums:
                    if len(nums) == 2:
                        win = amount * 18   # split -> 17:1 => 18x
                    elif len(nums) == 3:
                        win = amount * 12   # street -> 11:1 => 12x
                    elif len(nums) == 4:
                        win = amount * 9    # corner -> 8:1 => 9x
                    elif len(nums) == 6:
                        win = amount * 6    # line -> 5:1 => 6x
            except Exception:
                pass

        # Número straight (single) -> 35:1 => 36x
        else:
            try:
                if bet_type.isdigit() and int(bet_type) == result:
                    win = amount * 36
            except Exception:
                pass

        if win > 0:
            db.add_balance(user_id, win)
            winners.append((user_id, win))

    sym, color_name = get_color_and_symbol(result)

    # Construir mensaje de resultado y destacado del mayor ganador
    if winners:
        total_paid = sum(p for _, p in winners)
        top_uid, top_prize = max(winners, key=lambda x: x[1])
        # Obtener nombre legible
        try:
            member = await context.bot.get_chat_member(chat_id, top_uid)
            winner_name = member.user.first_name or getattr(member.user, "username", None) or f"Jugador-{top_uid}"
        except Exception:
            winner_name = db.get_username(top_uid) or f"Jugador-{top_uid}"

        banner = (
            "🎉🎊 <b>¡GANADOR!</b> 🎊🎉\n"
            f"🏆 <a href='tg://user?id={top_uid}'>{winner_name}</a>\n"
            f"👉 <b>{top_prize} fichas</b>\n\n"
            f"🎡 Resultado: <u>{result} {sym} {color_name}</u>\n"
        )

        # Si hay otros ganadores, mostramos un resumen
        others_count = len(winners) - 1
        if others_count > 0:
            banner += f"\n📢 Otros ganadores: {others_count} personas — premios totales: {total_paid - top_prize} fichas\n"

        text = banner
    else:
        text = f"🎡 Resultado: <u>{result} {sym} {color_name}</u>\n\n😢 No hubo ganadores."

    # Abrimos nueva ronda para que la gente apueste mientras corre el job
    db.get_or_open_round(chat_id)

    # Enviar (HTML safe)
    try:
        await context.bot.send_message(chat_id, text, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.exception("Error enviando resultado")


# -------------------------
# Control ruleta (admins)
# -------------------------
async def ruleta_on(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db.init_db()
    if not await es_admin(update, context):
        await update.message.reply_text("⛔ Solo admins pueden activar la ruleta.")
        return

    chat = update.effective_chat
    try:
        existing = context.job_queue.get_jobs_by_name(f'ruleta:{chat.id}')
    except Exception:
        existing = []
    if existing:
        await update.message.reply_text("⚠️ La ruleta ya está activa en este grupo.")
        return

    db.get_or_open_round(chat.id)
    context.job_queue.run_repeating(
        spin_and_settle,
        interval=ROUND_INTERVAL_SECONDS,
        first=ROUND_INTERVAL_SECONDS,
        chat_id=chat.id,
        name=f'ruleta:{chat.id}',
    )
    await update.message.reply_text(f"✅ Ruleta activada. Gira cada {ROUND_INTERVAL_SECONDS} segundos.")


async def ruleta_off(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await es_admin(update, context):
        await update.message.reply_text("⛔ Solo admins pueden desactivar la ruleta.")
        return
    chat = update.effective_chat
    jobs = context.job_queue.get_jobs_by_name(f'ruleta:{chat.id}')
    if not jobs:
        await update.message.reply_text("ℹ️ No hay ruleta activa.")
        return
    for job in jobs:
        job.schedule_removal()
    await update.message.reply_text("⏹️ Ruleta desactivada.")


# -------------------------
# Ranking
# -------------------------
async def ranking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db.init_db()
    rows = db.top_users(10)
    if not rows:
        await update.message.reply_text("Aún no hay usuarios en el ranking.")
        return
    text = ["🏆 <b>Top jugadores</b>:"]
    medals = ["🥇", "🥈", "🥉"] + ["🎖️"] * 7
    for i, r in enumerate(rows, start=1):
        name = r["username"] or f"Jugador-{r['user_id']}"
        text.append(f"{medals[i-1]} {i}. {name} — {r['balance']} fichas")
    await update.message.reply_text("\n".join(text), parse_mode=ParseMode.HTML)


# -------------------------
# Main
# -------------------------
def main():
    db.init_db()
    if not TOKEN:
        raise SystemExit("Falta BOT_TOKEN en .env")
    app = Application.builder().token(TOKEN).build()
    # Asegurar JobQueue inicializado
    _ = app.job_queue

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("saldo", saldo))
    app.add_handler(CommandHandler("reglas", reglas))
    app.add_handler(CommandHandler("apostar", apostar))
    app.add_handler(CommandHandler("ruleta_on", ruleta_on))
    app.add_handler(CommandHandler("ruleta_off", ruleta_off))
    app.add_handler(CommandHandler("dar", dar))
    app.add_handler(CommandHandler("regalar", regalar))
    app.add_handler(CommandHandler("listar_admins", listar_admins))
    app.add_handler(CommandHandler("ranking", ranking))

    app.run_polling()


if __name__ == "__main__":
    main()
