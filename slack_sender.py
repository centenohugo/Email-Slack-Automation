# -*- coding: utf-8 -*-
"""
Envío de recordatorios por Slack.

Mismo estilo de interfaz que email_sender.py: send_slack(...) devuelve
(success, error_message) con mensajes de error en castellano.

Requiere la variable de entorno SLACK_BOT_TOKEN (ver .env / .env.example).
Usa solo `requests` contra https://slack.com/api/ (sin slack_sdk).

Scopes necesarios en la Slack App:
  users:read.email, users:read, im:write (o chat:write con conversations.open),
  chat:write
"""

import config

SLACK_API = "https://slack.com/api/"
_TIMEOUT = 15

# Cachés en memoria (se vacían al reiniciar la app)
_user_id_cache = {}     # email -> user_id
_channel_cache = {}     # user_id -> channel_id


# ---------------------------------------------------------------------------
# Errores en castellano
# ---------------------------------------------------------------------------

_SLACK_ERRORS = {
    "users_not_found": (
        "Slack no encontró ningún usuario con el email {email}. "
        "Comprueba que esa persona tiene cuenta de Slack con ese correo."
    ),
    "invalid_auth": (
        "El token de Slack no es válido. Revisa SLACK_BOT_TOKEN en el archivo .env "
        "y reinicia la app."
    ),
    "not_authed": (
        "No se envió ningún token de Slack. Añade SLACK_BOT_TOKEN al archivo .env "
        "y reinicia la app."
    ),
    "account_inactive": "La cuenta del bot de Slack está desactivada. Contacta con el administrador del workspace.",
    "token_revoked": "El token de Slack fue revocado. Genera uno nuevo y actualiza .env.",
    "missing_scope": (
        "Al bot de Slack le falta el permiso {needed}. Anadelo en "
        "api.slack.com > OAuth & Permissions, pulsa 'Reinstall to Workspace' "
        "y copia el token NUEVO al archivo .env."
    ),
    "not_allowed_token_type": (
        "El token de Slack no es de tipo bot. Debe empezar por 'xoxb-' "
        "(Bot User OAuth Token)."
    ),
    "channel_not_found": "Slack no encontró la conversación con ese usuario.",
    "is_archived": "La conversación de Slack está archivada.",
    "msg_too_long": "El mensaje es demasiado largo para Slack. Acorta el texto en SLACK_MESSAGE.md.",
    "invalid_blocks": (
        "Slack rechazó el formato del mensaje. Revisa SLACK_MESSAGE.md: probablemente "
        "hay un bloque de texto vacío o mal cerrado."
    ),
    "rate_limited": "Slack está limitando los envíos (demasiados mensajes seguidos). Espera un momento y reintenta.",
    "cannot_dm_bot": "No se puede enviar un mensaje directo a un bot de Slack.",
    "user_not_visible": "El bot no puede ver a ese usuario de Slack (permisos del workspace).",
}


def _friendly_error(code, email=None, needed=None):
    """Traduce el codigo de error de Slack a una frase accionable."""
    if not code:
        return "Error desconocido al enviar el mensaje de Slack."
    tpl = _SLACK_ERRORS.get(code)
    if tpl:
        return tpl.format(email=email or "", needed=needed or "que pide esa llamada")
    return f"Slack devolvió el error '{code}'."


def _friendly_exception(e):
    msg = str(e)
    low = msg.lower()
    if "timed out" in low or "timeout" in low:
        return (
            "Slack no respondió a tiempo. Comprueba tu conexión a internet "
            "(o el proxy corporativo) e inténtalo de nuevo."
        )
    if "ssl" in low or "certificate" in low:
        return (
            "Error de certificado SSL al conectar con Slack. Suele deberse al proxy "
            f"corporativo. (Detalle técnico: {msg})"
        )
    if "connection" in low or "resolve" in low or "name or service" in low:
        return (
            "No se pudo conectar con Slack. Comprueba tu conexión a internet o el proxy. "
            f"(Detalle técnico: {msg})"
        )
    return f"Error inesperado al enviar el mensaje de Slack: {msg}"


# ---------------------------------------------------------------------------
# Llamadas a la API
# ---------------------------------------------------------------------------

def _token():
    return (getattr(config, "SLACK_BOT_TOKEN", "") or "").strip()


def _api(method, payload=None, params=None, as_json=True, email=None):
    """Devuelve (data, error_message) con el error ya traducido al castellano."""
    import requests  # import perezoso para dar un error claro si falta

    token = _token()
    if not token:
        return None, (
            "Falta el token de Slack. Añade SLACK_BOT_TOKEN=xoxb-... al archivo .env "
            "(en la carpeta del proyecto) y reinicia la app."
        )

    headers = {"Authorization": f"Bearer {token}"}
    try:
        if as_json:
            headers["Content-Type"] = "application/json; charset=utf-8"
            r = requests.post(SLACK_API + method, headers=headers, json=payload or {}, timeout=_TIMEOUT)
        else:
            r = requests.get(SLACK_API + method, headers=headers, params=params or {}, timeout=_TIMEOUT)
    except Exception as e:
        return None, _friendly_exception(e)

    try:
        data = r.json()
    except ValueError:
        return None, f"Slack devolvió una respuesta inesperada (HTTP {r.status_code})."

    if not data.get("ok"):
        # En missing_scope, Slack indica en 'needed' el permiso exacto que falta.
        return None, _friendly_error(data.get("error"), email=email,
                                     needed=data.get("needed"))
    return data, None


