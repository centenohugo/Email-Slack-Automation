# -*- coding: utf-8 -*-
"""
Carga y renderiza SLACK_MESSAGE.md (el archivo editable por el usuario).

Se lee EN CADA ENVÍO, así que basta con guardar SLACK_MESSAGE.md para que los
cambios tengan efecto: no hace falta reiniciar la app.

Si el archivo falta o una sección está mal escrita, se usan los textos por
defecto de DEFAULTS y se añade un aviso a la lista de warnings.
"""

import os
import re

import config

MESSAGE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "SLACK_MESSAGE.md")

# Límites de la API de Slack
_HEADER_MAX = 150
_SECTION_MAX = 2900  # el límite real es 3000; dejamos margen


# ---------------------------------------------------------------------------
# Textos por defecto (se usan si SLACK_MESSAGE.md falta o está incompleto)
# ---------------------------------------------------------------------------

DEFAULTS = {
    "recordatorio_srmet": {
        "titulo": "🚨 Safety Training — Equipo {crew}",
        "mensaje": (
            "Hola *{srmet_first_name}*, tu equipo tiene *{count}* curso(s) de "
            "Safety Training próximos a vencer o ya vencidos:\n\n"
            "{course_list}\n\n"
            "Por favor haz seguimiento con cada técnico. Si algún curso no puede "
            "completarse a tiempo, contáctanos para buscar una solución conjunta.\n\n"
            "Gracias,\n*{signature}* · {today}"
        ),
        "linea_curso": "{emoji} *{name}* — {course_title} · `{days} d`",
    },
    "recordatorio_directo": {
        "titulo": "🚨 Safety Training — Cursos pendientes",
        "mensaje": (
            "Hola *{employee_first_name}*, tienes *{count}* curso(s) de Safety "
            "Training próximos a vencer o ya vencidos:\n\n"
            "{course_list}\n\n"
            "Te pedimos que los completes antes de la fecha de vencimiento. Si "
            "alguno no puede completarse a tiempo, contáctanos.\n\n"
            "Gracias,\n*{signature}* · {today}"
        ),
        "linea_curso": "{emoji} {course_title} · `{days} d`",
    },
    "felicitacion": {
        "titulo": "✅ Safety Training — Equipo {crew} al día",
        "mensaje": (
            "¡Enhorabuena *{srmet_first_name}*! 🎉\n\n"
            "Tu equipo no tiene ningún curso de Safety Training pendiente en los "
            "próximos {days} días. Sois un referente en compliance — ¡seguid así! 💪\n\n"
            "Gracias,\n*{signature}* · {today}"
        ),
        "linea_curso": "",
    },
}

# Nombres de sub-apartados aceptados dentro de cada sección -> clave interna
_SUBKEYS = {
    "titulo": "titulo",
    "título": "titulo",
    "mensaje": "mensaje",
    "cuerpo": "mensaje",
    "linea de curso": "linea_curso",
    "línea de curso": "linea_curso",
    "formato de linea de curso": "linea_curso",
    "formato de línea de curso": "linea_curso",
}


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def _strip_accents_lower(s):
    table = str.maketrans("áàäâéèëêíìïîóòöôúùüûñÁÀÄÂÉÈËÊÍÌÏÎÓÒÖÔÚÙÜÛÑ",
                          "aaaaeeeeiiiioooouuuunAAAAEEEEIIIIOOOOUUUUN")
    return s.translate(table).strip().lower()


def first_name(full_name):
    """'Apellido, Nombre' -> 'Nombre'. Cualquier otra cosa se devuelve tal cual."""
    if not full_name:
        return ""
    s = str(full_name)
    if "," in s:
        parts = s.split(",", 1)
        if parts[1].strip():
            return parts[1].strip()
    return s.strip()


class _SafeDict(dict):
    """Deja intactos los {placeholders} que no existan, en vez de reventar."""
    def __missing__(self, key):
        return "{" + key + "}"


def render_placeholders(template, values):
    if not template:
        return ""
    try:
        return template.format_map(_SafeDict(values))
    except (ValueError, IndexError):
        # llaves sueltas mal escritas por el usuario: devolvemos el texto crudo
        return template


def markdown_to_mrkdwn(text):
    """Convierte Markdown normal al 'mrkdwn' de Slack."""
    if not text:
        return ""
    out = text
    # [texto](url) -> <url|texto>
    out = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r"<\2|\1>", out)
    # **negrita** / __negrita__ -> *negrita*
    out = re.sub(r"\*\*(.+?)\*\*", r"*\1*", out, flags=re.S)
    out = re.sub(r"__(.+?)__", r"*\1*", out, flags=re.S)
    # viñetas markdown "- " al inicio de línea -> "• "
    out = re.sub(r"(?m)^(\s*)[-*]\s+", r"\1• ", out)
    return out


