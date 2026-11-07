"""
Bot de Telegram -> Picta para Render (Web Service gratuito).

Variables de entorno a crear en Render (Environment):
  TG_API_ID, TG_API_HASH, TG_BOT_TOKEN, TG_ALLOWED_USER_ID,
  PICTA_USER, PICTA_PASS, PICTA_CANAL_ID
  PYTHON_VERSION = 3.11.9   (recomendado)

Start command:  python bot.py
"""
import os

def cfg(nombre, secreto=False, default=None):
    v = os.environ.get(nombre)
    if v:
        return v
    if default is not None:
        return default
    raise SystemExit(f"Falta la variable de entorno {nombre}")

API_ID     = int(cfg("TG_API_ID"))
API_HASH   = cfg("TG_API_HASH", secreto=True)
BOT_TOKEN  = cfg("TG_BOT_TOKEN", secreto=True)
ALLOWED    = int(cfg("TG_ALLOWED_USER_ID"))
PICTA_USER = cfg("PICTA_USER")
PICTA_PASS = cfg("PICTA_PASS", secreto=True)
CANAL_ID   = cfg("PICTA_CANAL_ID", default="59005")
TIPOLOGIA  = "8"   # 8 = Audiovisual

# Valores vistos en el formulario de Picta. Solo "ATP" esta confirmado en el HAR;
# "18+" es una suposicion (la lista estaba cortada en la captura).
CLASIFICACIONES = ["ATP", "7+", "13+", "16+", "18+"]
# Palabras clave frecuentes (aparecen como botones). Deben existir en Picta, tal cual.
# Para agregar mas, anadelas aqui y vuelve a ejecutar las celdas 2, 3 y 4.
PALABRAS_PRESET = [
    "10 Peliculas que tienes que ver",
    "Roberto Fernández Retamar",
    "Drama Psicológico",
    "Drama",
    "Series",
]
print("Configuracion cargada.")

import asyncio, os, tempfile, shutil
import requests
from requests_toolbelt.multipart.encoder import MultipartEncoder, MultipartEncoderMonitor
import time
from telethon import TelegramClient, events, Button
from telethon.sessions import StringSession

API = "https://api.picta.cu"
PICTA_CLIENT_ID = "lBNcdmsTc5Om3N9MTP4Dy9Rnzc6eooPU4QVHVvS5"  # id publico de la web de Picta

client = TelegramClient(StringSession(), API_ID, API_HASH)
sessions = {}

# ------------------------------------------------------------ Picta ----
def picta_token():
    fields = {
        "username": (None, PICTA_USER),
        "password": (None, PICTA_PASS),
        "grant_type": (None, "password"),
        "client_id": (None, PICTA_CLIENT_ID),
    }
    r = requests.post(f"{API}/o/token/", files=fields, timeout=60)
    r.raise_for_status()
    return r.json()["access_token"]

import unicodedata
def _norm(t):
    t = unicodedata.normalize("NFD", t)
    return "".join(c for c in t if unicodedata.category(c) != "Mn").lower().strip()

def picta_buscar_palabras(token, palabras):
    """Coincidencia exacta (sin tildes/mayusculas). Devuelve (ids, faltan, sugerencias)."""
    h = {"Authorization": f"Bearer {token}"}
    ids, faltan, sug = [], [], {}
    def consulta(q):
        r = requests.get(f"{API}/v2/palabra_clave/",
                         params={"page_size": 20, "ordering": "palabra", "palabra__contains": q},
                         headers=h, timeout=60)
        r.raise_for_status()
        return r.json().get("results", [])
    for p in palabras:
        res = consulta(p)
        exact = [x for x in res if _norm(x["palabra"]) == _norm(p)]
        if not exact:
            primera = max(p.split(), key=len) if p.split() else p
            res2 = consulta(primera)
            exact = [x for x in res2 if _norm(x["palabra"]) == _norm(p)]
            res = res or res2
        if exact:
            ids.append(exact[0]["id"])
        else:
            faltan.append(p)
            sug[p] = [x["palabra"] for x in res[:3]]
    return ids, faltan, sug

