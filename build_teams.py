"""
Regenera el fichero de equipos (Teams.xlsx) a partir de la rota anual (.xlsm).

Uso:
    python build_teams.py <ruta-de-la-rota>.xlsm

Produce el fichero que consume la app, con las columnas: Crew, Login, Name, X, Role.

Que hojas lee se configura en el .env:
    ROTA_MAIN_SHEET   hoja principal (turnos numericos 1..CREW_COUNT)
    ROTA_EXTRA_SHEET  hoja opcional de un equipo con nombre propio (NAMED_CREWS)

Reglas:
  - Hoja principal: se busca la tabla de personal (cabecera "Crew | Login | ...").
    Los turnos numericos son los equipos con SRMET. "C" (central) y "Ap"
    (aprendices) se conservan para identificar a la persona, pero sin equipo.
  - Hoja extra: el personal marcado con el nombre del equipo en la columna X se
    agrupa en ese equipo. Las filas centrales ("C") se ignoran porque ya vienen
    de la hoja principal.
  - Se descartan las filas de recuento, la seccion ATTRITION y las vacantes
    (aquellas cuyo Login es un marcador de puesto como "SRMET"/"RMET").
"""
import sys
import os
import openpyxl
import config

HEADER = ["Crew", "Login", "Name", "X", "Role"]
ROLE_PLACEHOLDERS = {"srmet", "rmet", "rmeo", "rmea", "rmep", "isrmet"}
OUT_PATH = config.TEAMS_FILE
MAIN_SHEET = os.environ.get("ROTA_MAIN_SHEET", "CALENDAR")
EXTRA_SHEET = os.environ.get("ROTA_EXTRA_SHEET", "")
# Nombre del equipo de la hoja extra (el primero de NAMED_CREWS en el .env).
EXTRA_CREW = config.NAMED_CREWS[0] if config.NAMED_CREWS else ""


def _txt(v):
    return "" if v is None else str(v).strip()


def _find_header_row(ws):
    for r in range(1, min(ws.max_row, 60) + 1):
        for c in range(1, 8):
            if _txt(ws.cell(r, c).value).lower() == "crew" and \
               _txt(ws.cell(r, c + 1).value).lower() == "login":
                return r, c
    raise RuntimeError(f"No se encontro la cabecera Crew/Login en '{ws.title}'")


def _read_people(ws):
    """Devuelve las filas de personal (crew, login, name, x, role) de una hoja."""
    hr, hc = _find_header_row(ws)
    people = []
    for r in range(hr + 1, ws.max_row + 1):
        crew = _txt(ws.cell(r, hc).value)
        login = _txt(ws.cell(r, hc + 1).value)
        name = _txt(ws.cell(r, hc + 2).value)
        x = _txt(ws.cell(r, hc + 3).value)
        role = _txt(ws.cell(r, hc + 4).value)

        # Fila de recuento / separador: solo un numero suelto en Login.
        if login.isdigit():
            continue
        # Fin de la tabla: seccion ATTRITION u otras notas al pie.
        if crew.upper().startswith("ATTRITION"):
            break
        if not login or not name or not role:
            continue
        # Vacante sin login real (el Login repite el nombre del puesto).
        if login.lower() in ROLE_PLACEHOLDERS:
            print(f"  [omitido] vacante sin login: {name} ({role}) fila {r}")
            continue
        people.append({"crew": crew, "login": login.lower(), "name": name,
                       "x": x, "role": role})
    return people, hr


def build(xlsm_path, out_path=OUT_PATH):
    wb = openpyxl.load_workbook(xlsm_path, data_only=True)

    rows = []
    seen = {}

    if MAIN_SHEET not in wb.sheetnames:
        raise SystemExit(
            f"La rota no tiene ninguna hoja llamada '{MAIN_SHEET}'.\n"
            f"Hojas disponibles: {', '.join(wb.sheetnames)}\n"
            "Ajusta ROTA_MAIN_SHEET en el archivo .env."
        )

    print(f"{MAIN_SHEET}:")
    principal, hr = _read_people(wb[MAIN_SHEET])
    # La tabla principal termina donde empieza la seccion de aprendices "Ap";
    # ambas se conservan, pero cortamos si aparece algo que no es turno/C/Ap.
    for p in principal:
        crew = p["crew"]
        if crew.isdigit():
            crew = int(crew)
        elif crew.upper() not in ("C", "AP"):
            continue
        if p["login"] in seen:
            continue
        seen[p["login"]] = crew
        rows.append([crew, p["login"], p["name"], p["x"] or None, p["role"]])

    # Hoja extra opcional: un equipo con nombre propio en su propia pestana.
    if EXTRA_SHEET and EXTRA_CREW and EXTRA_SHEET in wb.sheetnames:
        print(f"{EXTRA_SHEET}:")
        extra, _ = _read_people(wb[EXTRA_SHEET])
        for p in extra:
            # Solo el personal propio de ese equipo (marcado en la columna X);
            # las filas "C" ya vienen de la hoja principal.
            if p["x"].upper() != EXTRA_CREW.upper():
                continue
            if p["login"] in seen:
                print(f"  [omitido] {p['login']} ya asignado a equipo {seen[p['login']]}")
                continue
            seen[p["login"]] = EXTRA_CREW
            rows.append([EXTRA_CREW, p["login"], p["name"], None, p["role"]])

    out = openpyxl.Workbook()
    ws = out.active
    ws.title = "Teams"
    ws.append(HEADER)
    for row in rows:
        ws.append(row)
    for col, width in zip("ABCDE", (8, 14, 34, 6, 12)):
        ws.column_dimensions[col].width = width

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    out.save(out_path)
    return rows, out_path


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("Uso: python build_teams.py <ruta-de-la-rota>.xlsm")
    rows, path = build(sys.argv[1])
    print(f"\n{len(rows)} personas escritas en {path}")