def mrkdwn_to_plain(text):
    """Texto plano para el 'text' de notificación (fallback)."""
    if not text:
        return ""
    out = re.sub(r"<(https?://[^|>]+)\|([^>]+)>", r"\2", text)
    out = out.replace("*", "").replace("`", "").replace("_", "")
    return out.strip()


# ---------------------------------------------------------------------------
# Clasificación de urgencia (misma lógica que las plantillas de email)
# ---------------------------------------------------------------------------

def urgency_for(days):
    try:
        d = int(days)
    except (TypeError, ValueError):
        return "🔵", "ATENCIÓN"
    if d <= 0:
        return "🔴", "NON COMPLIANT"
    if d <= 7:
        return "🟠", "CRÍTICO"
    if d <= 14:
        return "🟡", "URGENTE"
    return "🔵", "ATENCIÓN"


# ---------------------------------------------------------------------------
# Parser de SLACK_MESSAGE.md
# ---------------------------------------------------------------------------

_FENCE_RE = re.compile(r"^```[^\n]*\n(.*?)^```\s*$", re.S | re.M)


def _parse_section_body(raw, warnings, section_id):
    """Dentro de una sección '## id', busca '### sub' + bloque ``` ```."""
    found = {}
    # partir por sub-encabezados de nivel 3
    parts = re.split(r"(?m)^###\s+(.+?)\s*$", raw)
    # parts = [texto_antes, sub1, cuerpo1, sub2, cuerpo2, ...]
    for i in range(1, len(parts) - 1, 2):
        sub_raw = parts[i]
        body = parts[i + 1]
        key = _SUBKEYS.get(_strip_accents_lower(sub_raw))
        if not key:
            continue
        m = _FENCE_RE.search(body)
        if not m:
            warnings.append(
                f"SLACK_MESSAGE.md: la sección «{section_id}» → «{sub_raw}» no tiene "
                "un bloque de texto entre ``` ```. Se usa el texto por defecto."
            )
            continue
        found[key] = m.group(1).rstrip("\n")
    return found


def load_messages(path=None):
    """
    Devuelve (messages, warnings).
    messages = {section_id: {'titulo':..., 'mensaje':..., 'linea_curso':...}}
    """
    path = path or MESSAGE_FILE
    warnings = []
    messages = {k: dict(v) for k, v in DEFAULTS.items()}

    if not os.path.exists(path):
        warnings.append(
            f"No se encontró {os.path.basename(path)} en la carpeta del proyecto. "
            "Se usan los mensajes por defecto."
        )
        return messages, warnings

    try:
        with open(path, "r", encoding="utf-8") as fh:
            raw = fh.read()
    except Exception as e:
        warnings.append(f"No se pudo leer {os.path.basename(path)}: {e}. Se usan los mensajes por defecto.")
        return messages, warnings

    # partir por secciones de nivel 2
    chunks = re.split(r"(?m)^##\s+(.+?)\s*$", raw)
    if len(chunks) < 3:
        warnings.append(
            "SLACK_MESSAGE.md no contiene ninguna sección '## id'. Se usan los mensajes por defecto."
        )
        return messages, warnings

    seen = set()
    for i in range(1, len(chunks) - 1, 2):
        section_id = _strip_accents_lower(chunks[i]).replace(" ", "_")
        body = chunks[i + 1]
        if section_id not in messages:
            continue  # sección desconocida: la ignoramos sin molestar
        seen.add(section_id)
        found = _parse_section_body(body, warnings, section_id)
        if not found:
            warnings.append(
                f"SLACK_MESSAGE.md: la sección «{section_id}» no tiene ningún bloque "
                "válido. Se usa el texto por defecto."
            )
        messages[section_id].update({k: v for k, v in found.items() if v is not None})

    for missing in set(messages) - seen:
        warnings.append(
            f"SLACK_MESSAGE.md: falta la sección «{missing}». Se usa el texto por defecto."
        )

    return messages, warnings


# ---------------------------------------------------------------------------
# Construcción de bloques (Block Kit)
# ---------------------------------------------------------------------------

def _split_for_sections(mrkdwn_text):
    """Divide el cuerpo en trozos que quepan en un bloque 'section'."""
    chunks = []
    for part in mrkdwn_text.split("\n---\n"):
        part = part.strip("\n")
        if not part:
            continue
        while len(part) > _SECTION_MAX:
            cut = part.rfind("\n", 0, _SECTION_MAX)
            if cut <= 0:
                cut = _SECTION_MAX
            chunks.append(part[:cut].strip("\n"))
            part = part[cut:].strip("\n")
        if part:
            chunks.append(part)
    return chunks or [" "]


