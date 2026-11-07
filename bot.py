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
# Tipologias de Picta (id, nombre, modelo), tomadas de /v1/tipologia/.
# Solo se usan de respaldo si el bot no puede consultar la lista a Picta.
TIPOLOGIAS_RESPALDO = [
    {"id": 7,  "nombre": "Audio",              "modelo": "audio"},
    {"id": 12, "nombre": "Audio Sincronizado", "modelo": "audiosincronizado"},
    {"id": 8,  "nombre": "Audiovisual",        "modelo": "categoria"},
    {"id": 10, "nombre": "Canci\u00f3n",        "modelo": "cancion"},
    {"id": 17, "nombre": "Cultural",           "modelo": "categoria"},
    {"id": 6,  "nombre": "Curso",              "modelo": "curso"},
    {"id": 14, "nombre": "Deporte",            "modelo": "video"},
    {"id": 2,  "nombre": "Documental",         "modelo": "documental"},
    {"id": 13, "nombre": "Evento",             "modelo": "eventotipologia"},
    {"id": 19, "nombre": "Humor\u00edstico",    "modelo": "categoria"},
    {"id": 18, "nombre": "Informativo",        "modelo": "categoria"},
    {"id": 9,  "nombre": "Live",               "modelo": "live"},
    {"id": 22, "nombre": "Microdrama",         "modelo": "capitulo"},
    {"id": 21, "nombre": "Orientaci\u00f3n Social", "modelo": "categoria"},
    {"id": 1,  "nombre": "Pel\u00edcula",       "modelo": "pelicula"},
    {"id": 4,  "nombre": "Reportaje",          "modelo": "reportaje"},
    {"id": 20, "nombre": "Revista",            "modelo": "categoria"},
    {"id": 5,  "nombre": "Serie",              "modelo": "capitulo"},
    {"id": 15, "nombre": "Shorts",             "modelo": "categoria"},
    {"id": 11, "nombre": "Videoclip",          "modelo": "videoclip"},
    {"id": 3,  "nombre": "Video Musical",      "modelo": "video"},
]
# Tipologias que se muestran en el menu (en este orden): 8 = Audiovisual, 1 = Pelicula, 5 = Serie, 2 = Documental.
# Para mostrar otra, anade su id aqui (ids en TIPOLOGIAS_RESPALDO).
TIPOLOGIAS_PERMITIDAS = [8, 1, 5, 2]
print("Configuracion cargada.")

import asyncio, os, tempfile, shutil, base64, json
import requests
from requests_toolbelt.multipart.encoder import MultipartEncoder, MultipartEncoderMonitor
import time
from contextlib import ExitStack
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

def picta_tipologias(token):
    """Lista de tipologias desde Picta: [{id, nombre, modelo}, ...]."""
    r = requests.get(f"{API}/v1/tipologia/", headers={"Authorization": f"Bearer {token}"}, timeout=60)
    r.raise_for_status()
    j = r.json()
    res = j.get("results", []) if isinstance(j, dict) else j
    return [{"id": int(x["id"]), "nombre": x["nombre"], "modelo": x.get("modelo", "")} for x in res]

def _pagina(url, params, h, parse, page):
    r = requests.get(url, params=params, headers=h, timeout=60)
    if r.status_code == 404 and page > 1:      # pagina fuera de rango
        return [], False, 0
    r.raise_for_status()
    j = r.json()
    items = [parse(x) for x in j.get("results", [])]
    items = [x for x in items if x["nombre"]]
    return items, bool(j.get("next")), j.get("count", 0)

def _nom(x):
    return {"id": int(x["id"]), "nombre": " ".join((x.get("nombre") or "").split())}

def _extra(tipo, q, page):
    h = {"Authorization": f"Bearer {picta_token()}"}
    params = {"tipo": tipo, "page_size": 8, "page": page}
    if q: params["nombre__contains"] = q
    return _pagina(f"{API}/v2/extra/", params, h, _nom, page)

def pk_productora(q, page): return _extra("productora", q, page)
def pk_premio(q, page): return _extra("premio", q, page)

def pk_persona(q, page):
    h = {"Authorization": f"Bearer {picta_token()}"}
    params = {"page_size": 8, "page": page}
    if q: params["nombre__contains"] = q
    return _pagina(f"{API}/v2/persona/", params, h, _nom, page)

