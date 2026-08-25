import os
import pandas as pd
from datetime import date
import config


def _building_filter():
    """Lista de edificios aceptados, o None si no hay que filtrar."""
    raw = getattr(config, 'BUILDING_FILTER', None)
    if not raw:
        return None
    if isinstance(raw, str):
        raw = [raw]
    return {str(b).strip().upper() for b in raw if str(b).strip()}


# El informe de formacion se exporta en varios formatos segun el report que
# se use en la herramienta. Cada campo que necesitamos puede venir con
# nombres distintos; aqui se listan todos los alias conocidos (en minusculas).
COLUMN_ALIASES = {
    'login':                  ('employee login', 'login', 'employee_login'),
    'name':                   ('employee name', 'name', 'employee_name'),
    'course_title':           ('course title', 'course_title', 'coursetitle'),
    'days_til_non_compliant': ('days til non compliant', 'days_til_non_compliant'),
    'expiration_date':        ('expiration date', 'expiration_date'),
    'compliance_category':    ('compliance category', 'compliance_category'),
    'building':               ('building', 'site'),
}


def _column_map(df):
    """Relaciona cada campo interno con la columna real del CSV, si existe."""
    found = {}
    for internal, aliases in COLUMN_ALIASES.items():
        for col in df.columns:
            if str(col).strip().lower().lstrip('﻿') in aliases:
                found[internal] = col
                break
    return found


def _tidy_name(value):
    """Normaliza 'Apellidos,Nombre' a 'Nombre Apellidos'."""
    text = str(value).strip()
    if ',' in text:
        surname, _, given = text.partition(',')
        given, surname = given.strip(), surname.strip()
        if given and surname:
            return f'{given} {surname}'
    return text


def process_csv(filepath):
    # utf-8-sig: algunos informes se exportan con BOM y la primera columna
    # llegaria como '﻿Building'.
    df = pd.read_csv(filepath, encoding='utf-8-sig')
    cols = _column_map(df)

    missing = [f for f in ('login', 'name', 'course_title') if f not in cols]
    if 'days_til_non_compliant' not in cols and 'expiration_date' not in cols:
        missing.append("'Days Til Non Compliant' o 'Expiration Date'")
    if missing:
        raise ValueError(
            "El CSV no tiene el formato esperado. Faltan estas columnas: "
            + ", ".join(missing)
            + ". Columnas encontradas: " + ", ".join(str(c) for c in df.columns)
        )

    # Filtro por edificio: el informe puede venir con varios sites mezclados.
    buildings = _building_filter()
    if buildings and 'building' in cols:
        col = cols['building']
        df = df[df[col].astype(str).str.strip().str.upper().isin(buildings)]

    if 'days_til_non_compliant' in cols:
        # El informe ya trae los dias calculados.
        days = pd.to_numeric(df[cols['days_til_non_compliant']], errors='coerce')
    else:
        # Hay que calcularlos a partir de la fecha de caducidad.
        exp = pd.to_datetime(df[cols['expiration_date']], errors='coerce')
        today = date.today()
        days = exp.apply(lambda x: (x.date() - today).days if pd.notna(x) else None)
        days = pd.to_numeric(days, errors='coerce')

    df = df.assign(days_til_non_compliant=days)
    df = df[df['days_til_non_compliant'].notna() &
            (df['days_til_non_compliant'] < config.DAYS_THRESHOLD)]

    result = pd.DataFrame({
        'login': df[cols['login']].astype(str).str.strip().str.lower(),
        'name': df[cols['name']].apply(_tidy_name),
        'course_title': df[cols['course_title']].astype(str).str.strip(),
        'days_til_non_compliant': df['days_til_non_compliant'].astype(int),
        'compliance_category': (df[cols['compliance_category']]
                                if 'compliance_category' in cols else ''),
    })

    return result.to_dict('records')


_NAMED_CREWS = {str(c).strip().upper(): str(c) for c in config.NAMED_CREWS}


def _parse_crew(crew_raw):
    """Normaliza el valor de la columna Crew.

    Devuelve el numero de turno (int) si es uno de los turnos con SRMET,
    el nombre del equipo (str) si es un equipo con nombre propio (NAMED_CREWS),
    o None para el resto ("C", "Ap", vacio...), que no forman equipo.
    """
    if crew_raw is None or (isinstance(crew_raw, float) and pd.isna(crew_raw)):
        return None
    raw = str(crew_raw).strip()
    if not raw or raw.lower() == 'nan':
        return None
    if raw.upper() in _NAMED_CREWS:
        return _NAMED_CREWS[raw.upper()]
    try:
        n = int(float(raw))
    except (ValueError, TypeError):
        return None
    return n if n in config.NUMERIC_CREWS else None


