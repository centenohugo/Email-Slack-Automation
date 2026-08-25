"""
Configuracion de la app. Todo se lee del archivo .env de esta misma carpeta.

Si una variable no esta en el .env se usa el valor por defecto de aqui abajo.
Los valores por defecto son genericos a proposito: los datos reales de tu
site (edificios, dominio de correo, enlace del informe) van en el .env, que
NUNCA se sube al repositorio.
"""
import os
from dotenv import load_dotenv

load_dotenv()


def _texto(nombre, por_defecto=""):
    return (os.environ.get(nombre) or por_defecto).strip()


def _lista(nombre, por_defecto=""):
    """Lee una variable separada por comas: 'EDIF1, EDIF2' -> ('EDIF1', 'EDIF2')."""
    crudo = _texto(nombre, por_defecto)
    return tuple(x.strip() for x in crudo.split(",") if x.strip())


def _entero(nombre, por_defecto):
    try:
        return int(_texto(nombre) or por_defecto)
    except ValueError:
        return por_defecto


# --- Identidad del site -----------------------------------------------------
# Nombre corto que aparece en la cabecera de la web y al firmar los mensajes.
SITE_NAME = _texto("SITE_NAME", "RME")
# Firma de los correos y mensajes de Slack.
SIGNATURE = _texto("SIGNATURE", f"Equipo de {SITE_NAME}-Trainings")
# Dominio de correo de la empresa: el login 'jdoe' se convierte en jdoe@...
EMAIL_DOMAIN = _texto("EMAIL_DOMAIN", "@example.com")

# --- Filtros del informe ----------------------------------------------------
# Edificios que se tienen en cuenta. Vacio = no filtrar por edificio.
BUILDING_FILTER = _lista("BUILDINGS")
# Se avisa de los cursos que caducan en menos de estos dias (incluye caducados).
DAYS_THRESHOLD = _entero("DAYS_THRESHOLD", 21)
# Turnos numericos que tienen SRMET asignado: 1..CREW_COUNT.
NUMERIC_CREWS = range(1, _entero("CREW_COUNT", 12) + 1)
# Equipos con nombre propio que tambien tienen SRMET (p.ej. un edificio aparte).
NAMED_CREWS = _lista("NAMED_CREWS")

# --- Enlaces y ficheros -----------------------------------------------------
# De donde se descarga el CSV de formacion. Se muestra en la pantalla inicial.
REPORT_URL = _texto("REPORT_URL")
TEAMS_FILE = _texto("TEAMS_FILE", os.path.join("sample", "Teams.xlsx"))
UPLOAD_FOLDER = "uploads"

# --- Credenciales -----------------------------------------------------------
# Si falta SECRET_KEY se genera una de un solo uso, para no impedir arrancar.
SECRET_KEY = _texto("SECRET_KEY") or os.urandom(24).hex()
SLACK_BOT_TOKEN = _texto("SLACK_BOT_TOKEN")

# --- Envio ------------------------------------------------------------------
# Destinatario de las pruebas: por defecto, el usuario de Windows que ejecuta.
_USUARIO = os.environ.get("USERNAME") or os.environ.get("USER") or "test"
TEST_EMAIL = _texto("TEST_EMAIL") or f"{_USUARIO}{EMAIL_DOMAIN}"
# Pausa entre envios, para no saturar Outlook ni la API de Slack.
EMAIL_SEND_DELAY = 1.5
SLACK_SEND_DELAY = 1.0
PORT = _entero("PORT", 5005)