def pk_genero(q, page):
    """Los generos de cine son pocos (54): se piden todos y se pagina aqui."""
    h = {"Authorization": f"Bearer {picta_token()}"}
    r = requests.get(f"{API}/v2/genero/", params={"tipo": "ci", "ordering": "nombre", "page_size": 100},
                     headers=h, timeout=60)
    r.raise_for_status()
    todos = [_nom(x) for x in r.json().get("results", [])]
    todos = [x for x in todos if x["nombre"] and (not q or _norm(q) in _norm(x["nombre"]))]
    ini = (page - 1) * 8
    return todos[ini:ini + 8], len(todos) > ini + 8, len(todos)


def picta_subir(video_path, cover_path, nombre, descripcion, palabra_ids, clasificacion, estado, tipologia=TIPOLOGIA, extra=None, poster_path=None):
    extra = extra or []
    estado.update(fase="login", enviado=0, total=os.path.getsize(video_path), t_ultimo=time.time(), t_inicio=time.time())
    token = picta_token()
    h = {"Authorization": f"Bearer {token}"}

    # 0) Validar los datos ANTES de subir el video (igual que hace la web de Picta)
    estado["fase"] = "validando"
    with ExitStack() as stk:
        cf = stk.enter_context(open(cover_path, "rb"))
        parts = [
            ("tipo", "publicacion"), ("tipologia", str(tipologia)), ("nombre", nombre),
            ("descripcion", descripcion), ("canal", str(CANAL_ID)),
        ]
        for pid in palabra_ids:
            parts.append(("palabraClave", str(pid)))
        parts += [
            ("publicado", "true"), ("descargable", "true"), ("mostrar_comentarios", "true"),
            ("internacional", "false"), ("es_exclusivo", "false"), ("clasificacion", clasificacion),
            ("url_imagen", (os.path.basename(cover_path), cf, "image/jpeg")),
            ("evento", ""),
        ] + list(extra)
        if poster_path:
            pf = stk.enter_context(open(poster_path, "rb"))
            parts.append(("imagen_secundaria", (os.path.basename(poster_path), pf, "image/jpeg")))
        enc = MultipartEncoder(fields=parts)
        r = requests.post(f"{API}/v1/publicacion/validar_campos/", data=enc,
                          headers={**h, "Content-Type": enc.content_type}, timeout=120)
    print("validar_campos:", r.status_code, r.text[:500], flush=True)
    if not r.ok:
        raise RuntimeError(f"Picta rechazo los datos ({r.status_code}): {r.text[:700]}")

    # 1) URL firmada
    r = requests.get(f"{API}/v2/publicacion/devolver_url_minio/", headers=h, timeout=60)
    r.raise_for_status()
    url, fields = r.json()["url_minio"]
    key = fields["key"]

    # Limite de tamano declarado en la politica firmada (si existe)
    limite = None
    try:
        pol = json.loads(base64.b64decode(fields["policy"]))
        for c in pol.get("conditions", []):
            if isinstance(c, list) and len(c) == 3 and c[0] == "content-length-range":
                limite = int(c[2])
    except Exception as ex:
        print("No pude leer la politica:", ex, flush=True)
    print("Campos de la URL firmada:", list(fields.keys()), "| limite:", limite, flush=True)
    tam = os.path.getsize(video_path)
    if limite and tam > limite:
        raise RuntimeError(f"El video pesa {tam // 1048576} MB y Picta solo acepta {limite // 1048576} MB.")

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
        try:
            r = requests.post(url, data=mon, headers={"Content-Type": mon.content_type}, timeout=(30, 180))
        except requests.exceptions.ConnectionError as ex:
            lim_txt = f"{limite // 1048576} MB" if limite else "no declarado en la politica"
            raise RuntimeError(
                f"El servidor corto la conexion tras enviar {estado['enviado'] // 1048576} MB "
                f"de {tam // 1048576} MB. Limite de Picta: {lim_txt}.") from ex
    if r.status_code not in (200, 201, 204):
        raise RuntimeError(f"Fallo subiendo el video: {r.status_code} {r.text[:300]}")

    # 3) Crear la publicacion
    estado["fase"] = "publicando"
    with ExitStack() as stk:
        cf = stk.enter_context(open(cover_path, "rb"))
        parts = [
            ("nombre", nombre), ("canal", str(CANAL_ID)), ("descripcion", descripcion),
            ("descargable", "true"), ("mostrar_comentarios", "true"),
            ("url_manifiesto", key), ("tipologia", str(tipologia)), ("tipo", "publicacion"),
            ("publicado", "true"), ("internacional", "false"),
            ("clasificacion", clasificacion), ("es_exclusivo", "false"),
            ("url_imagen", (os.path.basename(cover_path), cf, "image/jpeg")),
        ]
        # OJO: al crear la publicacion, Picta recibe las palabras clave en UN solo campo separado por comas
        # (en validar_campos, en cambio, van como campos repetidos). Confirmado en el HAR.
        parts.append(("palabraClave", ",".join(str(p) for p in palabra_ids)))
        parts += list(extra)
        if poster_path:
            pf = stk.enter_context(open(poster_path, "rb"))
            parts.append(("imagen_secundaria", (os.path.basename(poster_path), pf, "image/jpeg")))
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

    elif step == "pick":
        q = e.raw_text.strip()
        if not q:
            return await e.respond("Escribe parte del nombre para buscar.")
        await mostrar_picker(e, s, q, 1)

    elif step == "texto":
        campo, v = s["campo"], e.raw_text.strip()
        if campo == "ano":
            if not (v.isdigit() and len(v) == 4 and 1888 <= int(v) <= 2100):
                return await e.respond("Escribe un ano de 4 digitos, por ejemplo 2026.")
        elif not v or len(v) > 60:
            return await e.respond("Escribe el pais (maximo 60 caracteres).")
        s["datos"][campo] = v
        await siguiente_paso(e, s)

    elif step == "portada":
        if not e.photo:
            return await e.respond("Mandame una foto para la portada.")
        s["cover"] = await e.download_media(file=s["dir"] + "/cover.jpg")
        s["step"] = "tipologia"
        try:
            token = await asyncio.to_thread(picta_token)
            tips = await asyncio.to_thread(picta_tipologias, token)
            if not tips:
                raise ValueError("lista vacia")
        except Exception as ex:
            print("No pude leer las tipologias de Picta:", ex, flush=True)
            tips = TIPOLOGIAS_RESPALDO
        tips = ([t for t in tips if t["id"] in TIPOLOGIAS_PERMITIDAS]
                or [t for t in TIPOLOGIAS_RESPALDO if t["id"] in TIPOLOGIAS_PERMITIDAS])
        s["tips"] = {t["id"]: t for t in tips}
        await e.respond(TXT_TIPOLOGIA, buttons=teclado_tipologias(tips))

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