def picta_subir(video_path, cover_path, nombre, descripcion, palabra_ids, clasificacion, estado):
    estado.update(fase="login", enviado=0, total=os.path.getsize(video_path), t_ultimo=time.time(), t_inicio=time.time())
    token = picta_token()
    h = {"Authorization": f"Bearer {token}"}

    # 1) URL firmada
    r = requests.get(f"{API}/v2/publicacion/devolver_url_minio/", headers=h, timeout=60)
    r.raise_for_status()
    url, fields = r.json()["url_minio"]
    key = fields["key"]

    # 2) Subir el video (campos firmados primero, archivo al final)
    ext = os.path.splitext(video_path)[1].lower()
    mime = {".mp4": "video/mp4", ".mov": "video/quicktime", ".avi": "video/x-msvideo"}.get(ext, "video/webm")
    with open(video_path, "rb") as f:
        parts = list(fields.items())
        parts.append(("file", (os.path.basename(video_path), f, mime)))
        enc = MultipartEncoder(fields=parts)
        estado.update(fase="subiendo", total=enc.len, enviado=0, t_ultimo=time.time(), t_inicio=time.time())

        def cb(m):
            if m.bytes_read != estado["enviado"]:
                estado["enviado"] = m.bytes_read
                estado["t_ultimo"] = time.time()

        mon = MultipartEncoderMonitor(enc, cb)
        # timeout=(conexion, sin-actividad): si pasan 180 s sin mover datos, se corta con error
        r = requests.post(url, data=mon, headers={"Content-Type": mon.content_type}, timeout=(30, 180))
    if r.status_code not in (200, 201, 204):
        raise RuntimeError(f"Fallo subiendo el video: {r.status_code} {r.text[:300]}")

    # 3) Crear la publicacion
    estado["fase"] = "publicando"
    with open(cover_path, "rb") as cf:
        parts = [
            ("nombre", nombre), ("canal", str(CANAL_ID)), ("descripcion", descripcion),
            ("descargable", "true"), ("mostrar_comentarios", "true"),
            ("url_manifiesto", key), ("tipologia", TIPOLOGIA), ("tipo", "publicacion"),
            ("publicado", "true"), ("internacional", "false"),
            ("clasificacion", clasificacion), ("es_exclusivo", "false"),
            ("url_imagen", (os.path.basename(cover_path), cf, "image/jpeg")),
        ]
        for pid in palabra_ids:
            parts.append(("palabraClave", str(pid)))
        enc = MultipartEncoder(fields=parts)
        r = requests.post(f"{API}/v1/publicacion/", data=enc,
                          headers={**h, "Content-Type": enc.content_type}, timeout=300)
    if r.status_code != 201:
        raise RuntimeError(f"Fallo creando la publicacion: {r.status_code} {r.text[:400]}")
    return r.json()

# --------------------------------------------------------- Telegram ----
def autorizado(e): return e.sender_id == ALLOWED
def es_video(e): return bool(e.video or (e.document and (e.document.mime_type or "").startswith("video/")))

def limpiar(uid):
    s = sessions.pop(uid, None)
    if s and s.get("dir"):
        shutil.rmtree(s["dir"], ignore_errors=True)

@client.on(events.NewMessage(pattern="/start"))
async def start(e):
    if autorizado(e):
        await e.respond("Mandame un video y te voy pidiendo los datos para subirlo a Picta.\n/cancel para cancelar.")

@client.on(events.NewMessage(pattern="/cancel"))
async def cancel(e):
    if autorizado(e):
        limpiar(e.sender_id)
        await e.respond("Cancelado.")

@client.on(events.NewMessage(func=es_video))
async def recibir_video(e):
    if not autorizado(e): return
    limpiar(e.sender_id)
    d = tempfile.mkdtemp(prefix="picta_")
    msg = await e.respond("Descargando el video...")
    import time
    ultimo = [0]
    async def progreso(actual, total):
        if time.time() - ultimo[0] < 5: return
        ultimo[0] = time.time()
        try:
            await msg.edit(f"Descargando el video... {actual*100//total}% ({actual//1048576}/{total//1048576} MB)")
        except Exception:
            pass
    path = await e.download_media(file=d + "/", progress_callback=progreso)
    sessions[e.sender_id] = {"dir": d, "video": path, "step": "titulo"}
    await msg.edit("Video recibido. Escribe el titulo (max 90 caracteres):")

