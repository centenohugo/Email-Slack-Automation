import os, json, time
from flask import Flask, request, redirect, url_for, render_template, flash, Response, stream_with_context, session
from werkzeug.utils import secure_filename
from datetime import date
import config
from processor import process_csv, load_teams, assign_teams, group_no_srmet_by_employee, get_compliant_srmets
from email_sender import send_email
from slack_sender import send_slack
import slack_message

app = Flask(__name__)
app.secret_key = config.SECRET_KEY
os.makedirs(config.UPLOAD_FOLDER, exist_ok=True)

_state = {'results': None, 'pending_send': None, 'send_meta': None}


def is_test_mode():
    return session.get('test_mode', True)


@app.context_processor
def inject_globals():
    """Valores disponibles en todas las plantillas (paginas y emails)."""
    buildings = config.BUILDING_FILTER or ()
    if isinstance(buildings, str):
        buildings = (buildings,)
    return {
        'days_threshold': config.DAYS_THRESHOLD,
        'buildings': ' / '.join(buildings) or 'todos',
        'site_name': config.SITE_NAME,
        'signature': config.SIGNATURE,
        'report_url': config.REPORT_URL,
    }

CHANNEL_LABELS = {
    'email': 'Email (Outlook)',
    'slack': 'Slack',
    'both': 'Email + Slack',
}


def _channels_from_form(form):
    """Devuelve la lista de canales elegidos en el formulario. Email por defecto."""
    choice = (form.get('channels') or 'email').strip().lower()
    if choice == 'slack':
        return ['slack']
    if choice == 'both':
        return ['email', 'slack']
    return ['email']


def _slack_preview_text(built):
    """Convierte los bloques de Slack en texto plano legible para el preview."""
    parts = []
    for block in built.get('blocks', []):
        btype = block.get('type')
        if btype == 'divider':
            parts.append('─' * 40)
        else:
            txt = (block.get('text') or {}).get('text', '')
            if btype == 'header':
                txt = txt.upper()
            parts.append(txt)
    return '\n\n'.join(p for p in parts if p)


@app.route('/toggle-test', methods=['POST'])
def toggle_test():
    session['test_mode'] = not is_test_mode()
    return redirect(request.referrer or url_for('index'))


@app.route('/')
def index():
    return render_template('index.html',
        teams_file=config.TEAMS_FILE,
        test_mode=is_test_mode(),
        test_email=config.TEST_EMAIL
    )


@app.route('/upload', methods=['POST'])
def upload():
    f = request.files.get('csv_file')
    if not f or f.filename == '':
        flash('No se seleccionó ningún archivo.', 'error')
        return redirect(url_for('index'))
    if not f.filename.lower().endswith('.csv'):
        flash('Solo se admiten archivos .csv', 'error')
        return redirect(url_for('index'))

    filename = secure_filename(f.filename)
    filepath = os.path.join(config.UPLOAD_FOLDER, filename)
    f.save(filepath)

    try:
        filtered = process_csv(filepath)
        teams, login_to_crew = load_teams()
        srmet_groups, no_srmet = assign_teams(filtered, teams, login_to_crew)
        no_srmet_employees = group_no_srmet_by_employee(no_srmet)
        compliant_srmets = get_compliant_srmets(teams, srmet_groups)
        _state['results'] = {
            'filtered': filtered,
            'srmet_groups': srmet_groups,
            'no_srmet': no_srmet,
            'no_srmet_employees': no_srmet_employees,
            'compliant_srmets': compliant_srmets,
            'filename': f.filename
        }
    except Exception as e:
        flash(f'Error procesando el CSV: {e}', 'error')
        return redirect(url_for('index'))
    finally:
        if os.path.exists(filepath):
            os.remove(filepath)

    return redirect(url_for('results'))


@app.route('/results')
def results():
    data = _state.get('results')
    if not data:
        flash('No hay datos cargados. Sube un CSV primero.', 'info')
        return redirect(url_for('index'))

    today_str = date.today().strftime('%d/%m/%Y')

    return render_template('results.html',
        filtered=data['filtered'],
        srmet_groups=data['srmet_groups'],
        no_srmet=data['no_srmet'],
        no_srmet_employees=data['no_srmet_employees'],
        compliant_srmets=data.get('compliant_srmets', []),
        today=today_str,
        filename=data['filename'],
        test_mode=is_test_mode(),
        test_email=config.TEST_EMAIL
    )