PERSONAS = ("director", "reparto", "fotografia", "musica", "guion")
PREMIO_NINGUNO = 469   # id de "Ninguno" (visto en el HAR)

# campo -> (como se nombra en la pregunta, funcion de busqueda, listar sin que escribas nada)
PICKERS = {
    "productora": ("la productora", pk_productora, True),
    "premio":     ("el premio", pk_premio, True),
    "genero":     ("el genero", pk_genero, True),
    "director":   ("el director", pk_persona, False),
    "reparto":    ("una persona del reparto", pk_persona, False),
    "fotografia": ("la fotografia", pk_persona, False),
    "musica":     ("la musica", pk_persona, False),
    "guion":      ("el guion", pk_persona, False),
}
PREGUNTAS_TEXTO = {
    "pais": "Escribe el pais (por ejemplo: Cuba):",
    "ano": "Escribe el ano (4 digitos, por ejemplo: 2026):",
}
# Pasos que pide cada tipologia (id). Los nombres de campo son los del HAR de Picta.
FLUJOS = {
    2: ["pick:productora", "text:pais"],                                   # Documental
    1: ["text:pais", "text:ano", "pick:genero", "pick:productora", "pick:premio",
        "pick:director", "pick:reparto", "pick:fotografia", "pick:musica", "pick:guion"],   # Pelicula
}
CAMPOS_EXTRA = {tid: [p.split(":")[1] for p in pasos] for tid, pasos in FLUJOS.items()}

