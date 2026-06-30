import os, json, time
from flask import Flask, request, redirect, url_for, render_template, flash, Response, stream_with_context, session
from werkzeug.utils import secure_filename
from datetime import date
import config
from processor import process_csv, load_teams, assign_teams, group_no_srmet_by_employee
from email_sender import send_email

app = Flask(__name__)
app.secret_key = config.SECRET_KEY
os.makedirs(config.UPLOAD_FOLDER, exist_ok=True)

_state = {'results': None, 'pending_send': None, 'send_meta': None}


def is_test_mode():
    return session.get('test_mode', True)

TEMPLATE_LABELS = {
    'template_table': 'Tabla limpia (por urgencia)',
}


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
        _state['results'] = {
            'filtered': filtered,
            'srmet_groups': srmet_groups,
            'no_srmet': no_srmet,
            'no_srmet_employees': no_srmet_employees,
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

    return render_template('preview.html',
        srmet_groups=data['srmet_groups'],
        no_srmet_employees=data['no_srmet_employees'],
        no_srmet_previews=no_srmet_previews,
        email_previews=email_previews,
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

    selected_template = request.form.get('template', config.DEFAULT_TEMPLATE)
    send_no_srmet = request.form.get('send_no_srmet') == 'on'
    today_str = date.today().strftime('%d/%m/%Y')
    week_num = date.today().isocalendar()[1]

    email_list = []

    # Emails to SRMETs
    for group in data['srmet_groups']:
        html_body = render_template(f'emails/{selected_template}.html',
            srmet_name=group['srmet_name'],
            crew=group['crew'],
            members=group['members'],
            today=today_str
        )
        email_list.append({
            'to_email': group['srmet_email'],
            'subject': f"🚨 Cursos de Safety Training pendientes - Acción requerida",
            'html_body': html_body,
            'label': f"SRMET Equipo {group['crew']} · {group['srmet_name']}",
            'crew': group['crew']
        })

    # Direct emails to employees without SRMET (optional)
    if send_no_srmet:
        for emp in data['no_srmet_employees']:
            html_body = render_template('emails/template_employee_direct.html',
                employee_name=emp['name'],
                courses=emp['courses'],
                today=today_str
            )
            email_list.append({
                'to_email': emp['email'],
                'subject': f"🚨 Cursos de Safety Training pendientes - Acción requerida",
                'html_body': html_body,
                'label': f"Directo · {emp['name']}",
                'crew': None
            })

    _state['pending_send'] = email_list
    _state['send_meta'] = {
        'template_label': TEMPLATE_LABELS.get(selected_template, selected_template),
    }

    _state['send_test_mode'] = is_test_mode()

    return render_template('sending.html',
        total=len(email_list),
        test_mode=is_test_mode(),
        test_email=config.TEST_EMAIL
    )


@app.route('/send-stream')
def send_stream():
    def generate():
        email_list = _state.get('pending_send') or []
        meta = _state.get('send_meta') or {}
        test_mode = _state.get('send_test_mode', True)
        results = []

        for i, item in enumerate(email_list):
            display_email = config.TEST_EMAIL if test_mode else item['to_email']

            # Notify browser that this email is about to be sent
            yield "event: progress\ndata: {}\n\n".format(json.dumps({
                'step': i + 1,
                'total': len(email_list),
                'label': item['label'],
                'to_email': display_email,
                'status': 'sending'
            }))

            success, error = send_email(item['to_email'], item['subject'], item['html_body'], test_mode=test_mode)
            result = {
                'label': item['label'],
                'crew': item.get('crew'),
                'to_email': display_email,
                'success': success,
                'error': error
            }
            results.append(result)

            # Notify browser of the result
            yield "event: progress\ndata: {}\n\n".format(json.dumps({
                'step': i + 1,
                'total': len(email_list),
                'label': item['label'],
                'to_email': display_email,
                'success': success,
                'error': error
            }))

            if i < len(email_list) - 1:
                time.sleep(config.EMAIL_SEND_DELAY)

        _state['pending_send'] = None
        yield "event: done\ndata: {}\n\n".format(json.dumps({
            'results': results,
            'template_label': meta.get('template_label', '')
        }))

    return Response(
        stream_with_context(generate()),
        content_type='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'}
    )


if __name__ == '__main__':
    app.run(debug=True, port=5000, threaded=True)