def _crew_sort_key(crew):
    """Ordena los turnos numericos primero y despues los equipos con nombre."""
    return (0, crew, '') if isinstance(crew, int) else (1, 0, str(crew))


def load_teams():
    if not os.path.exists(config.TEAMS_FILE):
        raise FileNotFoundError(
            f"No se encuentra el fichero de equipos '{config.TEAMS_FILE}'. "
            "Generalo a partir de la rota anual con: "
            "python build_teams.py uploads/<CALENDAR_FULLROTA>.xlsm"
        )
    df = pd.read_excel(config.TEAMS_FILE)

    teams = {}           # crew_num (int 1-12) -> {'srmets': [{...}, ...], 'members': [...]}
    login_to_crew = {}   # login -> crew_num or None (non-main crew) or 'missing' (not in file)

    for _, row in df.iterrows():
        crew_raw = row.get('Crew')
        login = str(row.get('Login', '')).strip().lower()
        name = str(row.get('Name', '')).strip()
        role = str(row.get('Role', '')).strip()

        if not login or login == 'nan':
            continue

        crew_num = _parse_crew(crew_raw)

        login_to_crew[login] = crew_num

        if crew_num is not None:
            if crew_num not in teams:
                teams[crew_num] = {'srmets': [], 'members': []}
            if role == 'SRMET':
                teams[crew_num]['srmets'].append({'login': login, 'name': name})
            else:
                teams[crew_num]['members'].append({'login': login, 'name': name, 'role': role})

    return teams, login_to_crew


def assign_teams(filtered_records, teams, login_to_crew):
    srmet_groups = {}  # srmet_login -> group dict
    no_srmet = []

    for record in filtered_records:
        login = record['login']
        crew_num = login_to_crew.get(login)  # None if not in Teams.xlsx or non-main crew

        rec = dict(record)
        rec['crew'] = crew_num

        srmets = []
        if crew_num is not None and crew_num in teams:
            srmets = teams[crew_num].get('srmets', [])

        if srmets:
            for srmet in srmets:
                key = srmet['login']
                if key not in srmet_groups:
                    srmet_groups[key] = {
                        'srmet_login': key,
                        'srmet_name': srmet['name'],
                        'srmet_email': key + config.EMAIL_DOMAIN,
                        'crew': crew_num,
                        'members': []
                    }
                srmet_groups[key]['members'].append(rec)
        else:
            if login not in login_to_crew:
                rec['no_team_reason'] = 'No aparece en Teams.xlsx'
            elif crew_num is None:
                rec['no_team_reason'] = 'Equipo sin SRMET asignado (C / Ap)'
            else:
                rec['no_team_reason'] = f'Equipo {crew_num} sin SRMET definido'
            no_srmet.append(rec)

    for key in srmet_groups:
        srmet_groups[key]['members'].sort(key=lambda x: x['days_til_non_compliant'])

    no_srmet.sort(key=lambda x: x['days_til_non_compliant'])

    return list(srmet_groups.values()), no_srmet


def get_compliant_srmets(teams, srmet_groups):
    """SRMETs whose crew has an SRMET defined but no pending/expiring courses."""
    crews_with_issues = {g['crew'] for g in srmet_groups}
    compliant = []
    for crew_num, team in teams.items():
        if crew_num in crews_with_issues:
            continue
        for srmet in team.get('srmets', []):
            compliant.append({
                'crew': crew_num,
                'srmet_login': srmet['login'],
                'srmet_name': srmet['name'],
                'srmet_email': srmet['login'] + config.EMAIL_DOMAIN,
            })
    compliant.sort(key=lambda x: _crew_sort_key(x['crew']))
    return compliant


def group_no_srmet_by_employee(no_srmet):
    """Group no_srmet course records by employee, returning one entry per unique person."""
    employees = {}
    for rec in no_srmet:
        login = rec['login']
        if login not in employees:
            employees[login] = {
                'login': login,
                'name': rec['name'],
                'email': login + config.EMAIL_DOMAIN,
                'no_team_reason': rec.get('no_team_reason', ''),
                'courses': []
            }
        employees[login]['courses'].append({
            'course_title': rec['course_title'],
            'days_til_non_compliant': rec['days_til_non_compliant']
        })
    for emp in employees.values():
        emp['courses'].sort(key=lambda x: x['days_til_non_compliant'])
    return list(employees.values())