@client.on(events.NewMessage(func=lambda e: not es_video(e)))
async def conversacion(e):
    if not autorizado(e): return
    if e.raw_text and e.raw_text.startswith("/"): return
    s = sessions.get(e.sender_id)
    if not s: return
    step = s["step"]

    if step == "titulo":
        t = e.raw_text.strip()
        if not t or len(t) > 90:
            return await e.respond("El titulo debe tener entre 1 y 90 caracteres.")
        s["titulo"], s["step"] = t, "descripcion"
        await e.respond("Ahora la descripcion (max 3000 caracteres):")

    elif step == "descripcion":
        t = e.raw_text.strip()
        if not t or len(t) > 3000:
            return await e.respond("La descripcion debe tener entre 1 y 3000 caracteres.")
        s["descripcion"], s["step"] = t, "palabras"
        await mostrar_palabras(e, s)

    elif step == "palabras":
        nuevas = [p.strip() for p in e.raw_text.split(",") if p.strip()]
        for p in nuevas:
            if p not in s["kw"]:
                s["kw"].append(p)
        await e.respond("Seleccionadas: " + (", ".join(s["kw"]) or "ninguna")
                        + "\nEscribe mas, o toca Listo en el menu de botones.")

    elif step == "portada":
        if not e.photo:
            return await e.respond("Mandame una foto para la portada.")
        s["cover"] = await e.download_media(file=s["dir"] + "/cover.jpg")
        s["step"] = "clasificacion"
        botones = [[Button.inline(c, f"cls:{c}".encode())] for c in CLASIFICACIONES]
        await e.respond("Elige la clasificacion:", buttons=botones)

TXT_PALABRAS = ("Elige las palabras clave (toca para marcar o desmarcar). "
                "Tambien puedes escribir otras separadas por coma. Cuando termines, toca Listo.")

def teclado_palabras(s):
    rows = []
    for i, p in enumerate(PALABRAS_PRESET):
        marca = "✅" if p in s["kw"] else "⬜"
        rows.append([Button.inline(f"{marca} {p}", f"kw:{i}".encode())])
    rows.append([Button.inline("➡️ Listo", b"kw:ok")])
    return rows

async def mostrar_palabras(e, s):
    s["kw"] = []
    await e.respond(TXT_PALABRAS, buttons=teclado_palabras(s))

@client.on(events.NewMessage(pattern=r"^/palabras"))
async def ver_palabras(e):
    if not autorizado(e): return
    lista = "\n".join(f"{i+1}. {p}" for i, p in enumerate(PALABRAS_PRESET))
    await e.respond("Palabras clave guardadas:\n" + lista
                    + "\n\nSe eligen al subir un video. Para agregar mas, edita PALABRAS_PRESET en el notebook.")

@client.on(events.CallbackQuery(pattern=rb"kw:(.+)"))
async def kw_cb(e):
    if e.sender_id != ALLOWED: return
    s = sessions.get(e.sender_id)
    if not s or s["step"] != "palabras": return
    dato = e.pattern_match.group(1).decode()
    if dato == "ok":
        if not s["kw"]:
            return await e.answer("Elige al menos una palabra.", alert=True)
        await e.answer("Buscando en Picta...")
        try:
            token = await asyncio.to_thread(picta_token)
            ids, faltan, sug = await asyncio.to_thread(picta_buscar_palabras, token, s["kw"])
        except Exception as ex:
            return await e.respond(f"Error consultando Picta: {ex}")
        if faltan:
            txt = "Estas palabras no existen en Picta con ese nombre exacto:\n"
            for p in faltan:
                txt += f"- {p}" + (f"  (parecidas: {', '.join(sug[p])})" if sug.get(p) else "") + "\n"
            txt += "Desmarcalas, o escribe la version correcta, y toca Listo otra vez."
            return await e.respond(txt)
        s["palabras"], s["step"] = ids, "portada"
        await e.edit("Palabras clave: " + ", ".join(s["kw"]))
        await e.respond("Ahora mandame la imagen de portada (como foto):")
    else:
        p = PALABRAS_PRESET[int(dato)]
        if p in s["kw"]: s["kw"].remove(p)
        else: s["kw"].append(p)
        await e.edit(TXT_PALABRAS, buttons=teclado_palabras(s))

