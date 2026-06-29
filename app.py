import os
from flask import Flask, request, redirect, url_for, render_template, flash
from werkzeug.utils import secure_filename
from datetime import date
import config
from processor import process_csv, load_teams, assign_teams
from email_sender import send_all_emails

app = Flask(__name__)
app.secret_key = config.SECRET_KEY
os.makedirs(config.UPLOAD_FOLDER, exist_ok=True)

_state = {'results': None}

TEMPLATE_LABELS = {
    'template_table': 'A — Tabla limpia',
    'template_cards': 'B — Cards por persona',
    'template_minimal': 'C — Ultra minimalista',
}


@app.route('/')
def index():
    return render_template('index.html',
        teams_file=config.TEAMS_FILE,
        test_mode=config.TEST_MODE,
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
        _state['results'] = {
            'filtered': filtered,
            'srmet_groups': srmet_groups,
            'no_srmet': no_srmet,
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
    templates = list(TEMPLATE_LABELS.keys())

    email_previews = {}
    for tmpl in templates:
        previews = []
        for group in data['srmet_groups']:
            html = render_template(f'emails/{tmpl}.html',
                srmet_name=group['srmet_name'],
                crew=group['crew'],
                members=group['members'],
                today=today_str
            )
            previews.append({
                'srmet_login': group['srmet_login'],
                'srmet_name': group['srmet_name'],
                'crew': group['crew'],
                'html': html
            })
        email_previews[tmpl] = previews

    return render_template('results.html',
        filtered=data['filtered'],
        srmet_groups=data['srmet_groups'],
        no_srmet=data['no_srmet'],
        email_previews=email_previews,
        template_labels=TEMPLATE_LABELS,
        today=today_str,
        filename=data['filename'],
        test_mode=config.TEST_MODE,
        test_email=config.TEST_EMAIL,
        templates=templates
    )


@app.route('/send', methods=['POST'])
def send():
    data = _state.get('results')
    if not data:
        flash('No hay datos. Sube un CSV primero.', 'error')
        return redirect(url_for('index'))

    selected_template = request.form.get('template', config.DEFAULT_TEMPLATE)
    today_str = date.today().strftime('%d/%m/%Y')
    week_num = date.today().isocalendar()[1]

    email_list = []
    for group in data['srmet_groups']:
        html_body = render_template(f'emails/{selected_template}.html',
            srmet_name=group['srmet_name'],
            crew=group['crew'],
            members=group['members'],
            today=today_str
        )
        email_list.append({
            'to_email': group['srmet_email'],
            'subject': f"RME ZAZ1 | Formaciones próximas a caducar — Semana {week_num} | Crew {group['crew']}",
            'html_body': html_body,
            'srmet_name': group['srmet_name'],
            'crew': group['crew']
        })

    send_results = send_all_emails(email_list)

    return render_template('done.html',
        send_results=send_results,
        test_mode=config.TEST_MODE,
        test_email=config.TEST_EMAIL,
        template_label=TEMPLATE_LABELS.get(selected_template, selected_template)
    )


if __name__ == '__main__':
    app.run(debug=True, port=5000)