def extra_campos(s):
    """Campos extra segun la tipologia, con los nombres vistos en los HAR de Picta."""
    datos = s.get("datos", {})
    return [(c, str(datos[c])) for c in CAMPOS_EXTRA.get(s.get("tipologia"), []) if c in datos]

async def pedir_clasificacion(e):
    botones = [[Button.inline(c, f"cls:{c}".encode())] for c in CLASIFICACIONES]
    await e.respond("Elige la clasificacion:", buttons=botones)

async def siguiente_paso(e, s):
    if not s["flujo"]:
        s["step"] = "clasificacion"
        return await pedir_clasificacion(e)
    tipo, campo = s["flujo"].pop(0).split(":")
    s["campo"] = campo
    if tipo == "text":
        s["step"] = "texto"
        await e.respond(PREGUNTAS_TEXTO[campo])
    else:
        s["step"] = "pick"
        await mostrar_picker(e, s, "", 1)

async def mostrar_picker(e, s, q, page, edit=False):
    campo = s["campo"]
    etiqueta, fetch, listar = PICKERS[campo]
    filas, opts = [], {}
    previa = s.get("ultima_persona") if campo in PERSONAS else None
    if previa:
        filas.append([Button.inline(f"Igual que antes: {previa[1][:40]}", b"pks")])
    if not q and not listar:
        txt = f"Busca {etiqueta}: escribe parte del nombre."
        return await e.respond(txt, buttons=filas or None)
    try:
        items, sig, total = await asyncio.to_thread(fetch, q, page)
    except Exception as ex:
        return await e.respond(f"Error consultando Picta: {ex}")
    if not items:
        return await e.respond("No encontre nada con ese texto. Escribe otro nombre.")
    if campo == "premio" and not q and page == 1:
        filas.append([Button.inline("Ninguno", f"pk:{PREMIO_NINGUNO}".encode())])
        opts[PREMIO_NINGUNO] = "Ninguno"
        items = [x for x in items if x["id"] != PREMIO_NINGUNO]
    for x in items:
        opts[x["id"]] = x["nombre"]
        filas.append([Button.inline(x["nombre"][:60], f"pk:{x['id']}".encode())])
    nav = []
    if page > 1: nav.append(Button.inline("⬅️ Anterior", f"pkp:{page - 1}".encode()))
    if sig: nav.append(Button.inline("Siguiente ➡️", f"pkp:{page + 1}".encode()))
    if nav: filas.append(nav)
    s["pick_q"], s["pick_opts"] = q, opts
    txt = (f"Resultados para «{q}»" if q else f"Elige {etiqueta}") \
          + f" (pagina {page}, {total} en total).\nToca una opcion, o escribe parte del nombre para buscar."
    if edit: await e.edit(txt, buttons=filas)
    else: await e.respond(txt, buttons=filas)

async def _elegir(e, s, pid, nombre):
    campo = s["campo"]
    s["datos"][campo] = pid
    s["nombres"][campo] = nombre
    if campo in PERSONAS:
        s["ultima_persona"] = (pid, nombre)
    etiqueta = PICKERS[campo][0]
    await e.edit(f"{etiqueta.capitalize()}: {nombre}")
    await siguiente_paso(e, s)

@client.on(events.CallbackQuery(pattern=rb"pkp:(\d+)"))
async def pkp_cb(e):
    if e.sender_id != ALLOWED: return
    s = sessions.get(e.sender_id)
    if not s or s["step"] != "pick": return
    await e.answer()
    await mostrar_picker(e, s, s.get("pick_q", ""), int(e.pattern_match.group(1)), edit=True)

@client.on(events.CallbackQuery(pattern=rb"pk:(\d+)"))
async def pk_cb(e):
    if e.sender_id != ALLOWED: return
    s = sessions.get(e.sender_id)
    if not s or s["step"] != "pick": return
    pid = int(e.pattern_match.group(1))
    nombre = s.get("pick_opts", {}).get(pid)
    if not nombre:
        return await e.answer("Opcion no valida.", alert=True)
    await _elegir(e, s, pid, nombre)

@client.on(events.CallbackQuery(pattern=rb"pks"))
async def pks_cb(e):
    if e.sender_id != ALLOWED: return
    s = sessions.get(e.sender_id)
    if not s or s["step"] != "pick" or not s.get("ultima_persona"): return
    pid, nombre = s["ultima_persona"]
    await _elegir(e, s, pid, nombre)