@app.route('/preview')
def preview():
    data = _state.get('results')
    if not data:
        flash('No hay datos cargados. Sube un CSV primero.', 'info')
        return redirect(url_for('index'))

    today_str = date.today().strftime('%d/%m/%Y')

    # Pre-render SRMET email previews
    email_previews = []
    for group in data['srmet_groups']:
        html = render_template('emails/template_table.html',
            srmet_name=group['srmet_name'],
            crew=group['crew'],
            members=group['members'],
            today=today_str
        )
        email_previews.append({
            'srmet_login': group['srmet_login'],
            'srmet_name': group['srmet_name'],
            'crew': group['crew'],
            'html': html
        })

    # Pre-render direct employee previews (sin SRMET)
    no_srmet_previews = {}
    for emp in data['no_srmet_employees']:
        no_srmet_previews[emp['login']] = render_template(
            'emails/template_employee_direct.html',
            employee_name=emp['name'],
            courses=emp['courses'],
            today=today_str
        )

    # Pre-render congrats previews (SRMETs whose team is fully compliant)
    congrats_previews = []
    for c in data.get('compliant_srmets', []):
        html = render_template('emails/template_congrats.html',
            srmet_name=c['srmet_name'],
            crew=c['crew']
        )
        congrats_previews.append({
            'srmet_login': c['srmet_login'],
            'srmet_name': c['srmet_name'],
            'crew': c['crew'],
            'html': html
        })

    # Pre-render Slack message previews (se lee SLACK_MESSAGE.md en cada visita)
    slack_warnings = []
    messages, slack_warnings = slack_message.load_messages()
    slack_previews = {}
    for group in data['srmet_groups']:
        built = slack_message.build_srmet_message(
            group['srmet_name'], group['crew'], group['members'], today_str, messages=messages)
        slack_previews['srmet:' + group['srmet_login']] = _slack_preview_text(built)
    for emp in data['no_srmet_employees']:
        built = slack_message.build_employee_message(
            emp['name'], emp['courses'], today_str, messages=messages)
        slack_previews['emp:' + emp['login']] = _slack_preview_text(built)
    for c in data.get('compliant_srmets', []):
        built = slack_message.build_congrats_message(
            c['srmet_name'], c['crew'], today_str, messages=messages)
        slack_previews['congrats:' + c['srmet_login']] = _slack_preview_text(built)

    return render_template('preview.html',
        slack_previews=slack_previews,
        slack_warnings=slack_warnings,
        srmet_groups=data['srmet_groups'],
        no_srmet_employees=data['no_srmet_employees'],
        no_srmet_previews=no_srmet_previews,
        email_previews=email_previews,
        congrats_previews=congrats_previews,
        today=today_str,
        filename=data['filename'],
        test_mode=is_test_mode(),
        test_email=config.TEST_EMAIL
    )


@app.route('/send', methods=['POST'])
def send():
    data = _state.get('results')
    if not data:
        flash('No hay datos. Sube un CSV primero.', 'error')
        return redirect(url_for('index'))

    # Destinatarios marcados uno a uno en el preview ('srmet:login', 'congrats:login', 'emp:login')
    selected = set(request.form.getlist('recipients'))
    if not selected:
        flash('No has seleccionado ningun destinatario.', 'error')
        return redirect(url_for('preview'))
    channels = _channels_from_form(request.form)
    today_str = date.today().strftime('%d/%m/%Y')

    send_list = []

    def add(channel, label, crew, to_email, extra):
        item = {
            'channel': channel,
            'label': label if channel == 'email' else label + ' · Slack',
            'crew': crew,
            'to_email': to_email,
        }
        item.update(extra)
        send_list.append(item)

    # SRMETs con cursos pendientes
    for group in data['srmet_groups']:
        if 'srmet:' + group['srmet_login'] not in selected:
            continue
        label = f"SRMET Equipo {group['crew']} · {group['srmet_name']}"
        if 'email' in channels:
            html_body = render_template('emails/template_table.html',
                srmet_name=group['srmet_name'],
                crew=group['crew'],
                members=group['members'],
                today=today_str
            )
            add('email', label, group['crew'], group['srmet_email'], {
                'subject': "🚨 Cursos de Safety Training pendientes - Acción requerida",
                'html_body': html_body,
            })
        if 'slack' in channels:
            add('slack', label, group['crew'], group['srmet_email'], {
                'to_slack': group['srmet_login'],
                'slack_kind': 'srmet',
                'slack_params': {
                    'srmet_name': group['srmet_name'],
                    'crew': group['crew'],
                    'members': group['members'],
                },
            })

    # Felicitación a SRMETs con el equipo al día
    for c in data.get('compliant_srmets', []):
        if 'congrats:' + c['srmet_login'] not in selected:
            continue
        label = f"✅ Equipo {c['crew']} · {c['srmet_name']}"
        if 'email' in channels:
            html_body = render_template('emails/template_congrats.html',
                srmet_name=c['srmet_name'],
                crew=c['crew']
            )
            add('email', label, c['crew'], c['srmet_email'], {
                'subject': "✅ Safety Training - Tu equipo está al día",
                'html_body': html_body,
            })
        if 'slack' in channels:
            add('slack', label, c['crew'], c['srmet_email'], {
                'to_slack': c['srmet_login'],
                'slack_kind': 'congrats',
                'slack_params': {
                    'srmet_name': c['srmet_name'],
                    'crew': c['crew'],
                },
            })

    # Avisos directos a empleados sin SRMET (solo los marcados)
    for emp in data['no_srmet_employees']:
        if 'emp:' + emp['login'] not in selected:
            continue
        label = f"Directo · {emp['name']}"
        if 'email' in channels:
            html_body = render_template('emails/template_employee_direct.html',
                employee_name=emp['name'],
                courses=emp['courses'],
                today=today_str
            )
            add('email', label, None, emp['email'], {
                'subject': "🚨 Cursos de Safety Training pendientes - Acción requerida",
                'html_body': html_body,
            })
        if 'slack' in channels:
            add('slack', label, None, emp['email'], {
                'to_slack': emp['login'],
                'slack_kind': 'employee',
                'slack_params': {
                    'employee_name': emp['name'],
                    'courses': emp['courses'],
                },
            })

    if not send_list:
        flash('Los destinatarios seleccionados ya no estan disponibles. Revisa el preview.', 'error')
        return redirect(url_for('preview'))

    _state['pending_send'] = send_list
    _state['send_meta'] = {
        'channel_label': CHANNEL_LABELS.get(
            'both' if len(channels) > 1 else channels[0], channels[0]),
        'today': today_str,
    }

    _state['send_test_mode'] = is_test_mode()

    return render_template('sending.html',
        total=len(send_list),
        test_mode=is_test_mode(),
        test_email=config.TEST_EMAIL
    )


