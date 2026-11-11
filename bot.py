"""
Bot de Telegram -> Picta para GitHub Codespaces.

Configuracion (cualquiera de las dos formas):
  a) Secretos de Codespaces (GitHub > Settings > Codespaces > Secrets), con estos nombres:
     TG_API_ID, TG_API_HASH, TG_BOT_TOKEN, TG_ALLOWED_USER_ID,
     PICTA_USER, PICTA_PASS, PICTA_CANAL_ID
  b) Un archivo .env junto a bot.py (ver .env.ejemplo). Esta en .gitignore: no lo subas a GitHub.

Instalar:  pip install -r requirements.txt
Ejecutar:  python bot.py
"""
import os

_RAROS = " \t\r\n\ufeff\u200b\u200c\u200d\u00a0"   # espacios invisibles que a veces mete el teclado del movil

def _cargar_env():
    """Carga variables desde .env (CLAVE=valor), si existe. No pisa una variable que ya tenga valor,
    pero si una que exista vacia (por ejemplo, un secreto de Codespaces sin contenido)."""
    ruta = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    cargadas = []
    try:
        with open(ruta, encoding="utf-8") as f:
            for linea in f:
                linea = linea.strip(_RAROS)
                if not linea or linea.startswith("#") or "=" not in linea:
                    continue
                k, v = linea.split("=", 1)
                k, v = k.strip(_RAROS), v.strip(_RAROS).strip('"').strip("'")
                if k and not os.environ.get(k):
                    os.environ[k] = v
                    cargadas.append(k)
    except FileNotFoundError:
        pass
    if cargadas:
        print("Variables leidas de .env:", ", ".join(cargadas), flush=True)

_cargar_env()

def cfg(nombre, secreto=False, default=None):
    v = os.environ.get(nombre)
    if v:
        return v
    if default is not None:
        return default
    raise SystemExit(f"Falta la variable de entorno {nombre}" + (" (existe pero esta vacia)" if v == "" else ""))

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
# Para agregar mas, anadelas aqui y y reinicia el bot.
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
# Tipologias que se muestran en el menu (en este orden): 8 = Audiovisual, 1 = Pelicula.
# Para mostrar otra, anade su id aqui (ids en TIPOLOGIAS_RESPALDO; 5 = Serie, 2 = Documental, sin probar).
TIPOLOGIAS_PERMITIDAS = [8, 1, 5]   # 5 = Serie (capitulos de una serie/temporada)

# ---- Modo automatico (/auto): valores que se usan sin preguntarte nada, salvo titulo, descripcion y portada ----
# Escribelos tal cual existen en Picta (da igual mayusculas o tildes). Si alguno no existe, el bot te lo dice
# y sigue en modo normal con ese video. Cambialos a tu gusto.
AUTO = {
    "tipologia": 8,                          # 8 = Audiovisual, 1 = Pelicula
    "clasificacion": "ATP",
    "palabras": ["Series"],
    # Solo se usan si la tipologia es Pelicula:
    "pais": "Cuba",
    "ano": None,                             # None = el ano actual
    "genero": "Drama",
    "productora": "Warner Bros. DC Entertainment",
    "premio": "Ninguno",
    "persona": "Bruce W. Timm",              # se usa como director, reparto, fotografia, musica y guion
}
ESTADO_AUTO = {"activo": False, "tipologia": AUTO["tipologia"]}   # se reinicia si el bot se reinicia
print("Configuracion cargada.")

# ---- Estilo del bot: mascota + lineas limpias + barra de progreso ----
MASCOTA    = "🦊"
NOMBRE_BOT = "Fito"
LINEA      = "─" * 16

def barra(pct, ancho=12):
    """Barra de progreso: barra(40) -> ▰▰▰▰▰▱▱▱▱▱▱▱"""
    pct = max(0, min(100, int(pct)))
    llenos = round(ancho * pct / 100)
    return "▰" * llenos + "▱" * (ancho - llenos)

def _dur(seg):
    seg = int(seg)
    if seg < 60:
        return f"{seg} s"
    m, s = divmod(seg, 60)
    if m < 60:
        return f"{m} min"
    h, m = divmod(m, 60)
    return f"{h} h {m} min"

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
SIN_AVANCE_MAX = 300   # segundos sin mover datos antes de dar la subida por cortada
# Limite de velocidad de subida a Picta en MB/s (0 = sin limite). Se puede cambiar con /velocidad N
# o con la variable de entorno VEL_MAX_MBS.
VEL_MAX = float(os.environ.get("VEL_MAX_MBS", "4"))
INTENTOS_SUBIDA = 3    # cada intento pide una URL firmada nueva y empieza desde cero

_TOKEN = {"v": None, "hasta": 0.0}

def picta_token():
    """Token de Picta; se reutiliza ~3 h (dura 4 h) para no iniciar sesion en cada busqueda."""
    if _TOKEN["v"] and time.time() < _TOKEN["hasta"]:
        return _TOKEN["v"]
    fields = {
        "username": (None, PICTA_USER),
        "password": (None, PICTA_PASS),
        "grant_type": (None, "password"),
        "client_id": (None, PICTA_CLIENT_ID),
    }
    r = requests.post(f"{API}/o/token/", files=fields, timeout=60)
    r.raise_for_status()
    _TOKEN["v"] = r.json()["access_token"]
    _TOKEN["hasta"] = time.time() + 3 * 3600
    return _TOKEN["v"]

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


# ---- Series y temporadas (campos tomados del HAR de admin.picta.cu) ----
# Valor por defecto de "visible" al crear una serie. En /serie el bot te pregunta con botones; esto es solo el respaldo.
SERIE_VISIBLE = "false"

def _auth():
    return {"Authorization": f"Bearer {picta_token()}"}

def _admin(referer="https://admin.picta.cu/publicaciones/add"):
    """Cabeceras como las de la web de admin. Sin Origin/Referer de admin.picta.cu, Picta devuelve el
    catalogo publico en vez de TUS series/temporadas (igual que en el panel)."""
    return {**_auth(), **ADMIN_HDR, "Referer": referer}

def pk_serie(q, page):
    """Series de TU canal (se filtran aqui por canal). El id de una serie en Picta es 'pelser_id'."""
    r = requests.get(f"{API}/v2/serie/", params={"page_size": 100, "ordering": "nombre"},
                     headers=_admin(), timeout=60)
    r.raise_for_status()
    crudas = r.json().get("results", [])
    todas = []
    for x in crudas:
        if str((x.get("canal") or {}).get("id")) != str(CANAL_ID):
            continue
        nombre = " ".join((x.get("nombre") or "").split())
        if nombre and x.get("pelser_id") is not None:
            todas.append({"id": int(x["pelser_id"]), "nombre": nombre})
    print(f"pk_serie: Picta devolvio {len(crudas)} series, {len(todas)} del canal {CANAL_ID}", flush=True)
    if q:
        todas = [x for x in todas if _norm(q) in _norm(x["nombre"])]
    ini = (page - 1) * 8
    return todas[ini:ini + 8], len(todas) > ini + 8, len(todas)

# Las temporadas que crea el bot se anotan aqui, para poder reutilizarlas aunque Picta tarde en listarlas.
ARCHIVO_TEMPORADAS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "temporadas_estado.json")

def _temp_cargar():
    try:
        with open(ARCHIVO_TEMPORADAS, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, ValueError):
        return {}

def _temp_guardar(serie_id, numero, tid):
    d = _temp_cargar()
    d.setdefault(str(serie_id), {})[str(numero)] = int(tid)
    try:
        with open(ARCHIVO_TEMPORADAS, "w", encoding="utf-8") as f:
            json.dump(d, f)
    except OSError as ex:
        print("No pude guardar las temporadas:", ex, flush=True)

def _temporadas_todas(serie_id):
    """Temporadas de una serie: las que lista Picta + las que creo el bot (sin repetir)."""
    por_id = {}

    def de_esta_serie(x):
        s = x.get("serie")
        if isinstance(s, dict):
            s = s.get("pelser_id", s.get("id"))
        return str(s) == str(serie_id)

    def anotar(resultados, filtrar):
        for x in resultados:
            if x.get("id") is None or (filtrar and not de_esta_serie(x)):
                continue
            por_id[int(x["id"])] = {"id": int(x["id"]), "numero": int(x.get("numero") or 0),
                                    "nombre": " ".join((x.get("nombre") or "").split())}

    try:
        r = requests.get(f"{API}/v2/temporada/", params={"page_size": 100, "serie_pelser_id": serie_id},
                         headers=_admin(), timeout=60)
        r.raise_for_status()
        anotar(r.json().get("results", []), False)
        print(f"pk_temporada: filtrando por serie, Picta devolvio {len(por_id)} temporadas (serie {serie_id})", flush=True)
        if not por_id:   # respaldo: pedir todas las tuyas y quedarme con las de esta serie
            r = requests.get(f"{API}/v2/temporada/", params={"page_size": 100}, headers=_admin(), timeout=60)
            r.raise_for_status()
            crudas = r.json().get("results", [])
            anotar(crudas, True)
            print(f"pk_temporada: sin filtro, Picta devolvio {len(crudas)} temporadas, {len(por_id)} de la serie {serie_id}", flush=True)
    except Exception as ex:
        print(f"pk_temporada: no pude leer las temporadas de Picta ({type(ex).__name__}): {ex}", flush=True)
    for num, tid in _temp_cargar().get(str(serie_id), {}).items():
        por_id.setdefault(int(tid), {"id": int(tid), "numero": int(num), "nombre": f"Temporada {num}"})
    return sorted(por_id.values(), key=lambda t: t["numero"])

def pk_temporada(serie_id, q, page):
    todas = []
    for t in _temporadas_todas(serie_id):
        extra = f" · {t['nombre']}" if t["nombre"] and t["nombre"] != f"Temporada {t['numero']}" else ""
        todas.append({"id": t["id"], "numero": t["numero"], "nombre": f"Temporada {t['numero']}{extra}"})
    if q:
        todas = [x for x in todas if _norm(q) in _norm(x["nombre"])]
    ini = (page - 1) * 8
    return todas[ini:ini + 8], len(todas) > ini + 8, len(todas)

def picta_temporada_asegurar(serie_id, numero):
    """Devuelve (id, creada). Si la temporada ya existe, la reutiliza en vez de crear otra."""
    for t in _temporadas_todas(serie_id):
        if t["numero"] == int(numero):
            return t["id"], False
    tid = picta_crear_temporada(serie_id, numero, f"Temporada {numero}")
    _temp_guardar(serie_id, numero, tid)
    return tid, True

def picta_crear_temporada(serie_id, numero, nombre):
    """POST /v1/temporada/ (igual que la web). Devuelve el id de la temporada."""
    campos = {
        "cantidad_capitulos": (None, "0"), "numero": (None, str(numero)), "nombre": (None, nombre),
        "canal": (None, str(CANAL_ID)), "serie": (None, str(serie_id)),
    }
    r = requests.post(f"{API}/v1/temporada/", files=campos, headers=_admin(), timeout=60)
    if r.status_code != 201:
        raise RuntimeError(f"Picta rechazo la temporada ({r.status_code}): {r.text[:300]}")
    return int(r.json()["id"])

def picta_crear_serie(s):
    """POST /v1/serie/ con los datos reunidos en la sesion. Devuelve el JSON de Picta (pelser_id = id de la serie)."""
    d = s["datos"]
    with ExitStack() as stk:
        poster = stk.enter_context(open(s["cover"], "rb"))
        secundaria = stk.enter_context(open(s["cover"], "rb"))   # la web manda la misma imagen en las dos
        parts = [
            ("nombre", s["titulo"]), ("sinopsis", s["descripcion"]), ("canal", str(CANAL_ID)),
            ("ano", str(d["ano"])), ("pais", str(d["pais"])), ("genero", str(d["genero"])),
            ("cantidad_temporadas", str(d["temporadas"])), ("cantidad_capitulos", "0"),
            ("clasificacion", s["clasificacion"]),
            ("director", str(d["director"])), ("reparto", str(d["reparto"])),
            ("productora", str(d["productora"])), ("fotografia", str(d["fotografia"])),
            ("musica", str(d["musica"])), ("guion", str(d["guion"])),
            ("url_imagen", ("poster.jpeg", poster, "image/jpeg")),
            ("imagen_secundaria", ("img.jpeg", secundaria, "image/jpeg")),
            ("visible", s.get("visible", SERIE_VISIBLE)), ("internacional", "false"),
        ]
        enc = MultipartEncoder(fields=parts)
        r = requests.post(f"{API}/v1/serie/", data=enc,
                          headers={**_auth(), "Content-Type": enc.content_type}, timeout=300)
    if r.status_code != 201:
        raise RuntimeError(f"Picta rechazo la serie ({r.status_code}): {r.text[:500]}")
    return r.json()