TXT_TIPOLOGIA = ("Elige la tipologia (Audiovisual es la de siempre). "
                 "Las marcadas con \u26a0\ufe0f pueden pedir campos extra en Picta y fallar al crear la publicacion.")

def es_basica(t):
    return t.get("modelo") == "categoria"   # mismo formulario que Audiovisual

def teclado_tipologias(tips):
    orden = sorted(tips, key=lambda t: TIPOLOGIAS_PERMITIDAS.index(t["id"]) if t["id"] in TIPOLOGIAS_PERMITIDAS else 99)
    botones = [Button.inline(("" if es_basica(t) else "\u26a0\ufe0f ") + t["nombre"], f"tip:{t['id']}".encode())
               for t in orden]
    return [[b] for b in botones]

@client.on(events.CallbackQuery(pattern=rb"tip:(\d+)"))
async def tipologia_cb(e):
    if e.sender_id != ALLOWED: return
    s = sessions.get(e.sender_id)
    if not s or s["step"] != "tipologia": return
    tid = int(e.pattern_match.group(1))
    t = s.get("tips", {}).get(tid)
    if not t:
        return await e.answer("Opcion no valida.", alert=True)
    s["tipologia"] = tid
    aviso = "" if es_basica(t) else "\n\u26a0\ufe0f Sin probar: puede pedir campos extra y fallar al crear la publicacion. Usa /cancel si no quieres seguir."
    await e.edit(f"Tipologia: {t['nombre']}{aviso}")
    if tid in FLUJOS:
        s["flujo"], s["datos"], s["nombres"] = list(FLUJOS[tid]), {}, {}
        await e.respond(f"{t['nombre']} pide algunos datos mas; te los voy preguntando.")
        return await siguiente_paso(e, s)
    s["step"] = "clasificacion"
    await pedir_clasificacion(e)

@client.on(events.NewMessage(pattern=r"^/palabras"))
async def ver_palabras(e):
    if not autorizado(e): return
    lista = "\n".join(f"{i+1}. {p}" for i, p in enumerate(PALABRAS_PRESET))
    await e.respond("Palabras clave guardadas:\n" + lista
                    + "\n\nSe eligen al subir un video. Para agregar mas, edita PALABRAS_PRESET en el notebook.")

@client.on(events.NewMessage(pattern=r"^/campos"))
async def ver_campos(e):
    """Solo lectura: pregunta a Picta que campos acepta al crear una publicacion. No publica nada."""
    if not autorizado(e): return
    msg = await e.respond("Consultando a Picta los campos de publicacion...")
    def consulta():
        token = picta_token()
        r = requests.options(f"{API}/v1/publicacion/", headers={"Authorization": f"Bearer {token}"}, timeout=60)
        return r.status_code, r.text
    try:
        code, txt = await asyncio.to_thread(consulta)
    except Exception as ex:
        return await msg.edit(f"Error consultando Picta ({type(ex).__name__}): {ex}")
    try:
        txt = json.dumps(json.loads(txt), ensure_ascii=False, indent=1)
    except Exception:
        pass
    d = tempfile.mkdtemp(prefix="campos_")
    try:
        ruta = os.path.join(d, "campos_picta.txt")
        with open(ruta, "w", encoding="utf-8") as f:
            f.write(f"HTTP {code}\n{txt}")
        await msg.edit(f"Picta respondio HTTP {code} ({len(txt)} caracteres). Te mando el archivo.")
        await client.send_file(e.sender_id, ruta, caption="OPTIONS /v1/publicacion/")
    finally:
        shutil.rmtree(d, ignore_errors=True)

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
            picta_subir, s["video"], s["cover"], s["titulo"], s["descripcion"], s["palabras"], cls, estado, s.get("tipologia", int(TIPOLOGIA)), extra_campos(s),
            s["cover"] if s.get("tipologia") == 1 else None))
        ultimo_txt, avisado = "", False
        while not tarea.done():
            await asyncio.sleep(5)
            fase = estado.get("fase", "login")
            if fase == "login":
                txt = "Iniciando sesion en Picta..."
            elif fase == "validando":
                txt = "Validando los datos con Picta (aun no sube el video)..."
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