def _build_slack_content(item, today_str, messages):
    kind = item.get('slack_kind')
    p = item.get('slack_params') or {}
    if kind == 'srmet':
        return slack_message.build_srmet_message(
            p['srmet_name'], p['crew'], p['members'], today_str, messages=messages)
    if kind == 'congrats':
        return slack_message.build_congrats_message(
            p['srmet_name'], p['crew'], today_str, messages=messages)
    return slack_message.build_employee_message(
        p['employee_name'], p['courses'], today_str, messages=messages)


@app.route('/send-stream')
def send_stream():
    def generate():
        send_list = _state.get('pending_send') or []
        meta = _state.get('send_meta') or {}
        test_mode = _state.get('send_test_mode', True)
        today_str = meta.get('today') or date.today().strftime('%d/%m/%Y')
        results = []

        # SLACK_MESSAGE.md se lee aquí, en el momento del envío
        slack_messages, slack_warnings = None, []
        if any(i.get('channel') == 'slack' for i in send_list):
            slack_messages, slack_warnings = slack_message.load_messages()

        for i, item in enumerate(send_list):
            display_email = config.TEST_EMAIL if test_mode else item['to_email']

            # Avisar al navegador de que este envío empieza
            yield "event: progress\ndata: {}\n\n".format(json.dumps({
                'step': i + 1,
                'total': len(send_list),
                'label': item['label'],
                'to_email': display_email,
                'status': 'sending'
            }))

            if item['channel'] == 'slack':
                content = _build_slack_content(item, today_str, slack_messages)
                success, error = send_slack(item['to_slack'], content, test_mode=test_mode)
            else:
                success, error = send_email(item['to_email'], item['subject'],
                                            item['html_body'], test_mode=test_mode)

            result = {
                'label': item['label'],
                'crew': item.get('crew'),
                'channel': item['channel'],
                'to_email': display_email,
                'success': success,
                'error': error
            }
            results.append(result)

            # Avisar al navegador del resultado
            yield "event: progress\ndata: {}\n\n".format(json.dumps({
                'step': i + 1,
                'total': len(send_list),
                'label': item['label'],
                'to_email': display_email,
                'success': success,
                'error': error
            }))

            if i < len(send_list) - 1:
                delay = config.SLACK_SEND_DELAY if item['channel'] == 'slack' else config.EMAIL_SEND_DELAY
                time.sleep(delay)

        _state['pending_send'] = None
        yield "event: done\ndata: {}\n\n".format(json.dumps({
            'results': results,
            'channel_label': meta.get('channel_label', ''),
            'slack_warnings': slack_warnings
        }))

    return Response(
        stream_with_context(generate()),
        content_type='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'}
    )


if __name__ == '__main__':
    app.run(debug=True, port=config.PORT, threaded=True)
