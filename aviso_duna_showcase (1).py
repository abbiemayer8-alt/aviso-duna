#!/usr/bin/env python3
"""
Avisa por Telegram cuando "Duna: Parte Tres" aparece en la cartelera de Showcase.

Uso:
    export TELEGRAM_TOKEN="123456:ABC..."
    export TELEGRAM_CHAT_ID="123456789"
    python3 aviso_duna_showcase.py            # queda corriendo y chequea cada 5 min
    python3 aviso_duna_showcase.py --once     # un solo chequeo (para cron / GitHub Actions)
    python3 aviso_duna_showcase.py --test     # manda un mensaje de prueba y sale

Solo usa la librería estándar de Python 3.8+.
"""
import argparse
import html
import json
import os
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request

URL = "https://entradas.todoshowcase.com/showcase/"
CHECK_EVERY_SECONDS = 300          # 5 minutos; no bajar de esto para no molestar al sitio
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".duna_avisado")

# Qué consideramos "la película". Se compara sobre el texto normalizado (sin tildes, minúsculas).
PATRONES = [
    r"duna[^a-z0-9]{0,5}parte[^a-z0-9]{0,5}(tres|3)",
    r"dune[^a-z0-9]{0,5}part[^a-z0-9]{0,5}(three|3)",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "es-AR,es;q=0.9",
}


def normalizar(texto: str) -> str:
    texto = html.unescape(texto)
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    return texto.lower()


def descargar(url: str) -> str:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")


def buscar_pelicula(pagina: str):
    """Devuelve (encontrada, link) buscando la película en el HTML de la cartelera."""
    norm = normalizar(pagina)
    for patron in PATRONES:
        m = re.search(patron, norm)
        if m:
            # Busca el link de la película (pelicula.aspx?filmid=N) cerca del texto encontrado.
            cercano = norm[max(0, m.start() - 800): m.end() + 800]
            f = re.search(r"pelicula\.aspx\?filmid=(\d+)", cercano)
            link = (
                f"https://entradas.todoshowcase.com/showcase/pelicula.aspx?filmid={f.group(1)}"
                if f else URL
            )
            return True, link
    return False, None


def telegram(mensaje: str):
    token = os.environ.get("TELEGRAM_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        sys.exit("Faltan las variables de entorno TELEGRAM_TOKEN y/o TELEGRAM_CHAT_ID.")
    data = urllib.parse.urlencode({"chat_id": chat_id, "text": mensaje}).encode()
    req = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=data)
    with urllib.request.urlopen(req, timeout=30) as r:
        resp = json.load(r)
    if not resp.get("ok"):
        raise RuntimeError(f"Telegram respondió: {resp}")


def chequear() -> bool:
    """Un chequeo. Devuelve True si ya avisó (ahora o antes)."""
    if os.path.exists(STATE_FILE):
        return True
    try:
        pagina = descargar(URL)
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] Error al descargar la cartelera: {e}")
        return False

    encontrada, link = buscar_pelicula(pagina)
    ts = time.strftime("%H:%M:%S")
    if not encontrada:
        print(f"[{ts}] Todavía no aparece Duna: Parte Tres en Showcase.")
        return False

    telegram(f"🎬 Duna: Parte Tres ya aparece en la cartelera de Showcase.\n"
             f"Fijate si ya hay entradas a la venta:\n{link}")
    with open(STATE_FILE, "w") as f:
        f.write(time.strftime("%Y-%m-%d %H:%M:%S"))
    print(f"[{ts}] ¡Encontrada! Aviso enviado.")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true", help="un solo chequeo y salir")
    ap.add_argument("--test", action="store_true", help="enviar mensaje de prueba y salir")
    args = ap.parse_args()

    if args.test:
        telegram("✅ Prueba: el bot de Duna / Showcase está funcionando.")
        print("Mensaje de prueba enviado.")
        return

    if args.once:
        if chequear():
            # Si corre en GitHub Actions, avisa al workflow que ya encontró la película
            salida = os.environ.get("GITHUB_OUTPUT")
            if salida:
                with open(salida, "a") as f:
                    f.write("found=true\n")
        return

    print(f"Chequeando {URL} cada {CHECK_EVERY_SECONDS // 60} min. Ctrl+C para cortar.")
    while not chequear():
        time.sleep(CHECK_EVERY_SECONDS)


if __name__ == "__main__":
    main()
