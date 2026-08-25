# Mensajes de Slack — archivo editable

Este archivo controla **lo que dice cada mensaje de Slack** que envía la app.
Puedes editarlo con el Bloc de notas (o cualquier editor de texto) sin tocar
nada de código Python.

## Cómo funciona (léeme primero)

1. Abre este archivo, cambia el texto que hay **dentro de los recuadros de
   triple comilla** (` ``` `) y guarda.
2. No hace falta reiniciar la app: el archivo se lee **cada vez que se envía**.
3. No cambies los títulos de las secciones (`## recordatorio_srmet`, etc.) ni
   los subtítulos (`### Título`, `### Mensaje`, `### Formato de línea de curso`).
   Son las etiquetas que la app usa para encontrar cada texto.
4. Las palabras entre llaves, como `{crew}`, son **huecos** que la app rellena
   automáticamente. Puedes moverlos, repetirlos o quitarlos, pero escríbelos
   exactamente igual (en minúsculas y sin espacios).
5. Si algo se rompe (borras una sección, te dejas un ` ``` ` sin cerrar…), la app
   **no falla**: usa el texto por defecto y muestra un aviso en pantalla.

### Formato del texto

- `**negrita**` se convierte automáticamente al formato de Slack (`*negrita*`).
- `_cursiva_` funciona tal cual.
- Los saltos de línea se respetan.
- Una línea con `---` (tres guiones) parte el mensaje en dos bloques separados
  por una línea divisoria, como en el email.
- El **Título** aparece como cabecera destacada del mensaje (texto plano: la
  negrita no se aplica ahí, pero los emojis sí).

### Huecos disponibles

| Hueco | Qué contiene | Dónde funciona |
|---|---|---|
| `{srmet_name}` | Nombre completo del SRMET (`Apellido, Nombre`) | SRMET y felicitación |
| `{srmet_first_name}` | Solo el nombre de pila del SRMET | SRMET y felicitación |
| `{employee_name}` | Nombre completo del empleado | Recordatorio directo |
| `{employee_first_name}` | Solo el nombre de pila del empleado | Recordatorio directo |
| `{crew}` | Identificador del equipo (p. ej. `3`) | SRMET y felicitación |
| `{today}` | Fecha de hoy (dd/mm/aaaa) | Todas |
| `{count}` | Número de cursos pendientes del mensaje | SRMET y directo |
| `{course_list}` | La lista completa de cursos ya formateada | SRMET y directo |

### Huecos de la línea de curso

Se usan **solo** dentro de `### Formato de línea de curso`. La app repite esa
línea una vez por curso (ordenados del más urgente al menos urgente) y el
resultado es lo que se pega en `{course_list}`.

| Hueco | Qué contiene |
|---|---|
| `{course_title}` | Nombre de la formación |
| `{days}` | Días que faltan para vencer (negativo si ya venció) |
| `{emoji}` | Semáforo de urgencia: 🔴 vencido · 🟠 <7 días · 🟡 <14 días · 🔵 <21 días |
| `{urgencia}` | Texto de urgencia: `NON COMPLIANT`, `CRÍTICO`, `URGENTE`, `ATENCIÓN` |
| `{name}` | Nombre completo del técnico (solo en el mensaje al SRMET) |
| `{first_name}` | Nombre de pila del técnico (solo en el mensaje al SRMET) |
| `{login}` | Login del técnico (solo en el mensaje al SRMET) |

---

## recordatorio_srmet

Mensaje que recibe el **SRMET** con los cursos pendientes de su equipo.
Equivale al email `template_table.html`.

### Título

```text
🚨 Safety Training — Equipo {crew}
```

### Mensaje

```text
Hola **{srmet_first_name}**, tu equipo tiene **{count}** curso(s) de Safety Training próximos a vencer o ya vencidos:

{course_list}

---
Te pedimos que hagas seguimiento personal con cada técnico listado para que completen sus cursos. Si algún curso no puede completarse a tiempo, contáctanos para buscar una solución conjunta.

Muchas gracias,
**{signature}** · {today}
```

### Formato de línea de curso

```text
{emoji} **{name}** — {course_title} · `{days} d`
```

---

## recordatorio_directo

Mensaje que recibe **directamente el empleado** cuando su equipo no tiene SRMET
asignado. Equivale al email `template_employee_direct.html`.

### Título

```text
🚨 Safety Training — Tienes cursos pendientes
```

### Mensaje

```text
Hola **{employee_first_name}**, tienes **{count}** curso(s) de Safety Training próximos a caducar o ya caducados:

{course_list}

---
Te pedimos que completes los cursos antes de la fecha de vencimiento. Si alguno no puede completarse a tiempo, por favor contacta con nosotros para buscar una solución conjunta.

Muchas gracias,
**{signature}** · {today}
```

### Formato de línea de curso

```text
{emoji} {course_title} · `{days} d` — _{urgencia}_
```

---

## felicitacion

Mensaje de enhorabuena para el SRMET cuyo equipo está **al día**.
Equivale al email `template_congrats.html`. Aquí no hay lista de cursos.

### Título

```text
✅ Safety Training — Equipo {crew} al día
```

### Mensaje

```text
¡Enhorabuena **{srmet_first_name}**! 🎉

Tu equipo no tiene ningún curso de Safety Training pendiente en los próximos 21 días. Sois un referente en compliance — ¡seguid así! 💪

Muchas gracias,
**{signature}** · {today}
```

