import pandas as pd
from datetime import date
import config


def process_csv(filepath):
    df = pd.read_csv(filepath)

    if 'Building' in df.columns:
        df = df[df['Building'] == config.BUILDING_FILTER]

    df['Expiration Date'] = pd.to_datetime(df['Expiration Date'], errors='coerce')
    today = date.today()

    df['days_til_non_compliant'] = df['Expiration Date'].apply(
        lambda x: (x.date() - today).days if pd.notna(x) else None
    )

    df = df[df['days_til_non_compliant'].notna() & (df['days_til_non_compliant'] < config.DAYS_THRESHOLD)]

    result = df[['Employee Login', 'Employee Name', 'Course Title',
                 'days_til_non_compliant', 'Compliance Category']].copy()
    result.columns = ['login', 'name', 'course_title', 'days_til_non_compliant', 'compliance_category']
    result['login'] = result['login'].str.strip().str.lower()
    result['days_til_non_compliant'] = result['days_til_non_compliant'].astype(int)

    return result.to_dict('records')


def load_teams():
    df = pd.read_excel(config.TEAMS_FILE)

    teams = {}           # crew_num (int 1-12) -> {'srmet': {...}, 'members': [...]}
    login_to_crew = {}   # login -> crew_num or None (non-main crew) or 'missing' (not in file)

    for _, row in df.iterrows():
        crew_raw = row.get('Crew')
        login = str(row.get('Login', '')).strip().lower()
        name = str(row.get('Name', '')).strip()
        role = str(row.get('Role', '')).strip()

        if not login or login == 'nan':
            continue

        crew_num = None
        try:
            if pd.notna(crew_raw):
                n = int(float(str(crew_raw)))
                if 1 <= n <= 12:
                    crew_num = n
        except (ValueError, TypeError):
            pass

        login_to_crew[login] = crew_num

        if crew_num is not None:
            if crew_num not in teams:
                teams[crew_num] = {'srmet': None, 'members': []}
            if role == 'SRMET':
                teams[crew_num]['srmet'] = {'login': login, 'name': name}
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

        srmet = None
        if crew_num is not None and crew_num in teams:
            srmet = teams[crew_num].get('srmet')

        if srmet:
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
                rec['no_team_reason'] = 'Crew sin SRMET asignado (C / Ap)'
            else:
                rec['no_team_reason'] = f'Crew {crew_num} sin SRMET definido'
            no_srmet.append(rec)

    for key in srmet_groups:
        srmet_groups[key]['members'].sort(key=lambda x: x['days_til_non_compliant'])

    no_srmet.sort(key=lambda x: x['days_til_non_compliant'])

    return list(srmet_groups.values()), no_srmet