def build_blocks(header, body_mrkdwn):
    """header (texto plano) + divider + una o varias secciones mrkdwn."""
    blocks = []
    header = (header or "").strip()
    if header:
        blocks.append({
            "type": "header",
            "text": {"type": "plain_text", "text": header[:_HEADER_MAX], "emoji": True},
        })
        blocks.append({"type": "divider"})
    for i, chunk in enumerate(_split_for_sections(body_mrkdwn)):
        if i > 0:
            blocks.append({"type": "divider"})
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": chunk}})
    return blocks


def build_course_list(rows, line_template, extra=None):
    """
    rows: lista de dicts con al menos course_title y days_til_non_compliant
          (y opcionalmente name / login, para el recordatorio a SRMET).
    line_template: plantilla de una línea, ya en formato Slack.
    """
    lines = []
    tpl = line_template or DEFAULTS["recordatorio_srmet"]["linea_curso"]
    ordered = sorted(rows, key=lambda r: _as_int(r.get("days_til_non_compliant")))
    for r in ordered:
        days = r.get("days_til_non_compliant")
        emoji, urgencia = urgency_for(days)
        values = {
            "name": r.get("name", ""),
            "first_name": first_name(r.get("name", "")),
            "login": r.get("login", ""),
            "course_title": r.get("course_title", ""),
            "days": days if days is not None else "",
            "emoji": emoji,
            "urgency": urgencia,
            "urgencia": urgencia,
        }
        if extra:
            values.update(extra)
        lines.append(render_placeholders(tpl, values))
    return "\n".join(lines)


def _as_int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return 9999


# ---------------------------------------------------------------------------
# API pública: un builder por tipo de mensaje
# ---------------------------------------------------------------------------

def _render_section(section_id, values, rows=None, messages=None, warnings=None):
    if messages is None:
        messages, w = load_messages()
        if warnings is not None:
            warnings.extend(w)
    section = messages.get(section_id, DEFAULTS[section_id])

    line_tpl = markdown_to_mrkdwn(section.get("linea_curso") or DEFAULTS[section_id]["linea_curso"])
    course_list = build_course_list(rows or [], line_tpl) if rows else ""

    values = dict(values)
    values.setdefault("course_list", course_list)
    values.setdefault("count", len(rows or []))
    values.setdefault("total", len(rows or []))
    # Vienen del .env: la firma y el numero de dias de aviso.
    values.setdefault("signature", config.SIGNATURE)
    values.setdefault("days", config.DAYS_THRESHOLD)
    values.setdefault("site", config.SITE_NAME)

    header = render_placeholders(section.get("titulo") or DEFAULTS[section_id]["titulo"], values)
    header = mrkdwn_to_plain(markdown_to_mrkdwn(header))

    body = render_placeholders(
        markdown_to_mrkdwn(section.get("mensaje") or DEFAULTS[section_id]["mensaje"]), values
    )

    blocks = build_blocks(header, body)
    fallback = (header + " — " + mrkdwn_to_plain(body)).strip(" —")
    return {"blocks": blocks, "text": fallback[:2900]}


def build_srmet_message(srmet_name, crew, members, today, messages=None, warnings=None):
    values = {
        "srmet_name": srmet_name,
        "srmet_first_name": first_name(srmet_name),
        "employee_name": srmet_name,
        "employee_first_name": first_name(srmet_name),
        "crew": "" if crew is None else str(crew),
        "today": today,
    }
    return _render_section("recordatorio_srmet", values, rows=members,
                           messages=messages, warnings=warnings)


def build_employee_message(employee_name, courses, today, messages=None, warnings=None):
    values = {
        "employee_name": employee_name,
        "employee_first_name": first_name(employee_name),
        "srmet_name": "",
        "srmet_first_name": "",
        "crew": "",
        "today": today,
    }
    return _render_section("recordatorio_directo", values, rows=courses,
                           messages=messages, warnings=warnings)


def build_congrats_message(srmet_name, crew, today, messages=None, warnings=None):
    values = {
        "srmet_name": srmet_name,
        "srmet_first_name": first_name(srmet_name),
        "employee_name": srmet_name,
        "employee_first_name": first_name(srmet_name),
        "crew": "" if crew is None else str(crew),
        "today": today,
        "course_list": "",
        "count": 0,
    }
    return _render_section("felicitacion", values, rows=None,
                           messages=messages, warnings=warnings)
