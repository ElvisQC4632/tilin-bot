Telegram Roulette Bot — paquete corregido
----------------------------------------

Archivos incluidos:
  - bot.py        : Bot principal corregido (admin check, job queue, mejoras).
  - db.py         : Base de datos SQLite (asegura saldo inicial 1000).
  - roulette.py   : Lógica de ruleta (0-36, colores).
  - requirements.txt
  - .env.example  : plantilla para tu token.

Instrucciones rápidas (Windows + VSCode):
1) Extrae este ZIP y abre la carpeta en VSCode.
2) Abre la terminal integrada (Terminal -> Nueva terminal).
3) Crea y activa el entorno virtual (desde la carpeta del proyecto):
   python -m venv .venv
   .venv\Scripts\activate.bat   <-- usa cmd (Command Prompt) en VSCode
4) Instala dependencias:
   pip install -r requirements.txt
5) Copia .env.example -> .env y pega tu token de BotFather en BOT_TOKEN=...
6) Ejecuta el bot:
   python bot.py
7) Pruebas básicas:
   - En privado con el bot: /start  -> /saldo
   - En el grupo (agrega el bot y hazte admin): /listar_admins, /ruleta_on, /apostar 10 rojo, etc.

Notas:
  - Si PowerShell bloquea activar el venv, usa Command Prompt (cmd) o cambia la policy:
    Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned  (run as admin)
  - El JobQueue requiere el extra [job-queue] en python-telegram-bot (ya está en requirements.txt).