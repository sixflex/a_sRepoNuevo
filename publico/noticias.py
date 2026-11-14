"""
Noticias A+S del portal público (RF-PUB-03, RF-PUB-04, HU-11).

La Universidad todavía no entrega una fuente autorizada de noticias (PV-05):
su sitio no tiene una etiqueta ni un RSS de A+S. Mientras tanto, el
Coordinador pega el enlace de la noticia y el sistema lee de la propia página
el título, el resumen, la imagen y la fecha (etiquetas Open Graph), para que
solo revise y publique. Si la página no se puede leer, completa los datos a
mano (RF-PUB-04).
"""

from datetime import datetime
from html.parser import HTMLParser
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from django.utils import timezone

# Solo se leen páginas del sitio institucional: el servidor no visita
# cualquier dirección que se pegue.
DOMINIOS_LEIBLES = ("uautonoma.cl",)

# Búsqueda del sitio UA con las noticias de A+S.
BUSQUEDA_UA = "https://www.uautonoma.cl/?s=aprendizaje+servicio"

FUENTE_UA = "Universidad Autónoma de Chile"

PUBLICADA = "PUBLICADA"
OCULTA = "OCULTA"

TIEMPO_ESPERA = 8
MAXIMO_BYTES = 1_500_000


class NoticiaNoLeida(Exception):
    """La página no se pudo leer; el Coordinador completa los datos a mano."""


def normalizar_url(url):
    """Misma noticia, mismo enlace: sin espacios, sin #ancla ni "/" final."""
    url = (url or "").strip().split("#")[0]
    return url.rstrip("/")


def es_leible(url):
    partes = urlsplit(url)
    host = (partes.hostname or "").lower()
    return partes.scheme in ("http", "https") and any(
        host == dominio or host.endswith("." + dominio) for dominio in DOMINIOS_LEIBLES
    )


class _Metadatos(HTMLParser):
    """Junta las etiquetas <meta> y el <title> de la página."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.meta = {}
        self.titulo = ""
        self._en_titulo = False

    def handle_starttag(self, tag, attrs):
        datos = dict(attrs)
        if tag == "meta":
            clave = (datos.get("property") or datos.get("name") or "").lower()
            if clave and datos.get("content") and clave not in self.meta:
                self.meta[clave] = datos["content"].strip()
        elif tag == "title":
            self._en_titulo = True

    def handle_endtag(self, tag):
        if tag == "title":
            self._en_titulo = False

    def handle_data(self, data):
        if self._en_titulo:
            self.titulo += data


def _fecha(texto):
    try:
        fecha = datetime.fromisoformat((texto or "").replace("Z", "+00:00"))
    except ValueError:
        return None
    if timezone.is_naive(fecha):
        fecha = timezone.make_aware(fecha)
    return fecha


def _descargar(url):
    pedido = Request(url, headers={"User-Agent": "PortalAS/1.0 (noticias A+S)"})
    with urlopen(pedido, timeout=TIEMPO_ESPERA) as respuesta:
        juego = respuesta.headers.get_content_charset() or "utf-8"
        return respuesta.read(MAXIMO_BYTES).decode(juego, errors="replace")


def leer_noticia(url):
    """
    Datos de la noticia para precargar el formulario. Lanza NoticiaNoLeida si
    el enlace no es del sitio UA o la página no responde.
    """
    url = normalizar_url(url)
    if not es_leible(url):
        raise NoticiaNoLeida(
            "Solo se leen automáticamente las noticias de uautonoma.cl. Completa los datos a mano."
        )
    try:
        html = _descargar(url)
    except Exception as error:  # red, tiempo de espera, 404…
        raise NoticiaNoLeida(
            "No pudimos abrir la noticia en este momento. Completa los datos a mano o inténtalo más tarde."
        ) from error

    lector = _Metadatos()
    lector.feed(html)
    meta = lector.meta

    titulo = meta.get("og:title") or " ".join(lector.titulo.split())
    for sufijo in (" - Universidad Autónoma de Chile", " | Universidad Autónoma de Chile"):
        titulo = titulo.removesuffix(sufijo)
    if not titulo:
        raise NoticiaNoLeida("La página no tiene título de noticia. Completa los datos a mano.")

    return {
        "url_fuente": url,
        "titulo": titulo[:255],
        "resumen": meta.get("og:description") or meta.get("description") or "",
        "imagen_url": (meta.get("og:image") or "")[:500],
        "fecha_publicacion": _fecha(meta.get("article:published_time")) or timezone.now(),
        "fuente": FUENTE_UA,
    }
