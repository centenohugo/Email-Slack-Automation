# Training Reminder

App web local que lee el informe de formación en CSV, agrupa a cada persona con
el SRMET de su equipo y envía los recordatorios por **correo (Outlook)** o por
**Slack**.

Funciona entera en tu ordenador. No hay servidor ni base de datos.

---

## 1. Instalación (solo la primera vez)

### Requisitos

- **Windows** (el envío de correo usa la aplicación de escritorio de Outlook).
- **Python 3.10 o superior**. Para comprobar si lo tienes, abre una terminal
  (tecla Windows → escribe `cmd` → Enter) y ejecuta:

  ```
  python --version
  ```

  Si dice que no se reconoce el comando, descárgalo de
  <https://www.python.org/downloads/> y **marca la casilla "Add Python to PATH"**
  durante la instalación.

### Pasos

```
cd ruta\a\automated-reminder
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Después abre el archivo `.env` con el Bloc de notas y rellena tus datos
(mínimo `SECRET_KEY` y `EMAIL_DOMAIN`). Cada variable está explicada dentro del
propio archivo.

> **Atajo:** si haces doble clic en `iniciar.bat`, hace todo lo anterior solo:
> instala Python si falta, crea el entorno, instala las dependencias, crea el
> `.env` y abre el navegador.

---

## 2. Arrancar la app

Cada vez que quieras usarla, en la terminal:

```
cd ruta\a\automated-reminder
venv\Scripts\activate
python app.py
```

Luego abre <http://localhost:5005> en el navegador.

Para pararla: `Ctrl + C` en la terminal.

---

## 3. Cómo se usa

1. **Cargar CSV.** La pantalla inicial te da el enlace al panel del informe.
   Exporta el informe a CSV y súbelo.
2. **Abrir Outlook.** Tiene que estar abierto el **programa de escritorio**;
   el Outlook del navegador no vale. En esta pantalla también puedes revisar
   los datos que ha leído del CSV.
3. **Preview y envío.** Eliges canal (correo / Slack / ambos), marcas o
   desmarcas destinatarios uno a uno y envías.

La app arranca siempre en **modo test**: todo se envía a tu propio correo con
el prefijo `[TEST]`. El botón de arriba a la derecha cambia a envío real.

---

## 4. Estructura del proyecto

Esto es lo que hace cada archivo. Es la chuleta para saber **qué pedir que se
cambie y dónde**:

| Archivo | Qué hace |
|---|---|
| `app.py` | El servidor web. Define las pantallas (`/`, `/results`, `/preview`, `/send`) y decide a quién se envía. |
| `config.py` | Lee la configuración del `.env`. Aquí no se toca nada: los valores van en el `.env`. |
| `processor.py` | Lee el CSV, filtra los cursos que caducan y asigna cada persona a su equipo y su SRMET. |
| `email_sender.py` | Envía un correo a través de Outlook. |
| `slack_sender.py` | Envía un mensaje directo por Slack. |
| `slack_message.py` | Convierte `SLACK_MESSAGE.md` en el mensaje que se manda. |
| `build_teams.py` | Utilidad suelta: genera `Teams.xlsx` a partir de la rota anual. Se usa una vez al año. |
| `templates/` | Las pantallas web (`index`, `results`, `preview`, `sending`). |
| `templates/emails/` | El diseño de los correos que se envían. |
| `static/style.css` | Los estilos de las pantallas web. |
| `SLACK_MESSAGE.md` | **El texto de los mensajes de Slack.** Editable a mano, sin tocar código. |
| `.env` | Tus claves y tu configuración. **Nunca se sube al repositorio.** |

### Cómo pedir cambios a un asistente de IA

Di **qué** quieres y **en qué pantalla**; el archivo lo deduce de la tabla de
arriba. Ejemplos que funcionan bien:

- *"En la pantalla de preview (`templates/preview.html`), añade un buscador para
  filtrar destinatarios por nombre."*
- *"En `processor.py`, que los cursos ya caducados salgan siempre los primeros."*
- *"En `templates/emails/template_table.html`, cambia el color de la cabecera."*
- *"En `app.py`, añade una pantalla que exporte a Excel los datos filtrados."*

Dos avisos útiles al pedir cambios:

- El texto de los correos está en `templates/emails/`, el de Slack en
  `SLACK_MESSAGE.md`. No están en el código Python.
- Nada de configuración se escribe en el código: va al `.env` y se lee desde
  `config.py`.

---

## 5. Tareas habituales

### Cambiar el texto de los mensajes de Slack

Abre `SLACK_MESSAGE.md`, edita y guarda. **No hace falta reiniciar la app**: se
lee en cada envío. Los `{placeholders}` disponibles están explicados dentro del
propio archivo.

### Actualizar los equipos (una vez al año, o cuando cambie la rota)

```
python build_teams.py ruta\a\la\rota.xlsm
```

Genera el `Teams.xlsx` que usa la app. Las hojas que lee se configuran con
`ROTA_MAIN_SHEET` y `ROTA_EXTRA_SHEET` en el `.env`.

### Renovar el token de Slack

Edita `SLACK_BOT_TOKEN` en el `.env` y reinicia la app.

El bot necesita estos permisos (scopes): `users:read`, `users:read.email`,
`chat:write`, `im:write`. Si añades un scope nuevo, hay que pulsar **"Reinstall
to Workspace"** en api.slack.com y copiar el token **nuevo**: los scopes no se
aplican a un token ya emitido.

---

## 6. Si algo falla

| Síntoma | Qué hacer |
|---|---|
| `python` no se reconoce | Python no está instalado o no está en el PATH. Reinstálalo marcando "Add Python to PATH". |
| "No se pudo conectar a Microsoft Outlook" | Abre la aplicación de escritorio de Outlook y reintenta. El Outlook del navegador no sirve. |
| "No se encuentra el fichero de equipos" | Falta `Teams.xlsx`. Genéralo con `build_teams.py` (ver arriba). |
| "El CSV no tiene el formato esperado" | El informe exportado no trae las columnas esperadas. El mensaje de error lista las que sí ha encontrado. |
| "Al bot de Slack le falta el permiso X" | Añade ese scope en api.slack.com, pulsa "Reinstall to Workspace" y copia el token nuevo al `.env`. |
| Slack dice "usuario no encontrado" | Esa persona no tiene cuenta de Slack con ese correo. El resto del envío continúa igual. |
| El puerto 5005 está ocupado | Cambia `PORT` en el `.env`. |

---

## 7. Datos personales

El repositorio **no contiene datos de personas**. Los siguientes archivos se
quedan siempre en tu ordenador (están en `.gitignore`):

- `.env` — claves y configuración.
- `sample/Teams.xlsx` — nombres y logins reales.
- Los informes `Training_Report*.csv` descargados del panel.
- La rota anual `.xlsm` y la carpeta `uploads/`.

Si añades algún archivo nuevo con nombres, logins o correos, **añádelo al
`.gitignore` antes de hacer commit**.