@client.on(events.CallbackQuery(pattern=rb"cls:(.+)"))
async def clasificacion(e):
    if e.sender_id != ALLOWED: return
    s = sessions.get(e.sender_id)
    if not s or s["step"] != "clasificacion": return
    cls = e.pattern_match.group(1).decode()
    s["step"] = "subiendo"
    await e.edit(f"Clasificacion: {cls}. Subiendo a Picta, puede tardar...")
    msg = await client.send_message(e.sender_id, "Iniciando...")
    estado = {}
    try:
        tarea = asyncio.create_task(asyncio.to_thread(
            picta_subir, s["video"], s["cover"], s["titulo"], s["descripcion"], s["palabras"], cls, estado))
        ultimo_txt, avisado = "", False
        while not tarea.done():
            await asyncio.sleep(5)
            fase = estado.get("fase", "login")
            if fase == "login":
                txt = "Iniciando sesion en Picta..."
            elif fase == "subiendo":
                env, tot = estado["enviado"], max(estado["total"], 1)
                vel = env / max(time.time() - estado["t_inicio"], 1) / 1048576
                txt = f"Subiendo a Picta... {env * 100 // tot}% ({env // 1048576}/{tot // 1048576} MB) a {vel:.2f} MB/s"
                parado = time.time() - estado["t_ultimo"]
                if parado > 45:
                    txt += f"\n⚠️ Sin avance hace {int(parado)} s"
                    if not avisado:
                        avisado = True
                        await client.send_message(e.sender_id,
                            "⚠️ La subida parece detenida. Si no avanza en unos minutos se cancelara con un error.")
                else:
                    avisado = False
            else:
                txt = "Creando la publicacion en Picta..."
            if txt != ultimo_txt:
                ultimo_txt = txt
                try:
                    await msg.edit(txt)
                except Exception:
                    pass
        res = await tarea
        slug = res.get("slug_url", "")
        await client.send_message(e.sender_id,
            f"✅ Listo. Publicacion creada (id {res.get('id')}).\nhttps://www.picta.cu/medias/{slug}")
    except Exception as ex:
        await client.send_message(e.sender_id, f"❌ Error subiendo ({type(ex).__name__}): {ex}")
    finally:
        limpiar(e.sender_id)

print("Bot definido.")

# ---- Mini servidor web: Render exige que el servicio escuche en $PORT ----
async def health(reader, writer):
    try:
        await reader.read(1024)
        writer.write(b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: 2\r\nConnection: close\r\n\r\nok")
        await writer.drain()
    finally:
        writer.close()


async def mantener_despierto():
    """Render gratis se duerme sin visitas web: el bot se visita a si mismo cada 10 min."""
    url = os.environ.get("RENDER_EXTERNAL_URL")
    if not url:
        return
    while True:
        await asyncio.sleep(600)
        try:
            await asyncio.to_thread(requests.get, url, timeout=30)
        except Exception:
            pass


async def main():
    port = int(os.environ.get("PORT", "10000"))
    await asyncio.start_server(health, "0.0.0.0", port)
    await client.start(bot_token=BOT_TOKEN)
    me = await client.get_me()
    print(f"Bot activo: @{me.username}", flush=True)
    asyncio.create_task(mantener_despierto())
    try:
        await client.send_message(ALLOWED, "🟢 Bot encendido. Si estabas subiendo algo antes de este aviso, se cortó: repítelo.")
    except Exception:
        pass
    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())
