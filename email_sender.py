import config


def _friendly_error(e):
    msg = str(e)
    if '-2147221008' in msg or 'CoInitialize' in msg:
        return (
            "Outlook no inicializó COM correctamente. "
            "Asegúrate de que Microsoft Outlook está ABIERTO en tu PC "
            "y reinicia la app con: python app.py"
        )
    if 'Application' in msg or '-2147221005' in msg or 'RPC' in msg:
        return (
            "No se pudo conectar a Microsoft Outlook. "
            "Abre Outlook antes de intentar enviar correos."
        )
    if 'permission' in msg.lower() or 'access' in msg.lower():
        return (
            f"Outlook bloqueó el envío automático por seguridad. "
            "Ve a Configuración de Outlook > Centro de confianza y permite el acceso programático. "
            f"(Detalle técnico: {msg})"
        )
    return (
        f"Error inesperado al enviar el correo: {msg}. "
        "Comprueba que Outlook está instalado, abierto y con sesión activa."
    )


def send_email(to_email, subject, html_body, test_mode=True):
    try:
        import pythoncom
        import win32com.client
        pythoncom.CoInitialize()
        try:
            outlook = win32com.client.Dispatch("Outlook.Application")
            mail = outlook.CreateItem(0)
            if test_mode:
                mail.To = config.TEST_EMAIL
                mail.Subject = f"[TEST] {subject}"
            else:
                mail.To = to_email
                mail.Subject = subject
            mail.HTMLBody = html_body
            mail.Send()
            return True, None
        finally:
            pythoncom.CoUninitialize()
    except ImportError:
        return False, (
            "pywin32 no está instalado. "
            "Abre una terminal en la carpeta del proyecto y ejecuta: pip install pywin32"
        )
    except Exception as e:
        return False, _friendly_error(e)


def send_all_emails(email_list):
    """
    email_list: list of dicts with keys:
      to_email, subject, html_body, label (display name for the result table)
    """
    results = []
    for item in email_list:
        success, error = send_email(item['to_email'], item['subject'], item['html_body'])
        results.append({
            'label': item.get('label', item.get('srmet_name', '')),
            'crew': item.get('crew'),
            'to_email': config.TEST_EMAIL if config.TEST_MODE else item['to_email'],
            'success': success,
            'error': error
        })
    return results
