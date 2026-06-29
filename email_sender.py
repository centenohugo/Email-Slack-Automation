import config


def send_email(to_email, subject, html_body):
    try:
        import win32com.client
        outlook = win32com.client.Dispatch("Outlook.Application")
        mail = outlook.CreateItem(0)

        if config.TEST_MODE:
            mail.To = config.TEST_EMAIL
            mail.Subject = f"[TEST] {subject}"
        else:
            mail.To = to_email
            mail.Subject = subject

        mail.HTMLBody = html_body
        mail.Send()
        return True, None
    except ImportError:
        return False, "pywin32 no instalado. Ejecuta: pip install pywin32"
    except Exception as e:
        return False, str(e)


def send_all_emails(email_list):
    """email_list: list of dicts with keys to_email, subject, html_body, srmet_name"""
    results = []
    for item in email_list:
        success, error = send_email(item['to_email'], item['subject'], item['html_body'])
        results.append({
            'srmet_name': item['srmet_name'],
            'crew': item.get('crew'),
            'to_email': config.TEST_EMAIL if config.TEST_MODE else item['to_email'],
            'success': success,
            'error': error
        })
    return results
