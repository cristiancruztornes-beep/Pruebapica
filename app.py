"""
Prueba minima: abre la pagina y muestra si este servidor llega a Picta.
Solo usa la libreria estandar de Python (no necesita requirements.txt).
Start command en Render:  python app.py
"""
import os
import socket
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

HOSTS = ["api.picta.cu", "www.picta.cu", "admin.picta.cu", "videos.picta.cu"]


def probar(host, salida, i):
    try:
        ips = sorted({a[4][0] for a in socket.getaddrinfo(host, 443, socket.AF_INET)})
        s = socket.create_connection((host, 443), timeout=8)
        s.close()
        salida[i] = f"{host}: CONECTA {ips}"
    except Exception as e:
        salida[i] = f"{host}: FALLA {type(e).__name__}"


def mi_ip():
    try:
        return urllib.request.urlopen("https://api.ipify.org", timeout=8).read().decode()
    except Exception as e:
        return f"desconocida ({type(e).__name__})"


class H(BaseHTTPRequestHandler):
    def do_GET(self):
        salida = [None] * len(HOSTS)
        hilos = [threading.Thread(target=probar, args=(h, salida, i)) for i, h in enumerate(HOSTS)]
        for t in hilos:
            t.start()
        for t in hilos:
            t.join()
        texto = "IP de este servidor: " + mi_ip() + "\n\n" + "\n".join(salida) + "\n"
        data = texto.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    HTTPServer(("0.0.0.0", port), H).serve_forever()