def resolve_email(login_or_email):
    """login -> login@<EMAIL_DOMAIN>; un email se deja tal cual."""
    s = str(login_or_email or "").strip()
    if not s:
        return ""
    return s if "@" in s else s + config.EMAIL_DOMAIN


def lookup_user_id(email):
    """(user_id, error_message). Cachea el resultado."""
    email = (email or "").strip().lower()
    if not email:
        return None, "No se indicó ningún destinatario de Slack."
    if email in _user_id_cache:
        return _user_id_cache[email], None

    data, err = _api("users.lookupByEmail", params={"email": email},
                     as_json=False, email=email)
    if err:
        return None, err

    user_id = (data.get("user") or {}).get("id")
    if not user_id:
        return None, f"Slack no devolvió ningún usuario para {email}."
    _user_id_cache[email] = user_id
    return user_id, None


def open_dm(user_id):
    """(channel_id, error_message). Cachea el resultado."""
    if user_id in _channel_cache:
        return _channel_cache[user_id], None
    data, err = _api("conversations.open", payload={"users": user_id})
    if err:
        return None, err
    channel_id = (data.get("channel") or {}).get("id")
    if not channel_id:
        return None, "Slack no pudo abrir el mensaje directo con ese usuario."
    _channel_cache[user_id] = channel_id
    return channel_id, None


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------

def send_slack(user_email_or_login, text_or_blocks, test_mode=True):
    """
    Envía un mensaje directo de Slack. Devuelve (success, error_message).

    user_email_or_login: 'jdoe' o 'jdoe@empresa.com'.
    text_or_blocks:      str  -> se envía como texto (mrkdwn), o
                         dict -> {'blocks': [...], 'text': 'fallback'}, o
                         list -> lista de bloques de Block Kit.
    test_mode:           igual que en email_sender.send_email: todo se envía al
                         destinatario de pruebas (config.TEST_EMAIL) y el mensaje
                         se prefija con [TEST].
    """
    try:
        import requests  # noqa: F401
    except ImportError:
        return False, (
            "La librería 'requests' no está instalada. Abre una terminal en la carpeta "
            "del proyecto y ejecuta: pip install requests"
        )

    # 1) Normalizar el contenido
    blocks, text = _normalize_content(text_or_blocks)
    if not text and not blocks:
        return False, "El mensaje de Slack está vacío. Revisa SLACK_MESSAGE.md."

    # 2) Destinatario (modo test -> siempre al correo de pruebas, con prefijo [TEST])
    if test_mode:
        target_email = resolve_email(config.TEST_EMAIL)
        blocks, text = _prefix_test(blocks, text)
    else:
        target_email = resolve_email(user_email_or_login)

    # 3) Resolver el usuario de Slack a partir de su email y abrir el DM
    user_id, err = lookup_user_id(target_email)
    if err:
        return False, err

    channel_id, err = open_dm(user_id)
    if err:
        return False, err

    # 4) Publicar
    payload = {"channel": channel_id, "text": text or " "}
    if blocks:
        payload["blocks"] = blocks

    _, err = _api("chat.postMessage", payload=payload, email=target_email)
    if err:
        return False, err
    return True, None


def _normalize_content(content):
    """Devuelve (blocks, text_fallback)."""
    if content is None:
        return None, ""
    if isinstance(content, str):
        from slack_message import build_blocks, mrkdwn_to_plain
        return build_blocks("", content), mrkdwn_to_plain(content)[:2900]
    if isinstance(content, list):
        return content, ""
    if isinstance(content, dict):
        return content.get("blocks"), content.get("text", "") or ""
    return None, str(content)


def _prefix_test(blocks, text):
    """Añade [TEST] al principio, igual que email_sender hace con el asunto."""
    prefix = "[TEST] "
    text = prefix + (text or "")
    if not blocks:
        return blocks, text
    new_blocks = [dict(b) for b in blocks]
    for b in new_blocks:
        t = b.get("text")
        if isinstance(t, dict) and t.get("text"):
            nt = dict(t)
            nt["text"] = prefix + nt["text"]
            if b.get("type") == "header":
                nt["text"] = nt["text"][:150]  # límite de Slack para 'header'
            b["text"] = nt
            break
    else:
        new_blocks.insert(0, {
            "type": "section",
            "text": {"type": "mrkdwn", "text": "*[TEST]*"},
        })
    return new_blocks, text