def picta_subir(video_path, cover_path, nombre, descripcion, palabra_ids, clasificacion, estado, tipologia=TIPOLOGIA, extra=None, poster_path=None, publicado="true"):
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
            ("publicado", publicado), ("descargable", "true"), ("mostrar_comentarios", "true"),
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

    tam = os.path.getsize(video_path)
    ext = os.path.splitext(video_path)[1].lower()
    mime = {".mp4": "video/mp4", ".mov": "video/quicktime", ".avi": "video/x-msvideo"}.get(ext, "video/webm")

    for intento in range(1, INTENTOS_SUBIDA + 1):
        estado["intento"] = intento
        estado["fase"] = "login" if intento == 1 else "reintentando"

        # 1) URL firmada (una nueva en cada intento)
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
        if limite and tam > limite:
            raise RuntimeError(f"El video pesa {tam // 1048576} MB y Picta solo acepta {limite // 1048576} MB.")

        # 2) Subir el video (campos firmados primero, archivo al final)
        with open(video_path, "rb") as f:
            parts = list(fields.items())
            parts.append(("file", (os.path.basename(video_path), f, mime)))
            enc = MultipartEncoder(fields=parts)
            estado.update(fase="subiendo", total=enc.len, enviado=0, t_ultimo=time.time(), t_inicio=time.time())

            def cb(m):
                if m.bytes_read != estado["enviado"]:
                    estado["enviado"] = m.bytes_read
                    estado["t_ultimo"] = time.time()
                lim = VEL_MAX * 1048576
                if lim > 0:   # frenar la lectura para no pasar de VEL_MAX MB/s
                    espera = estado["t_inicio"] + m.bytes_read / lim - time.time()
                    if espera > 0.05:
                        time.sleep(min(espera, 2))

            mon = MultipartEncoderMonitor(enc, cb)
            try:
                # timeout=(conexion, sin-actividad): si pasan SIN_AVANCE_MAX s sin mover datos, se corta
                r = requests.post(url, data=mon, headers={"Content-Type": mon.content_type},
                                  timeout=(30, SIN_AVANCE_MAX))
            except requests.exceptions.RequestException as ex:
                parado = time.time() - estado["t_ultimo"]
                enviado = estado["enviado"] // 1048576
                if parado >= SIN_AVANCE_MAX - 15:
                    motivo = f"la subida se estanco: {int(parado)} s sin avanzar"
                else:
                    motivo = f"el servidor cerro la conexion ({type(ex).__name__})"
                print(f"Intento {intento} fallo: {motivo}; enviados {enviado} MB de {tam // 1048576} MB", flush=True)
                if intento == INTENTOS_SUBIDA:
                    raise RuntimeError(
                        f"Fallo tras {INTENTOS_SUBIDA} intentos. Ultimo: {motivo}, con {enviado} MB de "
                        f"{tam // 1048576} MB enviados.") from ex
                estado["aviso"] = (f"Intento {intento} fallo: {motivo} ({enviado} MB de {tam // 1048576} MB). "
                                   f"Reintentando ({intento + 1}/{INTENTOS_SUBIDA}) desde cero...")
                time.sleep(5)
                continue
        if r.status_code not in (200, 201, 204):
            raise RuntimeError(f"Fallo subiendo el video: {r.status_code} {r.text[:300]}")
        break

    # 3) Crear la publicacion
    estado["fase"] = "publicando"
    with ExitStack() as stk:
        cf = stk.enter_context(open(cover_path, "rb"))
        parts = [
            ("nombre", nombre), ("canal", str(CANAL_ID)), ("descripcion", descripcion),
            ("descargable", "true"), ("mostrar_comentarios", "true"),
            ("url_manifiesto", key), ("tipologia", str(tipologia)), ("tipo", "publicacion"),
            ("publicado", publicado), ("internacional", "false"),
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

@client.on(events.NewMessage(pattern=r"^/velocidad"))
async def velocidad(e):
    global VEL_MAX
    if not autorizado(e): return
    partes = e.raw_text.split()
    if len(partes) == 1:
        actual = f"{VEL_MAX:g} MB/s" if VEL_MAX > 0 else "sin limite"
        return await e.respond(f"Limite de subida a Picta: {actual}.\nPara cambiarlo: /velocidad 3  (0 = sin limite)")
    try:
        v = float(partes[1].replace(",", "."))
        if v < 0 or v > 100: raise ValueError
    except ValueError:
        return await e.respond("Escribe un numero de MB/s entre 0 y 100, por ejemplo /velocidad 3")
    VEL_MAX = v
    await e.respond(f"Limite de subida: {v:g} MB/s." if v > 0 else "Subida sin limite de velocidad.")

NOMBRES_TIPOLOGIA = {8: "Audiovisual", 1: "Pel\u00edcula"}
ALIAS_TIPOLOGIA = {"audiovisual": 8, "video": 8, "pelicula": 1, "pel\u00edcula": 1, "peli": 1}


def texto_bienvenida():
    return (
        f"{MASCOTA} ¡Hola! Soy {NOMBRE_BOT}, tu zorro de Picta.\n\n"
        "Mándame un video y me encargo de subirlo. "
        "Te iré pidiendo el título, la descripción, las palabras clave y la portada.\n\n"
        f"{LINEA}\n"
        "**Comandos**\n"
        "/ayuda · cómo se usa\n"
        "/auto · modo automático\n"
        "/panel · estadísticas del canal\n"
        "/comentarios · ver y responder comentarios\n"
        "/palabras · palabras clave frecuentes\n"
        "/velocidad · límite de subida\n"
        "/cancel · cancelar lo que estoy haciendo")


def texto_ayuda():
    por_defecto = NOMBRES_TIPOLOGIA.get(AUTO["tipologia"], "Audiovisual")
    return (
        f"{MASCOTA} **Cómo usarme**\n"
        f"{LINEA}\n"
        "**Subir un video**\n"
        "1 · Mándame el video\n"
        "2 · Título (máx. 90) y descripción (máx. 3000)\n"
        "3 · Palabras clave: toca los botones o escríbelas separadas por coma, y pulsa Listo\n"
        "4 · Portada, como foto\n"
        "5 · Tipología: Audiovisual o Película (la película pide más datos)\n"
        "6 · Clasificación, y empiezo a subir\n\n"
        "**Modo automático**\n"
        "Uso los valores guardados y solo te pido título, descripción y portada.\n"
        f"/auto · activar ({por_defecto})\n"
        "/auto pelicula · activar para película\n"
        "/auto audiovisual · activar para audiovisual\n"
        "/auto off · volver al modo normal\n\n"
        "**Crear (contenedores)**\n"
        "/serie · crear una serie (nombre, sinopsis, datos, poster)\n"
        "/temporada · crear una temporada dentro de una serie\n\n"
        "**Subir un capítulo**\n"
        "Mándame el video y elige la tipología Serie; solo eliges la serie y la temporada que ya existen, y el número del capítulo.\n\n"
        "**Panel**\n"
        "/panel · estadísticas y lista de videos; toca un número para ver su ficha\n\n"
        "**Comentarios**\n"
        "Te aviso cuando alguien comenta, con un botón Responder.\n"
        "/comentarios · los pendientes\n"
        "/comentarios todos · los últimos\n"
        "/comentarios 10 · cuántos muestro (máx. 10)\n\n"
        "**Otros**\n"
        "/velocidad 3 · límite de subida en MB/s (0 = sin límite)\n"
        "/palabras · palabras clave frecuentes\n"
        "/cancel · cancelar")

def resumen_auto(tip):
    lineas = [f"\u2022 Palabras clave: {', '.join(AUTO['palabras'])}",
              f"\u2022 Clasificaci\u00f3n: {AUTO['clasificacion']}"]
    if tip == 1:
        lineas += [f"\u2022 Pa\u00eds: {AUTO['pais']} \u00b7 A\u00f1o: {AUTO.get('ano') or 'el actual'} \u00b7 G\u00e9nero: {AUTO['genero']}",
                   f"\u2022 Productora: {AUTO['productora']} \u00b7 Premio: {AUTO['premio']}",
                   f"\u2022 Director, reparto, fotograf\u00eda, m\u00fasica y guion: {AUTO['persona']}"]
    return "\n".join(lineas)

@client.on(events.NewMessage(pattern="/start"))
async def start(e):
    if autorizado(e):
        await e.respond(texto_bienvenida())

@client.on(events.NewMessage(pattern=r"^/(ayuda|help)\b"))
async def ayuda(e):
    if autorizado(e):
        await e.respond(texto_ayuda())

@client.on(events.NewMessage(pattern=r"^/(auto|manual)\b"))
async def auto_cmd(e):
    if not autorizado(e): return
    partes = e.raw_text.lower().split()
    cmd, arg = partes[0].lstrip("/"), (partes[1] if len(partes) > 1 else "")
    if cmd == "manual" or arg in ("off", "no", "apagar", "manual", "0"):
        ESTADO_AUTO["activo"] = False
        return await e.respond("Modo autom\u00e1tico desactivado. Te pregunto todo como siempre.")
    tip = AUTO["tipologia"] if not arg else ALIAS_TIPOLOGIA.get(arg)
    if tip is None:
        return await e.respond("No entend\u00ed. Usa /auto, /auto pelicula, /auto audiovisual o /auto off.")
    ESTADO_AUTO.update(activo=True, tipologia=tip)
    await e.respond(
        f"\u26a1 Modo autom\u00e1tico ACTIVADO ({NOMBRES_TIPOLOGIA.get(tip, tip)}).\n"
        "Rellenar\u00e9 solo esto:\n" + resumen_auto(tip) + "\n\n"
        "Solo te pedir\u00e9 el t\u00edtulo, la descripci\u00f3n y la portada.\n"
        "Se mantiene hasta que lo apagues con /auto off (o se reinicie el bot).")

@client.on(events.NewMessage(pattern=r"^/serie\b"))
async def serie_cmd(e):
    if not autorizado(e): return
    limpiar(e.sender_id)
    RESPONDIENDO.pop(e.sender_id, None)
    sessions[e.sender_id] = {"dir": tempfile.mkdtemp(prefix="picta_"), "modo": "serie", "step": "s_nombre",
                             "datos": {}, "nombres": {}, "flujo": []}
    await e.respond(f"{MASCOTA} **Nueva serie**\nEscribe el nombre (max. 90 caracteres).")

@client.on(events.NewMessage(pattern=r"^/temporada\b"))
async def temporada_cmd(e):
    if not autorizado(e): return
    limpiar(e.sender_id)
    RESPONDIENDO.pop(e.sender_id, None)
    s = sessions[e.sender_id] = {"dir": tempfile.mkdtemp(prefix="picta_"), "modo": "temporada", "step": "pick",
                                 "datos": {}, "nombres": {}, "flujo": ["pick:serie", "text:temp_nueva"]}
    await e.respond(f"{MASCOTA} **Nueva temporada**\nElige la serie.")
    await siguiente_paso(e, s)

@client.on(events.NewMessage(pattern="/cancel"))
async def cancel(e):
    if autorizado(e):
        limpiar(e.sender_id)
        RESPONDIENDO.pop(e.sender_id, None)
        await e.respond(f"{MASCOTA} Cancelado. Aquí estoy cuando me necesites.")

# ---- Descarga rapida del video desde Telegram ----
# Se pide el archivo en N tramos a la vez (en vez de uno detras de otro). Cambia el numero con la variable de
# entorno DESCARGAS_PARALELAS (0 o 1 = descarga normal). Si algo sale mal, se descarga de la forma normal.
DESCARGAS_PARALELAS = int(os.environ.get("DESCARGAS_PARALELAS", "4"))
_CHUNK = 512 * 1024                  # tamano de cada peticion a Telegram
_MIN_PARALELA = 20 * 1048576         # por debajo de esto no vale la pena

async def descargar_rapido(e, carpeta, progreso):
    """Devuelve la ruta del video descargado en `carpeta`."""
    normal = lambda: e.download_media(file=carpeta + "/", progress_callback=progreso)
    n = DESCARGAS_PARALELAS
    total = getattr(e.file, "size", 0) or 0
    if n < 2 or total < _MIN_PARALELA:
        return await normal()
    ruta = os.path.join(carpeta, e.file.name or ("video" + (e.file.ext or ".mp4")))
    chunks_total = -(-total // _CHUNK)
    por_parte = -(-chunks_total // n)            # tramos de igual tamano, alineados a _CHUNK
    esperado = [max(0, min(total, (i + 1) * por_parte * _CHUNK) - i * por_parte * _CHUNK) for i in range(n)]
    hechos = [0] * n
    t0 = time.time()

    async def parte(i):
        if esperado[i] <= 0:
            return
        pos = i * por_parte * _CHUNK
        with open(ruta, "r+b") as f:
            f.seek(pos)
            async for trozo in client.iter_download(e.media, offset=pos, limit=por_parte,
                                                    request_size=_CHUNK, chunk_size=_CHUNK):
                f.write(trozo)
                hechos[i] += len(trozo)
                await progreso(sum(hechos), total)
                if hechos[i] >= esperado[i]:
                    break

    try:
        with open(ruta, "wb") as f:
            f.truncate(total)
        await asyncio.gather(*(parte(i) for i in range(n)))
        if hechos != esperado:
            raise RuntimeError(f"tamano distinto del esperado ({sum(hechos)} de {total} bytes)")
    except asyncio.CancelledError:
        raise
    except Exception as ex:
        print(f"Descarga rapida fallo ({type(ex).__name__}: {ex}); uso la descarga normal.", flush=True)
        try:
            os.remove(ruta)
        except OSError:
            pass
        return await normal()
    seg = max(time.time() - t0, 1)
    print(f"Descarga rapida: {total // 1048576} MB en {seg:.0f} s ({total / seg / 1048576:.1f} MB/s, {n} tramos)", flush=True)
    return ruta

@client.on(events.NewMessage(func=es_video))
async def recibir_video(e):
    if not autorizado(e): return
    limpiar(e.sender_id)
    RESPONDIENDO.pop(e.sender_id, None)   # si estabas escribiendo una respuesta, empieza el video y se descarta
    d = tempfile.mkdtemp(prefix="picta_")
    msg = await e.respond(f"{MASCOTA} **Descargando tu video…**\n{barra(0)} 0%")
    import time
    ultimo = [0]
    t_desc = time.time()
    async def progreso(actual, total):
        if time.time() - ultimo[0] < 5: return
        ultimo[0] = time.time()
        try:
            await msg.edit(f"{MASCOTA} **Descargando tu video…**\n{barra(actual*100//total)} {actual*100//total}%\n\n{actual//1048576} / {total//1048576} MB\n{actual / max(time.time() - t_desc, 1) / 1048576:.1f} MB/s")
        except Exception:
            pass
    path = await descargar_rapido(e, d, progreso)
    sessions[e.sender_id] = {"dir": d, "video": path, "step": "titulo"}
    extra = "\n\u26a1 Modo autom\u00e1tico activado (/auto off para quitarlo)." if ESTADO_AUTO["activo"] else ""
    await msg.edit(f"{MASCOTA} ¡Video recibido!\n\n**Título**\nEscríbelo (máx. 90 caracteres)." + extra)

@client.on(events.NewMessage(func=lambda e: not es_video(e)))
async def conversacion(e):
    if not autorizado(e): return
    if e.raw_text and e.raw_text.startswith("/"): return
    if RESPONDIENDO.get(e.sender_id) and e.raw_text:
        return await enviar_respuesta(e, RESPONDIENDO[e.sender_id])
    s = sessions.get(e.sender_id)
    if not s: return
    step = s["step"]

    if step == "titulo":
        t = e.raw_text.strip()
        if not t or len(t) > 90:
            return await e.respond("El titulo debe tener entre 1 y 90 caracteres.")
        s["titulo"], s["step"] = t, "descripcion"
        await e.respond(f"{MASCOTA} **Descripción**\nEscríbela (máx. 3000 caracteres).")

    elif step == "descripcion":
        t = e.raw_text.strip()
        if not t or len(t) > 3000:
            return await e.respond("La descripcion debe tener entre 1 y 3000 caracteres.")
        s["descripcion"], s["step"] = t, "palabras"
        if ESTADO_AUTO["activo"]:
            await e.respond("\u26a1 Modo autom\u00e1tico: buscando los datos en Picta...")
            try:
                s["auto"] = await asyncio.wait_for(asyncio.to_thread(auto_resolver, ESTADO_AUTO["tipologia"]), timeout=120)
            except Exception as ex:
                s["auto"] = None
                await e.respond(f"\u26a0\ufe0f No pude completar el modo autom\u00e1tico: {str(ex) or type(ex).__name__}\n"
                                "Sigo en modo normal con este video.")
            else:
                s["step"] = "portada"
                return await e.respond("\u2705 Datos autom\u00e1ticos listos. Ahora m\u00e1ndame la imagen de portada (como foto):")
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
        await e.respond(f"Buscando «{q}» en Picta...")
        try:
            await asyncio.wait_for(mostrar_picker(e, s, q, 1), timeout=100)
        except asyncio.TimeoutError:
            await e.respond("Picta tardo demasiado en responder. Escribe el nombre otra vez para reintentar.")
        except Exception as ex:
            await e.respond(f"Error buscando ({type(ex).__name__}): {ex}")

    elif step == "texto":
        campo, v = s["campo"], e.raw_text.strip()
        if campo == "ano":
            if not (v.isdigit() and len(v) == 4 and 1888 <= int(v) <= 2100):
                return await e.respond("Escribe un ano de 4 digitos, por ejemplo 2026.")
        elif campo in ("numero", "temporadas", "temp_nueva"):
            if not (v.isdigit() and 1 <= int(v) <= 9999):
                return await e.respond("Escribe un numero valido, por ejemplo 1.")
            if campo == "temp_nueva":
                return await crear_temporada_flujo(e, s, int(v))
        elif not v or len(v) > 60:
            return await e.respond("Escribe el pais (maximo 60 caracteres).")
        s["datos"][campo] = v
        await siguiente_paso(e, s)

    elif step == "s_nombre":
        t = e.raw_text.strip()
        if not t or len(t) > 90:
            return await e.respond("El nombre debe tener entre 1 y 90 caracteres.")
        s["titulo"], s["step"] = t, "s_sinopsis"
        await e.respond(f"{MASCOTA} **Sinopsis**\nEscribela (max. 3000 caracteres).")

    elif step == "s_sinopsis":
        t = e.raw_text.strip()
        if not t or len(t) > 3000:
            return await e.respond("La sinopsis debe tener entre 1 y 3000 caracteres.")
        s["descripcion"], s["flujo"] = t, list(FLUJO_SERIE)
        await e.respond("Ahora unos datos de la serie; te los voy preguntando.")
        await siguiente_paso(e, s)

    elif step == "s_portada":
        if not e.photo:
            return await e.respond("Mandame una foto para el poster de la serie.")
        s["cover"] = await e.download_media(file=s["dir"] + "/cover.jpg")
        s["step"] = "s_creando"
        await e.respond(f"{MASCOTA} Creando la serie en Picta…")
        try:
            res = await asyncio.to_thread(picta_crear_serie, s)
        except Exception as ex:
            s["step"] = "s_portada"
            return await e.respond(f"No pude crear la serie: {ex}\nPuedes mandar la foto otra vez, o /cancel.")
        limpiar(e.sender_id)
        await e.respond(f"{MASCOTA} ¡Serie creada!\n{res.get('nombre', '')}\n\n"
                        "Para subir un capitulo: mandame el video y elige la tipologia Serie.",
                        parse_mode=None)

    elif step == "portada":
        if not e.photo:
            return await e.respond("Mandame una foto para la portada.")
        s["cover"] = await e.download_media(file=s["dir"] + "/cover.jpg")
        if s.get("auto"):
            return await lanzar_auto(e, s)
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
        aviso = TXT_TIPOLOGIA_AVISO if any(not es_basica(t) for t in tips) else ""
        await e.respond(TXT_TIPOLOGIA + aviso, buttons=teclado_tipologias(tips))

TXT_PALABRAS = (f"{MASCOTA} **Palabras clave**\n"
                "Toca para marcar o desmarcar. También puedes escribir otras separadas por coma. "
                "Cuando termines, pulsa Listo.")

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

def _buscar_exacto(fetch, etiqueta, nombre):
    """Busca en Picta un nombre exacto (da igual mayusculas o tildes). Devuelve {id, nombre}."""
    vistos = []
    for page in (1, 2, 3):
        items, sig, _ = fetch(nombre, page)
        for x in items:
            if _norm(x["nombre"]) == _norm(nombre):
                return x
        vistos += [x["nombre"] for x in items]
        if not sig:
            break
    pista = f" Parecidos: {', '.join(vistos[:3])}." if vistos else ""
    raise ValueError(f"no encontr\u00e9 {etiqueta} \u00ab{nombre}\u00bb en Picta con ese nombre exacto.{pista}")

def auto_resolver(tipologia):
    """Convierte los valores de AUTO (nombres) en lo que pide Picta (ids). Lanza ValueError si algo no existe."""
    if tipologia not in (8, 1):
        raise ValueError("el modo autom\u00e1tico solo funciona con Audiovisual y Pel\u00edcula")
    if AUTO["clasificacion"] not in CLASIFICACIONES:
        raise ValueError(f"la clasificaci\u00f3n \u00ab{AUTO['clasificacion']}\u00bb no es v\u00e1lida")
    token = picta_token()
    ids, faltan, sug = picta_buscar_palabras(token, AUTO["palabras"])
    if faltan:
        raise ValueError("estas palabras clave no existen en Picta: " + ", ".join(faltan))
    r = {"tipologia": tipologia, "clasificacion": AUTO["clasificacion"], "palabras": ids, "datos": {}, "nombres": {}}
    if tipologia == 1:   # Pelicula
        d, n = r["datos"], r["nombres"]
        d["pais"] = AUTO["pais"]
        d["ano"] = str(AUTO.get("ano") or time.localtime().tm_year)
        x = _buscar_exacto(pk_genero, "el g\u00e9nero", AUTO["genero"]);        d["genero"], n["genero"] = x["id"], x["nombre"]
        x = _buscar_exacto(pk_productora, "la productora", AUTO["productora"]); d["productora"], n["productora"] = x["id"], x["nombre"]
        if _norm(AUTO["premio"]) == "ninguno":
            d["premio"], n["premio"] = PREMIO_NINGUNO, "Ninguno"
        else:
            x = _buscar_exacto(pk_premio, "el premio", AUTO["premio"]);          d["premio"], n["premio"] = x["id"], x["nombre"]
        x = _buscar_exacto(pk_persona, "la persona", AUTO["persona"])
        for campo in PERSONAS:
            d[campo], n[campo] = x["id"], x["nombre"]
    return r

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
    "serie":      ("la serie", pk_serie, True),
    "temporada":  ("la temporada", None, True),   # su busqueda se arma en mostrar_picker (necesita la serie elegida)
}
PREGUNTAS_TEXTO = {
    "pais": "Escribe el pais (por ejemplo: Cuba):",
    "ano": "Escribe el ano (4 digitos, por ejemplo: 2026):",
    "numero": "Escribe el numero del capitulo (por ejemplo: 1):",
    "temporadas": "Cuantas temporadas tiene la serie? (un numero, por ejemplo: 2):",
    "temp_nueva": "Escribe el numero de la temporada (por ejemplo: 1). Si ya existe, la uso:",
}
# Pasos que pide cada tipologia (id). Los nombres de campo son los del HAR de Picta.
FLUJOS = {
    2: ["pick:productora", "text:pais"],                                   # Documental
    1: ["text:pais", "text:ano", "pick:genero", "pick:productora", "pick:premio",
        "pick:director", "pick:reparto", "pick:fotografia", "pick:musica", "pick:guion"],   # Pelicula
    5: ["pick:serie", "pick:temporada", "text:numero"],                    # Serie (capitulo)
}
# Datos que se piden al CREAR una serie con /serie (despues de titulo y sinopsis; luego clasificacion y portada)
FLUJO_SERIE = ["text:pais", "text:ano", "pick:genero", "pick:productora", "pick:director",
               "pick:reparto", "pick:fotografia", "pick:musica", "pick:guion", "text:temporadas"]
CAMPOS_EXTRA = {tid: [p.split(":")[1] for p in pasos] for tid, pasos in FLUJOS.items()}

def extra_campos(s):
    """Campos extra segun la tipologia, con los nombres vistos en los HAR de Picta."""
    datos = s.get("datos", {})
    return [(c, str(datos[c])) for c in CAMPOS_EXTRA.get(s.get("tipologia"), []) if c in datos]

async def pedir_clasificacion(e):
    botones = [[Button.inline(c, f"cls:{c}".encode())] for c in CLASIFICACIONES]
    await e.respond(f"{MASCOTA} **Clasificación**\nElige para qué público es.", buttons=botones)

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
    if campo == "temporada":
        serie_id = s["datos"]["serie"]
        fetch = lambda q_, p_: pk_temporada(serie_id, q_, p_)
    filas, opts = [], {}
    previa = s.get("ultima_persona") if campo in PERSONAS else None
    if previa:
        filas.append([Button.inline(f"Igual que antes: {previa[1][:40]}", b"pks")])
    if campo == "temporada":
        filas.append([Button.inline("➕ Nueva temporada", b"pkn")])
    if not q and not listar:
        txt = f"Busca {etiqueta}: escribe parte del nombre."
        return await e.respond(txt, buttons=filas or None)
    try:
        items, sig, total = await asyncio.to_thread(fetch, q, page)
    except Exception as ex:
        return await e.respond(f"Error consultando Picta: {ex}")
    if not items:
        if campo == "temporada" and not q:
            return await e.respond("Esta serie aun no tiene temporadas. Crea la primera:", buttons=filas)
        if campo == "serie" and not q:
            return await e.respond("No encontre series en tu canal. Crea una con /serie y vuelve a subir el video.")
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

@client.on(events.CallbackQuery(pattern=rb"pkn"))
async def pkn_cb(e):
    if e.sender_id != ALLOWED: return
    s = sessions.get(e.sender_id)
    if not s or s["step"] != "pick" or s.get("campo") != "temporada": return
    await e.answer()
    s["step"], s["campo"] = "texto", "temp_nueva"
    await e.respond("Escribe el numero de la nueva temporada (por ejemplo: 2):")

async def crear_temporada_flujo(e, s, num):
    try:
        tid, creada = await asyncio.to_thread(picta_temporada_asegurar, s["datos"]["serie"], num)
    except Exception as ex:
        return await e.respond(f"No pude crear la temporada: {ex}\nEscribe otro numero, o /cancel.")
    s["datos"]["temporada"], s["nombres"]["temporada"] = tid, f"Temporada {num}"
    await e.respond(f"✅ Temporada {num} creada." if creada else f"La Temporada {num} ya existia; la uso.")
    if s.get("modo") == "temporada":   # /temporada: solo crear, no hay video que subir
        limpiar(e.sender_id)
        return await e.respond(f"{MASCOTA} Lista. Para subir un capitulo: mandame el video y elige la tipologia Serie.")
    await siguiente_paso(e, s)

TXT_TIPOLOGIA = f"{MASCOTA} **Tipología**\nElige qué tipo de contenido es."
TXT_TIPOLOGIA_AVISO = (" Las marcadas con \u26a0\ufe0f pueden pedir campos extra en Picta "
                       "y fallar al crear la publicacion.")

MODELOS_PROBADOS = ("categoria", "pelicula")   # "categoria" = mismo formulario que Audiovisual

def es_basica(t):
    return t.get("modelo") in MODELOS_PROBADOS or t.get("id") == 5   # probadas (sin aviso en el menu)

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
                    + "\n\nSe eligen al subir un video. Para agregar mas, edita PALABRAS_PRESET en bot.py.")

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
        await e.respond(f"{MASCOTA} **Portada**\nMándame la imagen como foto.")
    else:
        p = PALABRAS_PRESET[int(dato)]
        if p in s["kw"]: s["kw"].remove(p)
        else: s["kw"].append(p)
        await e.edit(TXT_PALABRAS, buttons=teclado_palabras(s))

async def iniciar_subida(uid, s, cls):
    """Sube el video a Picta y va avisando del progreso. La usan el modo normal y el automatico."""
    msg = await client.send_message(uid, f"{MASCOTA} **Preparando la subida…**")
    estado = {}
    try:
        tarea = asyncio.create_task(asyncio.to_thread(
            picta_subir, s["video"], s["cover"], s["titulo"], s["descripcion"], s["palabras"], cls, estado, s.get("tipologia", int(TIPOLOGIA)), extra_campos(s),
            s["cover"] if s.get("tipologia") == 1 else None, s.get("publicado", "true")))
        ultimo_txt, avisado, ultimo_aviso = "", False, None
        prev_t, prev_b = time.time(), 0
        while not tarea.done():
            await asyncio.sleep(5)
            if estado.get("aviso") and estado["aviso"] != ultimo_aviso:
                ultimo_aviso = estado["aviso"]
                prev_t, prev_b, avisado = time.time(), 0, False
                await client.send_message(uid, "🔁 " + ultimo_aviso)
            fase = estado.get("fase", "login")
            if fase == "login":
                txt = f"{MASCOTA} **Iniciando sesión en Picta…**"
            elif fase == "validando":
                txt = f"{MASCOTA} **Validando los datos…**\nTodavía no he empezado a subir el video."
            elif fase == "subiendo":
                env, tot = estado["enviado"], max(estado["total"], 1)
                ahora = time.time()
                vel = env / max(ahora - estado["t_inicio"], 1) / 1048576             # promedio desde el inicio
                vel_ahora = max(env - prev_b, 0) / max(ahora - prev_t, 1) / 1048576  # ultimos segundos
                prev_t, prev_b = ahora, env
                pct = env * 100 // tot
                intento = f" · intento {estado['intento']}/{INTENTOS_SUBIDA}" if estado.get("intento", 1) > 1 else ""
                resta = f"\nFaltan unos {_dur((tot - env) / 1048576 / vel)}" if vel > 0.05 and env > 0 else ""
                tope = f" · límite {VEL_MAX:g}" if VEL_MAX > 0 else ""
                txt = (f"{MASCOTA} **Subiendo a Picta**{intento}\n"
                       f"{barra(pct)} {pct}%\n\n"
                       f"{env // 1048576} / {tot // 1048576} MB\n"
                       f"{vel_ahora:.1f} MB/s{tope}" + resta)
                parado = time.time() - estado["t_ultimo"]
                if parado > 45:
                    txt += f"\n⚠️ Sin avance desde hace {int(parado)} s"
                    if not avisado:
                        avisado = True
                        await client.send_message(uid,
                            f"⚠️ La subida parece detenida. Si no avanza en {SIN_AVANCE_MAX // 60} minutos se dará por cortada y se reintentará.")
                else:
                    avisado = False
            elif fase == "reintentando":
                txt = f"{MASCOTA} **Preparando el reintento…**"
            else:
                txt = f"{MASCOTA} **Publicando en Picta…**\n{barra(100)} 100%"
            if txt != ultimo_txt:
                ultimo_txt = txt
                try:
                    await msg.edit(txt)
                except Exception:
                    pass
        res = await tarea
        slug = res.get("slug_url", "")
        url = f"https://www.picta.cu/medias/{slug}"
        await client.send_message(uid,
            f"{MASCOTA} ¡Listo, ya está en Picta!\n{barra(100)} 100%\n\n{s['titulo']}",
            buttons=[[Button.url("🔗 Abrir en Picta", url)]], parse_mode=None)
    except Exception as ex:
        await client.send_message(uid, f"{MASCOTA} Algo salió mal al subir ({type(ex).__name__})\n\n{ex}", parse_mode=None)
    finally:
        limpiar(uid)

async def lanzar_auto(e, s):
    """Modo automatico: con la portada recibida, usa los datos ya resueltos y empieza la subida."""
    a = s["auto"]
    s["palabras"], s["tipologia"] = a["palabras"], a["tipologia"]
    if a["datos"]:
        s["datos"], s["nombres"] = dict(a["datos"]), dict(a["nombres"])
    s["step"] = "subiendo"
    await e.respond(f"{MASCOTA} Todo listo en automático. Voy a subirlo, puede tardar un rato.")
    await iniciar_subida(e.sender_id, s, a["clasificacion"])

@client.on(events.CallbackQuery(pattern=rb"vis:(true|false)"))
async def visibilidad_cb(e):
    if e.sender_id != ALLOWED: return
    s = sessions.get(e.sender_id)
    if not s or s["step"] != "s_visible": return
    v = e.pattern_match.group(1).decode()
    s["visible"], s["step"] = v, "s_portada"
    await e.edit("Visibilidad: " + ("visible" if v == "true" else "oculta"))
    await e.respond(f"{MASCOTA} **Poster de la serie**\nMandame la imagen como foto.")

@client.on(events.CallbackQuery(pattern=rb"cls:(.+)"))
async def clasificacion(e):
    if e.sender_id != ALLOWED: return
    s = sessions.get(e.sender_id)
    if not s or s["step"] != "clasificacion": return
    cls = e.pattern_match.group(1).decode()
    if s.get("modo") == "serie":
        s["clasificacion"], s["step"] = cls, "s_visible"
        await e.edit(f"Clasificación: {cls}")
        return await e.respond(f"{MASCOTA} **Visibilidad**\nLa serie nace visible u oculta?",
                               buttons=[[Button.inline("👁 Visible", b"vis:true"),
                                         Button.inline("🙈 Oculta", b"vis:false")]])
    s["cls"], s["step"] = cls, "v_publicar"
    await e.edit(f"Clasificación: {cls}")
    await e.respond(f"{MASCOTA} **Publicación**\nLo publico ya o lo dejo oculto?",
                    buttons=[[Button.inline("🌐 Publicar", b"pub:true"),
                              Button.inline("🙈 Oculto", b"pub:false")]])

@client.on(events.CallbackQuery(pattern=rb"pub:(true|false)"))
async def publicar_cb(e):
    if e.sender_id != ALLOWED: return
    s = sessions.get(e.sender_id)
    if not s or s["step"] != "v_publicar": return
    v = e.pattern_match.group(1).decode()
    s["publicado"], s["step"] = v, "subiendo"
    await e.edit("Publicación: " + ("publicado" if v == "true" else "oculto"))
    await iniciar_subida(e.sender_id, s, s["cls"])

# ---------------------------------------------------------------------------------------------
# /panel: estadisticas del canal (solo lectura). Usa el mismo inicio de sesion que la subida.
# ---------------------------------------------------------------------------------------------
from datetime import datetime, timezone, timedelta
try:
    from zoneinfo import ZoneInfo
    TZ_CUBA = ZoneInfo("America/Havana")
except Exception:
    TZ_CUBA = timezone(timedelta(hours=-5))

PANEL_POR_PAGINA = 6
PANEL_CACHE_SEG = 90
ORDENES = {   # clave -> (etiqueta, funcion de orden)
    "recientes": ("\U0001F552 Recientes", lambda v: v["ts"]),
    "vistas":    ("\U0001F440 Vistas",    lambda v: v["vistas"]),
    "gustados":  ("\u2764\ufe0f Me gusta", lambda v: v["likes"]),
}
_PANEL = {"datos": None, "t": 0.0}

ADMIN_HDR = {"Origin": "https://admin.picta.cu", "Referer": "https://admin.picta.cu/publicaciones",
             "Accept": "application/json, text/plain, */*",
             "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36"}

def picta_publicaciones(token, limite=100):
    """Todas las publicaciones del canal. Pide la pagina 1 y, si la API dice cuantas hay ('count'),
    baja el resto de paginas EN PARALELO. Si se pasa de 'limite' segundos devuelve lo que ya tenga."""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    h = {"Authorization": f"Bearer {token}", **ADMIN_HDR}
    url, t0, TAM = f"{API}/v2/publicacion/", time.time(), 50

    def pedir(page):
        t = time.time()
        # mismos parametros que el panel de admin de Picta; sin filtro de canal (la lista ya es la tuya)
        r = requests.get(url, params={"tipo__in": "", "nombre__contains": "", "tipologia_nombre_raw": "",
                                      "page_size": TAM, "page": page, "ordering": "-fecha_creacion"},
                         headers=h, timeout=(15, 45))
        r.raise_for_status()
        print(f"Panel: pagina {page} en {time.time() - t:.1f}s", flush=True)
        return r.json()

    j = pedir(1)
    out = list(j.get("results", []))
    total = j.get("count")
    if isinstance(total, int) and total > 1500:
        raise RuntimeError(f"Picta devolvio el catalogo completo ({total} videos), no solo los de tu canal. "
                           "La sesion del bot no es la del canal: revisa PICTA_USER y PICTA_PASS.")
    if isinstance(total, int) and total > len(out):
        paginas = list(range(2, -(-total // TAM) + 1))
        res = {}
        ex = ThreadPoolExecutor(max_workers=4)
        futs = {ex.submit(pedir, pg): pg for pg in paginas}
        try:
            for f in as_completed(futs, timeout=max(5, limite - (time.time() - t0))):
                try:
                    res[futs[f]] = f.result().get("results", [])
                except Exception as err:
                    print("Panel: fallo pagina", futs[f], type(err).__name__, err, flush=True)
        except Exception as err:
            print("Panel: tiempo agotado, uso lo descargado:", type(err).__name__, flush=True)
        ex.shutdown(wait=False, cancel_futures=True)
        for pg in sorted(res):
            out += res[pg]
    else:
        page, sig = 1, j.get("next")
        while sig and time.time() - t0 < limite:
            page = sig if isinstance(sig, int) else page + 1
            j = pedir(page)
            out += j.get("results", [])
            sig = j.get("next")
    print(f"Panel: {len(out)} publicaciones en {time.time() - t0:.1f}s", flush=True)
    return out

def _fecha(txt):
    try:
        return datetime.fromisoformat(txt)
    except Exception:
        return None

def _n(x):
    try:
        return int(x or 0)
    except Exception:
        return 0

def normalizar_pub(p):
    f = _fecha(p.get("fecha_publicado") or p.get("fecha_creacion") or "")
    canal = p.get("canal") or {}
    return {
        "id": p.get("id"), "nombre": p.get("nombre") or "(sin titulo)", "slug": p.get("slug_url") or "",
        "fecha": f, "ts": f.timestamp() if f else 0.0,
        "publicado": bool(p.get("publicado")), "eliminado": bool(p.get("eliminado")),
        "duracion": p.get("duracion") or "", "descripcion": (p.get("descripcion") or "").strip(),
        "vistas": _n(p.get("cantidad_visitas")), "repro": _n(p.get("cantidad_reproducciones")),
        "likes": _n(p.get("cantidad_me_gusta")), "dislikes": _n(p.get("cantidad_no_me_gusta")),
        "descargas": _n(p.get("cantidad_descargas")), "comentarios": _n(p.get("cantidad_comentarios")),
        "convertido": bool(p.get("convertido")), "hd": bool(p.get("hd")),
        "subs": bool(p.get("subtitulos") or p.get("url_subtitulo")),
        "canal_id": canal.get("id"), "canal_nombre": canal.get("nombre"),
    }

def preparar_panel(crudos):
    """Normaliza, quita eliminados y deja solo los del canal configurado (si la API dice de que canal son)."""
    vids = [normalizar_pub(p) for p in crudos]
    n_api = len(vids)
    vids = [v for v in vids if not v["eliminado"]]
    canales = sorted({str(v["canal_id"]) for v in vids if v["canal_id"] is not None})
    propios = [v for v in vids if v["canal_id"] is None or str(v["canal_id"]) == str(CANAL_ID)]
    if not propios and vids and len(canales) == 1:
        propios = vids          # todos son de un unico canal (el tuyo): se usa ese
    _PANEL["diag"] = f"La API devolvio {n_api} publicaciones ({len(vids)} sin eliminar). Canales vistos: {', '.join(canales) or 'ninguno'}. Canal configurado: {CANAL_ID}."
    print("Panel:", _PANEL["diag"], flush=True)
    return propios

def _cortar(t, n):
    t = " ".join(t.split())
    return t if len(t) <= n else t[:n - 1].rstrip() + "\u2026"

def _fmt_fecha(dt):
    return dt.astimezone(TZ_CUBA).strftime("%d/%m/%Y %H:%M") if dt else "\u2014"

def ordenar_panel(vids, orden):
    clave = ORDENES.get(orden, ORDENES["recientes"])[1]
    return sorted(vids, key=clave, reverse=True)

def total_paginas(vids):
    return max(1, -(-len(vids) // PANEL_POR_PAGINA))


def panel_texto(vids, orden, pag):
    if not vids:
        return f"{MASCOTA} Panel de Picta\n\nNo encontré videos en tu canal.\n\n{_PANEL.get('diag', '')}"
    pub = [v for v in vids if v["publicado"]]
    hoy = datetime.now(TZ_CUBA).date()
    hoy_n = sum(1 for v in pub if v["fecha"] and v["fecha"].astimezone(TZ_CUBA).date() == hoy)
    suma = lambda k: sum(v[k] for v in vids)
    masv = max(vids, key=lambda v: v["vistas"])
    masg = max(vids, key=lambda v: v["likes"])
    nombre = next((v["canal_nombre"] for v in vids if v["canal_nombre"]), None) or f"Canal {CANAL_ID}"
    sin_pub = f" (+{len(vids) - len(pub)} sin publicar)" if len(vids) != len(pub) else ""
    paginas = total_paginas(vids)
    pag = min(max(pag, 1), paginas)
    ordenados = ordenar_panel(vids, orden)
    ini = (pag - 1) * PANEL_POR_PAGINA
    lineas = [
        f"{MASCOTA} Panel · {nombre}",
        LINEA,
        f"{len(pub)} videos{sin_pub} · {hoy_n} subidos hoy",
        f"👀 {suma('vistas'):,} vistas · ▶️ {suma('repro'):,} reproducciones",
        f"❤️ {suma('likes'):,} me gusta · 📥 {suma('descargas'):,} descargas · 💬 {suma('comentarios'):,}",
        LINEA,
    ]
    if masv["vistas"]:
        lineas.append(f"Más visto · {_cortar(masv['nombre'], 40)} ({masv['vistas']:,})")
    if masg["likes"]:
        lineas.append(f"Más gustado · {_cortar(masg['nombre'], 40)} ({masg['likes']:,})")
    if masv["vistas"] or masg["likes"]:
        lineas.append(LINEA)
    lineas += [f"Orden: {ORDENES.get(orden, ORDENES['recientes'])[0]} · pág. {pag}/{paginas}", ""]
    for i, v in enumerate(ordenados[ini:ini + PANEL_POR_PAGINA], start=ini + 1):
        lineas.append(f"{i}. {_cortar(v['nombre'], 60)}" + ("" if v["publicado"] else "  🔒"))
        lineas.append(f"    👀 {v['vistas']:,} · ❤️ {v['likes']:,} · 📥 {v['descargas']:,} · 💬 {v['comentarios']:,}")
        lineas.append("")
    lineas.append("Toca un número para ver la ficha del video.")
    return "\n".join(lineas)

def panel_botones(vids, orden, pag):
    paginas = total_paginas(vids)
    pag = min(max(pag, 1), paginas)
    ordenados = ordenar_panel(vids, orden)
    ini = (pag - 1) * PANEL_POR_PAGINA
    nums = [Button.inline(str(i), f"pn:v:{v['id']}:{orden}:{pag}".encode())
            for i, v in enumerate(ordenados[ini:ini + PANEL_POR_PAGINA], start=ini + 1)]
    filas = [nums[i:i + 3] for i in range(0, len(nums), 3)]
    if paginas > 1:
        nav = []
        if pag > 1: nav.append(Button.inline("\u25c0\ufe0f", f"pn:l:{orden}:{pag - 1}".encode()))
        nav.append(Button.inline(f"{pag}/{paginas}", b"pn:n"))
        if pag < paginas: nav.append(Button.inline("\u25b6\ufe0f", f"pn:l:{orden}:{pag + 1}".encode()))
        filas.append(nav)
    filas.append([Button.inline(("\u2705 " if k == orden else "") + etiqueta, f"pn:l:{k}:1".encode())
                  for k, (etiqueta, _) in ORDENES.items()])
    filas.append([Button.inline("\U0001F504 Actualizar", f"pn:r:{orden}:{pag}".encode())])
    return filas


def ficha_texto(v):
    estado = "convertido" if v["convertido"] else "procesando ⏳"
    desc = _cortar(v["descripcion"], 600) if v["descripcion"] else "Sin descripción"
    dur = v["duracion"] or "—"
    hd = "HD" if v["hd"] else "SD"
    subs = "con subtítulos" if v["subs"] else "sin subtítulos"
    return "\n".join([
        f"{MASCOTA} {v['nombre']}",
        LINEA,
        f"Publicado · {_fmt_fecha(v['fecha'])}" + ("" if v["publicado"] else "  🔒 sin publicar"),
        f"Duración · {dur} · {hd} · {estado} · {subs}",
        f"ID · {v['id']}",
        LINEA,
        f"👀 {v['vistas']:,} vistas · ▶️ {v['repro']:,} reproducciones",
        f"❤️ {v['likes']:,} me gusta · 👎 {v['dislikes']:,}",
        f"📥 {v['descargas']:,} descargas · 💬 {v['comentarios']:,} " + ("comentario" if v["comentarios"] == 1 else "comentarios"),
        LINEA,
        desc,
    ])

async def _datos_panel(forzar=False):
    if not forzar and _PANEL["datos"] is not None and time.time() - _PANEL["t"] < PANEL_CACHE_SEG:
        return _PANEL["datos"]
    try:
        token = await asyncio.wait_for(asyncio.to_thread(picta_token), timeout=90)
        crudos = await asyncio.wait_for(asyncio.to_thread(picta_publicaciones, token), timeout=240)
    except Exception:
        if _PANEL["datos"] is not None:      # si ya habia datos, enseno esos antes que fallar
            return _PANEL["datos"]
        raise
    _PANEL["datos"], _PANEL["t"] = preparar_panel(crudos), time.time()
    return _PANEL["datos"]

async def _editar(e, texto, botones):
    try:
        await e.edit(texto, buttons=botones, parse_mode=None)
    except Exception as ex:
        if "modified" not in str(ex).lower():   # Telegram avisa si el texto no cambio: se ignora
            raise

# ---------------------------------------------------------------------------------------------
# Tarjetas de imagen para /panel y la ficha de cada video (necesita Pillow: pip install Pillow).
# Si Pillow no esta instalado, el bot sigue funcionando con los textos de siempre.
# ---------------------------------------------------------------------------------------------
import io
try:
    from PIL import Image, ImageDraw, ImageFont
    TARJETAS = True
except ImportError:
    TARJETAS = False
    print("Aviso: no esta Pillow (pip install Pillow); el panel se mostrara solo con texto.", flush=True)

C_FONDO, C_BLANCO, C_BORDE = "#FBF8F3", "#FFFFFF", "#EAE3D9"
C_TEXTO, C_SUAVE = "#1F2328", "#7A7F87"
C_NARANJA, C_NARANJA_OSC, C_PISTA, C_CHIP = "#F28C28", "#C8651B", "#F1EBE2", "#F6EFE5"

_FUENTES = {}
_RUTAS_FUENTE = {
    False: ["DejaVuSans.ttf", "LiberationSans-Regular.ttf", "NotoSans-Regular.ttf", "Arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/dejavu/DejaVuSans.ttf"],
    True:  ["DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf", "NotoSans-Bold.ttf", "Arialbd.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf"],
}

def _fuente(tam, negrita=False):
    clave = (tam, negrita)
    if clave not in _FUENTES:
        rutas = ([os.environ["FUENTE_TARJETAS"]] if os.environ.get("FUENTE_TARJETAS") else []) + _RUTAS_FUENTE[negrita]
        f = None
        for r in rutas:
            try:
                f = ImageFont.truetype(r, tam)
                break
            except Exception:
                continue
        if f is None:
            try:
                f = ImageFont.load_default(tam)
            except Exception:
                f = ImageFont.load_default()
        _FUENTES[clave] = f
    return _FUENTES[clave]

class _Lienzo:
    """Dibuja al doble de tamano y reduce al final, para que los bordes salgan suaves."""
    S = 2

    def __init__(self, w, h, fondo=C_FONDO):
        self.w, self.h = w, h
        self.img = Image.new("RGB", (w * self.S, h * self.S), fondo)
        self.d = ImageDraw.Draw(self.img)

    def _s(self, v):
        return int(round(v * self.S))

    def rect(self, x0, y0, x1, y1, r=0, fill=None, borde=None, grosor=2):
        self.d.rounded_rectangle([self._s(x0), self._s(y0), self._s(x1), self._s(y1)], radius=self._s(r),
                                 fill=fill, outline=borde, width=self._s(grosor) if borde else 0)

    def poly(self, pts, fill):
        self.d.polygon([(self._s(x), self._s(y)) for x, y in pts], fill=fill)

    def elipse(self, cx, cy, rx, ry, fill):
        self.d.ellipse([self._s(cx - rx), self._s(cy - ry), self._s(cx + rx), self._s(cy + ry)], fill=fill)

    def texto(self, x, y, t, tam, color=C_TEXTO, negrita=False):
        self.d.text((self._s(x), self._s(y)), t, font=_fuente(self._s(tam), negrita), fill=color)

    def medir(self, t, tam, negrita=False):
        return _fuente(self._s(tam), negrita).getlength(t) / self.S

    def png(self):
        img = self.img.resize((self.w, self.h), Image.LANCZOS)
        b = io.BytesIO()
        img.save(b, "PNG", optimize=True)
        return b.getvalue()

def _zorro(L, x, y, tam):
    """La mascota (Fito) dibujada con formas simples. Rejilla de 100 x 100."""
    k = tam / 100.0
    P = lambda pts: [(x + a * k, y + b * k) for a, b in pts]
    L.poly(P([(8, 8), (36, 30), (64, 30), (92, 8), (95, 54), (50, 94), (5, 54)]), C_NARANJA)       # cabeza y orejas
    L.poly(P([(15, 19), (31, 33), (16, 42)]), C_NARANJA_OSC)                                        # oreja izquierda
    L.poly(P([(85, 19), (69, 33), (84, 42)]), C_NARANJA_OSC)                                        # oreja derecha
    L.poly(P([(5, 54), (30, 58), (50, 68), (70, 58), (95, 54), (50, 94)]), "#FFF0DC")              # mejillas y hocico
    L.elipse(x + 33 * k, y + 47 * k, 4.5 * k, 5.5 * k, C_TEXTO)                                     # ojos
    L.elipse(x + 67 * k, y + 47 * k, 4.5 * k, 5.5 * k, C_TEXTO)
    L.poly(P([(43, 79), (57, 79), (50, 89)]), C_TEXTO)                                              # nariz

def _compacto(n):
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M".replace(".0M", "M")
    if n >= 10_000:
        return f"{n / 1000:.1f}K".replace(".0K", "K")
    return f"{n:,}"

def _recortar(L, t, tam, negrita, ancho):
    if L.medir(t, tam, negrita) <= ancho:
        return t
    while t and L.medir(t + "…", tam, negrita) > ancho:
        t = t[:-1]
    return t.rstrip() + "…"

def _ajustar(L, texto, tam, negrita, ancho, max_lineas):
    """Parte el texto en lineas que caben en 'ancho'; si sobran, la ultima termina en ..."""
    lineas, actual = [], ""
    for p in texto.split():
        prueba = (actual + " " + p).strip()
        if actual and L.medir(prueba, tam, negrita) > ancho:
            lineas.append(actual)
            actual = p
        else:
            actual = prueba
    if actual:
        lineas.append(actual)
    if len(lineas) > max_lineas:
        lineas = lineas[:max_lineas]
        lineas[-1] = lineas[-1].rstrip("….") + "…"
    return [_recortar(L, l, tam, negrita, ancho) for l in lineas] or [""]

def _casillas(L, y0, datos, M=56, gap=24, alto=150):
    """Cuadricula de 3 columnas con numero grande y etiqueta. Devuelve la 'y' donde termina."""
    ancho = (L.w - 2 * M - 2 * gap) // 3
    for i, (etiqueta, valor) in enumerate(datos):
        x0, y = M + (i % 3) * (ancho + gap), y0 + (i // 3) * (alto + gap)
        L.rect(x0, y, x0 + ancho, y + alto, r=24, fill=C_BLANCO, borde=C_BORDE)
        L.texto(x0 + 26, y + 22, etiqueta, 26, C_SUAVE)
        L.texto(x0 + 26, y + 62, valor, 56, C_TEXTO, True)
        L.rect(x0 + 26, y + alto - 24, x0 + 62, y + alto - 18, r=3, fill=C_NARANJA)
    filas = -(-len(datos) // 3)
    return y0 + filas * alto + (filas - 1) * gap

def _pie(L, y):
    ahora = datetime.now(TZ_CUBA).strftime("%d/%m/%Y %H:%M")
    L.texto(56, y, f"{NOMBRE_BOT} · actualizado {ahora}", 24, C_SUAVE)

def tarjeta_panel(vids):
    """Imagen resumen del canal. Devuelve los bytes de un PNG."""
    pub = [v for v in vids if v["publicado"]]
    suma = lambda k: sum(v[k] for v in vids)
    nombre = next((v["canal_nombre"] for v in vids if v["canal_nombre"]), None) or f"Canal {CANAL_ID}"
    top = [v for v in sorted(vids, key=lambda v: v["vistas"], reverse=True)[:5] if v["vistas"] > 0]
    W, M = 1080, 56
    H = 210 + 2 * 150 + 24 + (80 + len(top) * 78 + 20 if top else 0) + 100
    L = _Lienzo(W, H)
    _zorro(L, M, 48, 92)
    L.texto(M + 120, 54, "Panel de Picta", 46, C_TEXTO, True)
    L.texto(M + 120, 114, _recortar(L, nombre, 28, False, W - 2 * M - 120), 28, C_SUAVE)
    y = _casillas(L, 192, [
        ("Videos", _compacto(len(pub))), ("Vistas", _compacto(suma("vistas"))), ("Reproducciones", _compacto(suma("repro"))),
        ("Me gusta", _compacto(suma("likes"))), ("Descargas", _compacto(suma("descargas"))), ("Comentarios", _compacto(suma("comentarios"))),
    ])
    y += 54
    if top:
        L.texto(M, y, "Más vistos", 34, C_TEXTO, True)
        y += 62
        mayor = max(v["vistas"] for v in top)
        for v in top:
            val = _compacto(v["vistas"])
            L.texto(W - M - L.medir(val, 28, True), y, val, 28, C_SUAVE, True)
            L.texto(M, y, _recortar(L, " ".join(v["nombre"].split()), 28, False, W - 2 * M - 130), 28, C_TEXTO)
            L.rect(M, y + 42, W - M, y + 54, r=6, fill=C_PISTA)
            L.rect(M, y + 42, M + max(14, (W - 2 * M) * v["vistas"] / mayor), y + 54, r=6, fill=C_NARANJA)
            y += 78
        y += 6
    _pie(L, y + 14)
    return L.png()

def tarjeta_ficha(v):
    """Imagen con la ficha de un video. Devuelve los bytes de un PNG."""
    W, M = 1080, 56
    L = _Lienzo(W, 1000)
    _zorro(L, M, 44, 64)
    L.texto(M + 90, 56, "Ficha del video", 28, C_SUAVE)
    L.texto(M + 90, 90, f"ID {v['id']}", 24, C_SUAVE)
    y = 150
    for linea in _ajustar(L, v["nombre"], 50, True, W - 2 * M, 3):
        L.texto(M, y, linea, 50, C_TEXTO, True)
        y += 64
    y += 14
    chips = [_fmt_fecha(v["fecha"]).split(" ")[0] if v["fecha"] else "—", v["duracion"] or "—",
             "HD" if v["hd"] else "SD", "Convertido" if v["convertido"] else "Procesando"]
    if not v["publicado"]:
        chips.append("Sin publicar")
    x = M
    for c in chips:
        w = L.medir(c, 26) + 40
        if x + w > W - M:
            x, y = M, y + 60
        L.rect(x, y, x + w, y + 48, r=24, fill=C_CHIP)
        L.texto(x + 20, y + 8, c, 26, C_NARANJA_OSC)
        x += w + 14
    y += 48 + 34
    y = _casillas(L, y, [
        ("Vistas", _compacto(v["vistas"])), ("Reproducciones", _compacto(v["repro"])), ("Me gusta", _compacto(v["likes"])),
        ("No me gusta", _compacto(v["dislikes"])), ("Descargas", _compacto(v["descargas"])), ("Comentarios", _compacto(v["comentarios"])),
    ]) + 44
    votos = v["likes"] + v["dislikes"]
    if votos:
        pct = round(v["likes"] * 100 / votos)
        L.texto(M, y, "Aprobación", 28, C_SUAVE)
        txt = f"{pct}%"
        L.texto(W - M - L.medir(txt, 28, True), y, txt, 28, C_TEXTO, True)
        L.rect(M, y + 46, W - M, y + 60, r=7, fill=C_PISTA)
        L.rect(M, y + 46, M + max(14, (W - 2 * M) * pct / 100), y + 60, r=7, fill=C_NARANJA)
        y += 84
    _pie(L, y + 6)
    L.h = int(y + 6 + 24 + 44)
    L.img = L.img.crop((0, 0, L.w * L.S, L.h * L.S))
    return L.png()

def _cap(t, n=1024):
    """Telegram limita el texto bajo una foto a 1024 caracteres."""
    return t if len(t) <= n else t[:n - 1].rstrip() + "…"

def panel_caption(vids, orden, pag):
    paginas = total_paginas(vids)
    pag = min(max(pag, 1), paginas)
    ordenados = ordenar_panel(vids, orden)
    ini = (pag - 1) * PANEL_POR_PAGINA
    suma = lambda k: sum(v[k] for v in vids)
    lineas = [f"📊 Totales · {len(vids)} videos", f"👀 {suma('vistas'):,} vistas · ▶️ {suma('repro'):,} reproducciones",
              f"❤️ {suma('likes'):,} me gusta · 📥 {suma('descargas'):,} descargas · 💬 {suma('comentarios'):,}", "",
              f"{ORDENES.get(orden, ORDENES['recientes'])[0]} · pág. {pag}/{paginas}", ""]
    for i, v in enumerate(ordenados[ini:ini + PANEL_POR_PAGINA], start=ini + 1):
        lineas.append(f"{i}. {_cortar(v['nombre'], 42)}" + ("" if v["publicado"] else " 🔒"))
        lineas.append(f"    👀 {v['vistas']:,} · ❤️ {v['likes']:,} · 📥 {v['descargas']:,} · 💬 {v['comentarios']:,}")
    lineas += ["", "Toca un número para ver la ficha."]
    return _cap("\n".join(lineas))

def ficha_caption(v):
    desc = _cortar(v["descripcion"], 380) if v["descripcion"] else "Sin descripción"
    return _cap(f"{desc}")

def _bio(png, nombre):
    b = io.BytesIO(png)
    b.name = nombre
    return b

def _png_panel(vids):
    """La tarjeta del panel se guarda mientras los datos no se actualicen."""
    if _PANEL.get("img") is None or _PANEL.get("img_t") != _PANEL["t"]:
        _PANEL["img"], _PANEL["img_t"] = tarjeta_panel(vids), _PANEL["t"]
    return _PANEL["img"]

_VISTA = {}   # id de mensaje -> "panel" o "ficha" (solo los mensajes que llevan tarjeta)

async def _mostrar(e, vista, caption, texto, botones, hacer_png, forzar=False):
    """Pone en el mensaje la vista pedida. Devuelve None si salio bien, o un texto de error."""
    mid = e.query.msg_id
    try:
        if mid in _VISTA:    # mensaje con tarjeta: se cambia la foto solo si hace falta
            if forzar or vista == "ficha" or _VISTA[mid] != vista:
                png = await asyncio.to_thread(hacer_png)
                await e.edit(caption, file=_bio(png, f"{vista}.png"), buttons=botones, parse_mode=None)
            else:
                await e.edit(caption, buttons=botones, parse_mode=None)
            _VISTA[mid] = vista
        else:                # mensaje de solo texto (sin Pillow, o de antes de reiniciar)
            await e.edit(texto, buttons=botones, parse_mode=None)
    except Exception as ex:
        if "modified" in str(ex).lower():   # Telegram avisa si nada cambio: se ignora
            return None
        print("Panel:", type(ex).__name__, ex, flush=True)
        return "No pude actualizar el panel. Escribe /panel otra vez."
    return None

@client.on(events.NewMessage(pattern=r"^/canal\b"))
async def canal_cmd(e):
    """Ayuda para descubrir el id del canal: muestra lo que Picta responde."""
    if not autorizado(e): return
    msg = await e.respond("Buscando el id de tu canal en Picta…", parse_mode=None)
    import re as _re
    _m = _re.search(r"\d+", e.raw_text or "")
    pub_id = _m.group(0) if _m else None
    def consultar():
        token = picta_token()
        h = {"Authorization": f"Bearer {token}"}
        lineas = []
        if pub_id:   # /canal 63644 -> datos de esa publicacion (a que canal pertenece, si esta publicada)
            for ruta in (f"/v2/publicacion/{pub_id}/", f"/v1/publicacion/{pub_id}/"):
                try:
                    r = requests.get(f"{API}{ruta}", headers=h, timeout=30)
                    try:
                        j = r.json()
                        cn = j.get("canal") or {}
                        txt = (f"nombre={j.get('nombre')} canal={cn.get('id')} ({cn.get('nombre')}) "
                               f"publicado={j.get('publicado')} eliminado={j.get('eliminado')} convertido={j.get('convertido')}")
                    except Exception:
                        txt = " ".join(r.text.split())[:200]
                    lineas.append(f"{ruta} -> {r.status_code}: {txt}")
                except Exception as ex:
                    lineas.append(f"{ruta} -> {type(ex).__name__}")
        lineas.append(f"Usuario del bot: {PICTA_USER}")
        pruebas = [("/v2/publicacion/", {}, False), ("/v2/publicacion/", {}, True)]
        for ruta, extra, con_admin in pruebas:
            extra = {**extra, "_cabeceras_admin": con_admin}
            try:
                hh = {**h, **ADMIN_HDR} if con_admin else h
                r = requests.get(f"{API}{ruta}", params={"page_size": 5}, headers=hh, timeout=30)
                try:
                    j = r.json()
                    nombres = [x.get("nombre") for x in j.get("results", [])][:3]
                    txt = f"count={j.get('count')} ejemplos={nombres}"
                except Exception:
                    txt = " ".join(r.text.split())[:200]
                lineas.append(f"{ruta} {extra or ''} -> {r.status_code}: {txt}")
            except Exception as ex:
                lineas.append(f"{ruta} -> {type(ex).__name__}")
        # canales que aparecen en los comentarios recibidos: ahi se ve el id real de tu canal
        try:
            hoy = datetime.now(TZ_CUBA).date()
            r = requests.get(f"{API}/v2/comentario/", params={
                "fecha__gte": (hoy - timedelta(days=60)).isoformat(),
                "fecha__lt": (hoy + timedelta(days=2)).isoformat(), "page_size": 50}, headers=h, timeout=45)
            vistos = {}
            for c in r.json().get("results", []):
                pub = c.get("publicacion") or {}
                cn = pub.get("canal") or {}
                clave = (cn.get("id"), cn.get("nombre"))
                vistos.setdefault(clave, set()).add(pub.get("nombre"))
            if vistos:
                lineas.append("Canales en tus comentarios:\n" + "\n".join(
                    f"- id {k[0]} ({k[1]}): {', '.join(str(x) for x in list(v)[:3])}" for k, v in vistos.items()))
            else:
                lineas.append(f"Comentarios: {r.status_code}, ninguno en 60 dias")
        except Exception as ex:
            lineas.append(f"Comentarios -> {type(ex).__name__}")
        return "\n\n".join(lineas)
    try:
        out = await asyncio.wait_for(asyncio.to_thread(consultar), timeout=150)
    except Exception as ex:
        return await msg.edit(f"No pude consultar Picta ({type(ex).__name__}): {ex or 'tardó demasiado'}", parse_mode=None)
    print("Canal:", out, flush=True)
    await msg.edit(out[:3900], parse_mode=None)

@client.on(events.NewMessage(pattern=r"^/panel\b"))
async def panel_cmd(e):
    if not autorizado(e): return
    msg = await e.respond(f"{MASCOTA} Consultando tu canal en Picta…", parse_mode=None)
    try:
        vids = await _datos_panel(forzar=True)
    except Exception as ex:
        return await msg.edit(f"No pude consultar Picta ({type(ex).__name__}): {ex or 'Picta tardó demasiado en responder'}", parse_mode=None)
    if TARJETAS and vids:
        try:
            png = await asyncio.to_thread(_png_panel, vids)
            m = await client.send_file(e.chat_id, _bio(png, "panel.png"), caption=panel_caption(vids, "recientes", 1),
                                       buttons=panel_botones(vids, "recientes", 1), parse_mode=None)
            _VISTA[m.id] = "panel"
        except Exception as ex:
            print("Tarjeta del panel:", type(ex).__name__, ex, flush=True)
        else:
            try:
                await msg.delete()
            except Exception:
                pass
            return
    await msg.edit(panel_texto(vids, "recientes", 1), buttons=panel_botones(vids, "recientes", 1), parse_mode=None)

@client.on(events.CallbackQuery(pattern=rb"pn:(.+)"))
async def panel_cb(e):
    if e.sender_id != ALLOWED: return
    partes = e.pattern_match.group(1).decode().split(":")
    acc = partes[0]
    if acc == "n":
        return await e.answer()
    try:
        if acc == "v":
            vid, orden, pag = int(partes[1]), partes[2], int(partes[3])
        else:
            orden, pag = partes[1], int(partes[2])
    except (IndexError, ValueError):
        return await e.answer("Boton no valido.", alert=True)
    if orden not in ORDENES:
        orden = "recientes"
    try:
        vids = await _datos_panel(forzar=(acc == "r"))
    except Exception as ex:
        return await e.answer(f"No pude consultar Picta ({type(ex).__name__}).", alert=True)
    if acc == "v":
        v = next((x for x in vids if x["id"] == vid), None)
        if not v:
            return await e.answer("No encuentro ese video. Toca Actualizar.", alert=True)
        botones = [[Button.url("🔗 Abrir en Picta", f"https://www.picta.cu/medias/{v['slug']}")]] if v["slug"] else []
        botones.append([Button.inline("⬅️ Volver al panel", f"pn:l:{orden}:{pag}".encode())])
        error = await _mostrar(e, "ficha", ficha_caption(v), ficha_texto(v), botones, lambda: tarjeta_ficha(v))
    else:
        error = await _mostrar(e, "panel", panel_caption(vids, orden, pag), panel_texto(vids, orden, pag),
                               panel_botones(vids, orden, pag), lambda: _png_panel(vids), forzar=(acc == "r"))
    if error:
        return await e.answer(error, alert=True)
    await e.answer("Actualizado." if acc == "r" else None)

# ---------------------------------------------------------------------------------------------
# Comentarios: avisos de comentarios nuevos, /comentarios y boton "Responder".
# ---------------------------------------------------------------------------------------------
COMENTARIOS_CADA_SEG = int(os.environ.get("COMENTARIOS_CADA_SEG", "180"))   # 0 = sin avisos automaticos
ARCHIVO_COMENTARIOS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "comentarios_estado.json")
_COM = {"vistos": set(), "propios": set()}
RESPONDIENDO = {}   # id de usuario -> {"comentario": id, "publicacion": id}

def _cargar_estado_com():
    """Lee los comentarios ya avisados. Devuelve False si no habia archivo (primer arranque)."""
    try:
        with open(ARCHIVO_COMENTARIOS, encoding="utf-8") as f:
            d = json.load(f)
        _COM["vistos"] = set(d.get("vistos", []))
        _COM["propios"] = set(d.get("propios", []))
        return True
    except (FileNotFoundError, ValueError):
        return False

def _guardar_estado_com():
    try:
        with open(ARCHIVO_COMENTARIOS, "w", encoding="utf-8") as f:
            json.dump({"vistos": sorted(_COM["vistos"])[-3000:], "propios": sorted(_COM["propios"])[-3000:]}, f)
    except OSError as ex:
        print("No pude guardar el estado de comentarios:", ex, flush=True)

def picta_comentarios(token, dias=30):
    """Comentarios recientes en los videos del canal (el mismo listado del panel de administracion)."""
    h = {"Authorization": f"Bearer {token}"}
    hoy = datetime.now(TZ_CUBA).date()
    fechas = {"fecha__gte": (hoy - timedelta(days=dias)).isoformat(),
              "fecha__lt": (hoy + timedelta(days=2)).isoformat()}
    out, page = [], 1
    for _ in range(100):
        r = requests.get(f"{API}/v2/comentario/", params={**fechas, "page": page, "page_size": 50}, headers=h, timeout=60)
        r.raise_for_status()
        j = r.json()
        out += j.get("results", [])
        sig = j.get("next")
        if not sig:
            break
        page = sig if isinstance(sig, int) else page + 1
    return out

def picta_responder(pub_id, comentario_id, texto):
    """Publica una respuesta a un comentario (misma peticion que hace el panel de Picta)."""
    token = picta_token()
    campos = {"publicacion": str(pub_id), "texto": texto, "usuario": "true", "comentario": str(comentario_id)}
    r = requests.post(f"{API}/v1/comentario/", files={k: (None, v) for k, v in campos.items()},
                      headers={"Authorization": f"Bearer {token}"}, timeout=60)
    if r.status_code not in (200, 201):
        raise RuntimeError(f"Picta respondio HTTP {r.status_code}: {r.text[:300]}")
    return r.json()

def normalizar_comentario(c):
    pub = c.get("publicacion") or {}
    canal = pub.get("canal") or {}
    f = _fecha(c.get("fecha") or "")
    return {
        "id": c.get("id"), "texto": (c.get("texto") or "").strip(), "fecha": f, "ts": f.timestamp() if f else 0.0,
        "respuestas": _n(c.get("cantidad_respuestas")), "es_respuesta": bool(c.get("comentario")),
        "eliminado": bool(c.get("eliminado")), "autor": (c.get("usuario") or {}).get("username") or "?",
        "pub_id": pub.get("id"), "pub_nombre": pub.get("nombre") or "(video)", "pub_slug": pub.get("slug_url") or "",
        "pub_eliminado": bool(pub.get("eliminado")), "canal_id": canal.get("id"),
    }

def _es_mio(c):
    return c["id"] in _COM["propios"] or c["autor"].lower() == str(PICTA_USER).lower()

def preparar_comentarios(crudos):
    """Normaliza, descarta eliminados y de otros canales, y ordena del mas reciente al mas antiguo."""
    cs = [normalizar_comentario(c) for c in crudos]
    cs = [c for c in cs if c["id"] is not None and c["pub_id"] is not None and not c["eliminado"] and not c["pub_eliminado"]
          and (c["canal_id"] is None or str(c["canal_id"]) == str(CANAL_ID))]
    return sorted(cs, key=lambda c: c["ts"], reverse=True)


def texto_comentario(c, nuevo=False):
    if c["es_respuesta"]:
        cab = "↩️ Nueva respuesta" if nuevo else "↩️ Respuesta"
    else:
        cab = "💬 Nuevo comentario" if nuevo else "💬 Comentario"
    extra = ""
    if c["respuestas"]:
        extra = f"\n\n↩️ {c['respuestas']} " + ("respuesta" if c["respuestas"] == 1 else "respuestas")
    return (f"{cab}\n«{_cortar(c['pub_nombre'], 60)}»\n"
            f"👤 {c['autor']} · {_fmt_fecha(c['fecha'])}\n\n{_cortar(c['texto'], 700)}{extra}")

def botones_comentario(c):
    fila = [Button.inline("\U0001F4AC Responder", f"cm:r:{c['id']}:{c['pub_id']}".encode())]
    if c["pub_slug"]:
        fila.append(Button.url("\U0001F517 Ver video", f"https://www.picta.cu/medias/{c['pub_slug']}"))
    return [fila]

async def revisar_comentarios(primera):
    """Una vuelta del vigilante. Avisa de los comentarios nuevos y devuelve si todavia es la 'primera' vuelta."""
    token = await asyncio.to_thread(picta_token)
    crudos = await asyncio.wait_for(asyncio.to_thread(picta_comentarios, token, 7), timeout=120)
    coms = preparar_comentarios(crudos)
    _COM["vistos"].update(c["id"] for c in coms if _es_mio(c))
    nuevos = [c for c in coms if c["id"] not in _COM["vistos"]]
    if primera:   # sin historial: lo que ya existe no se avisa
        _COM["vistos"].update(c["id"] for c in nuevos)
    else:
        for c in sorted(nuevos, key=lambda c: c["ts"]):
            await client.send_message(ALLOWED, texto_comentario(c, True), buttons=botones_comentario(c), parse_mode=None)
            _COM["vistos"].add(c["id"])
    _guardar_estado_com()
    return False

async def vigilar_comentarios():
    if COMENTARIOS_CADA_SEG <= 0:
        return
    primera = not _cargar_estado_com()
    while True:
        try:
            primera = await revisar_comentarios(primera)
        except Exception as ex:
            print("Vigilante de comentarios:", type(ex).__name__, ex, flush=True)
        await asyncio.sleep(COMENTARIOS_CADA_SEG)

@client.on(events.NewMessage(pattern=r"^/comentarios\b"))
async def comentarios_cmd(e):
    if not autorizado(e): return
    args = e.raw_text.lower().split()[1:]
    todos = "todos" in args
    n = next((min(int(a), 10) for a in args if a.isdigit() and int(a) > 0), 5)
    msg = await e.respond("\U0001F4AC Consultando los comentarios...", parse_mode=None)
    try:
        token = await asyncio.to_thread(picta_token)
        crudos = await asyncio.wait_for(asyncio.to_thread(picta_comentarios, token, 30), timeout=120)
    except Exception as ex:
        return await msg.edit(f"No pude consultar Picta ({type(ex).__name__}): {ex or 'Picta tardó demasiado en responder'}", parse_mode=None)
    coms = [c for c in preparar_comentarios(crudos) if not _es_mio(c)]
    pend = [c for c in coms if c["respuestas"] == 0]
    lista = (coms if todos else pend)[:n]
    resumen = f"\U0001F4AC Comentarios de los \u00faltimos 30 d\u00edas: {len(coms)} ({len(pend)} sin responder)."
    if not lista:
        vacio = "No hay comentarios." if todos else "No tienes comentarios sin responder. \U0001F389\nUsa /comentarios todos para ver los \u00faltimos."
        return await msg.edit(resumen + "\n\n" + vacio, parse_mode=None)
    quienes = "los \u00faltimos" if todos else "los pendientes m\u00e1s recientes"
    await msg.edit(resumen + f"\nTe muestro {quienes} ({len(lista)}):", parse_mode=None)
    for c in lista:
        await e.respond(texto_comentario(c), buttons=botones_comentario(c), parse_mode=None)

@client.on(events.CallbackQuery(pattern=rb"cm:r:(\d+):(\d+)"))
async def comentario_responder_cb(e):
    if e.sender_id != ALLOWED: return
    cid, pid = int(e.pattern_match.group(1)), int(e.pattern_match.group(2))
    s = sessions.get(e.sender_id)
    if s and s.get("step") != "subiendo":
        return await e.answer("Est\u00e1s preparando un video. Term\u00ednalo o usa /cancel antes de responder.", alert=True)
    RESPONDIENDO[e.sender_id] = {"comentario": cid, "publicacion": pid}
    await e.answer()
    await e.respond(f"{MASCOTA} ¿Qué le respondo?\nEscribe tu respuesta y la publico en Picta. /cancel para anular.", parse_mode=None)

async def enviar_respuesta(e, r):
    texto = e.raw_text.strip()
    if not texto:
        return await e.respond("Escribe el texto de tu respuesta (o /cancel).", parse_mode=None)
    msg = await e.respond("Enviando tu respuesta a Picta...", parse_mode=None)
    try:
        res = await asyncio.wait_for(asyncio.to_thread(picta_responder, r["publicacion"], r["comentario"], texto), timeout=90)
    except Exception as ex:
        return await msg.edit(f"\u274c No pude enviar la respuesta ({type(ex).__name__}): {ex or 'sin respuesta'}\n"
                              "Puedes escribirla otra vez, o usar /cancel.", parse_mode=None)
    RESPONDIENDO.pop(e.sender_id, None)
    if res.get("id") is not None:
        _COM["propios"].add(res["id"]); _COM["vistos"].add(res["id"])
        _guardar_estado_com()
    await msg.edit(f"{MASCOTA} ¡Respuesta publicada en Picta!", parse_mode=None)

# ---------------------------------------------------------------------------------------------
# Avisos de hitos (1000 vistas / 500 reproducciones) y resumen semanal
# ---------------------------------------------------------------------------------------------
ARCHIVO_METRICAS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "metricas_estado.json")
HITO_VISTAS = int(os.environ.get("HITO_VISTAS") or 1000)
HITO_REPRO = int(os.environ.get("HITO_REPRO") or 500)
METRICAS_CADA_SEG = int(os.environ.get("METRICAS_CADA_SEG") or 900)   # cada cuanto se revisa (15 min)
RESUMEN_DIA = int(os.environ.get("RESUMEN_DIA") or 6)                 # 0=lunes ... 6=domingo
RESUMEN_HORA = int(os.environ.get("RESUMEN_HORA") or 20)              # hora de Cuba
_MET = {"hito_v": set(), "hito_r": set(), "base": None, "base_fecha": None, "ultimo": None}
CAMPOS_MET = ("vistas", "repro", "likes", "comentarios", "descargas")

def _cargar_metricas():
    """Devuelve False si no habia archivo (primer arranque)."""
    try:
        with open(ARCHIVO_METRICAS, encoding="utf-8") as f:
            d = json.load(f)
        _MET["hito_v"], _MET["hito_r"] = set(d.get("hito_v", [])), set(d.get("hito_r", []))
        _MET["base"], _MET["base_fecha"], _MET["ultimo"] = d.get("base"), d.get("base_fecha"), d.get("ultimo")
        return True
    except (FileNotFoundError, ValueError):
        return False

def _guardar_metricas():
    try:
        with open(ARCHIVO_METRICAS, "w", encoding="utf-8") as f:
            json.dump({"hito_v": sorted(_MET["hito_v"]), "hito_r": sorted(_MET["hito_r"]), "base": _MET["base"],
                       "base_fecha": _MET["base_fecha"], "ultimo": _MET["ultimo"]}, f)
    except OSError as ex:
        print("No pude guardar las metricas:", ex, flush=True)

def _foto(vids):
    return {str(v["id"]): {k: v[k] for k in CAMPOS_MET} for v in vids}

def texto_resumen(vids, base, desde):
    pub = [v for v in vids if v["publicado"]]
    ganado = lambda v, k: max(0, v[k] - (base.get(str(v["id"]), {}).get(k, 0)))
    tot = lambda k: sum(ganado(v, k) for v in pub)
    nuevos = [v for v in pub if str(v["id"]) not in base]
    top = sorted((v for v in pub if ganado(v, "vistas") > 0), key=lambda v: ganado(v, "vistas"), reverse=True)[:3]
    hasta = datetime.now(TZ_CUBA).strftime("%d/%m")
    lineas = [f"{MASCOTA} Resumen · {desde} → {hasta}", LINEA,
              f"👀 +{tot('vistas'):,} vistas · ▶️ +{tot('repro'):,} reproducciones",
              f"❤️ +{tot('likes'):,} me gusta · 💬 +{tot('comentarios'):,} · 📥 +{tot('descargas'):,}",
              f"🎬 {len(nuevos)} " + ("video nuevo" if len(nuevos) == 1 else "videos nuevos")]
    if top:
        lineas += [LINEA, "Lo más visto del periodo:"]
        lineas += [f"{i}. {_cortar(v['nombre'], 40)} (+{ganado(v, 'vistas'):,})" for i, v in enumerate(top, 1)]
    lineas += [LINEA, f"Total del canal: {len(pub)} videos · 👀 {sum(v['vistas'] for v in pub):,} · "
                      f"▶️ {sum(v['repro'] for v in pub):,} · ❤️ {sum(v['likes'] for v in pub):,}"]
    return "\n".join(lineas)

async def revisar_metricas(primera):
    vids = await _datos_panel(forzar=True)
    pub = [v for v in vids if v["publicado"]]
    hoy = datetime.now(TZ_CUBA)
    if _MET["base"] is None:     # primera foto: desde aqui se cuenta la semana
        _MET["base"], _MET["base_fecha"] = _foto(pub), hoy.strftime("%d/%m")
    for v in pub:
        for clave, campo, meta, etiqueta in (("hito_v", "vistas", HITO_VISTAS, "vistas"),
                                             ("hito_r", "repro", HITO_REPRO, "reproducciones")):
            if v[campo] < meta or v["id"] in _MET[clave]:
                continue
            _MET[clave].add(v["id"])
            if primera:          # lo que ya estaba por encima al arrancar no se avisa
                continue
            texto = (f"🎉 ¡«{_cortar(v['nombre'], 50)}» llegó a {meta:,} {etiqueta}!\n"
                     f"👀 {v['vistas']:,} · ▶️ {v['repro']:,} · ❤️ {v['likes']:,} · 💬 {v['comentarios']:,}")
            botones = [[Button.url("🔗 Abrir en Picta", f"https://www.picta.cu/medias/{v['slug']}")]] if v["slug"] else None
            await client.send_message(ALLOWED, texto, buttons=botones, parse_mode=None)
    if hoy.weekday() == RESUMEN_DIA and hoy.hour >= RESUMEN_HORA and _MET["ultimo"] != hoy.date().isoformat():
        await client.send_message(ALLOWED, texto_resumen(vids, _MET["base"], _MET["base_fecha"]), parse_mode=None)
        _MET["base"], _MET["base_fecha"], _MET["ultimo"] = _foto(pub), hoy.strftime("%d/%m"), hoy.date().isoformat()
    _guardar_metricas()
    return False

async def vigilar_metricas():
    if METRICAS_CADA_SEG <= 0:
        return
    primera = not _cargar_metricas()
    while True:
        try:
            primera = await revisar_metricas(primera)
        except Exception as ex:
            print("Vigilante de metricas:", type(ex).__name__, ex, flush=True)
        await asyncio.sleep(METRICAS_CADA_SEG)

@client.on(events.NewMessage(pattern=r"^/resumen\b"))
async def resumen_cmd(e):
    """Muestra ahora el resumen desde la ultima foto (no la reinicia)."""
    if not autorizado(e): return
    msg = await e.respond(f"{MASCOTA} Preparando el resumen…", parse_mode=None)
    try:
        vids = await _datos_panel(forzar=True)
    except Exception as ex:
        return await msg.edit(f"No pude consultar Picta ({type(ex).__name__}): {ex or 'Picta tardó demasiado en responder'}", parse_mode=None)
    if _MET["base"] is None:
        _MET["base"], _MET["base_fecha"] = _foto([v for v in vids if v["publicado"]]), datetime.now(TZ_CUBA).strftime("%d/%m")
        _guardar_metricas()
        return await msg.edit(f"{MASCOTA} Empiezo a contar desde hoy. Escribe /resumen más adelante para ver cuánto crecieron tus videos.", parse_mode=None)
    await msg.edit(texto_resumen(vids, _MET["base"], _MET["base_fecha"]), parse_mode=None)

print("Bot definido.")

def _servidor_salud():
    """Solo si existe la variable PORT (la pone Render): abre un puerto HTTP minimo que responde "ok".
    Render lo exige para los servicios web, y un servicio externo (UptimeRobot) puede visitarlo
    cada pocos minutos para que el servicio gratis no se duerma."""
    puerto = os.environ.get("PORT")
    if not puerto:
        return
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class _H(BaseHTTPRequestHandler):
        def _cabeceras(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", "2")
            self.end_headers()

        def do_GET(self):
            self._cabeceras()
            self.wfile.write(b"ok")

        def do_HEAD(self):
            self._cabeceras()

        def log_message(self, *a):
            pass

    srv = HTTPServer(("0.0.0.0", int(puerto)), _H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    print(f"Servidor de salud escuchando en el puerto {puerto}", flush=True)

async def main():
    _servidor_salud()
    await client.start(bot_token=BOT_TOKEN)
    me = await client.get_me()
    print(f"Bot activo: @{me.username}", flush=True)
    try:
        try:
            import cryptg  # noqa: F401  (acelera mucho el descifrado de Telethon)
            aviso = ""
        except ImportError:
            aviso = "\n⚠️ Las descargas irán lentas: falta instalar cryptg (pip install cryptg) y reiniciar el bot."
            print("AVISO: cryptg no esta instalado; las descargas de Telegram seran lentas. pip install cryptg", flush=True)
        await client.send_message(ALLOWED, "🟢 Bot encendido. Si estabas subiendo algo antes de este aviso, se cortó: repítelo." + aviso)
    except Exception:
        pass
    vigilante = asyncio.create_task(vigilar_comentarios())   # avisos de comentarios nuevos
    metricas = asyncio.create_task(vigilar_metricas())       # avisos de hitos y resumen semanal
    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())
