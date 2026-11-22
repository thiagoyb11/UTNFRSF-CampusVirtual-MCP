# UTN FRSF · Campus Virtual MCP

Un servidor MCP para conectar asistentes de inteligencia artificial con el [Campus Virtual de la UTN Facultad Regional Santa Fe](https://campusvirtual.frsf.utn.edu.ar/).

Permite preguntarle a un asistente cosas como “¿qué trabajos vencen este mes?”, “descargá la bibliografía de Análisis Numérico” o “¿qué nota me pusieron en el TP 3?”, usando tu propia cuenta del campus.

> **Vista previa (0.2.0).** Las herramientas funcionan y se probaron contra el campus real, pero algunas solo para parte de su alcance. `get_server_info` informa el nivel de verificación de cada una. Ver [cambios](CHANGELOG.md).

## Qué puede hacer

| Área | Herramientas |
| --- | --- |
| Sesión y estado | `login`, `get_server_info` |
| Materias y agenda | `list_courses`, `list_monthly_activities` |
| Contenido | `get_course_resources`, `get_section_content`, `get_page_content`, `get_folder_content` |
| Avisos y foros | `list_forum_discussions`, `get_forum_discussion` |
| Materiales | `download_resources` (a `downloads/`) |
| Entregas | `get_submission_status`, `get_assignment_feedback`, `prepare_submission`, `upload_files`, `submit_assignment` |

Las entregas se hacen en pasos separados. `prepare_submission` valida los archivos en tu computadora, `upload_files` los sube a un área temporal y `submit_assignment` guarda la entrega y verifica en el campus cómo quedó. Ninguna herramienta reemplaza ni retira una entrega existente.

## Requisitos

- macOS o Linux (glibc 2.35 o superior, por ejemplo Ubuntu 22.04+). **Windows no está soportado**; usá WSL 2.
- Python 3.11 o posterior.
- Una cuenta del Campus Virtual UTN FRSF.

[Lightpanda](https://lightpanda.io/), el navegador que usa el servidor, se instala con el paquete de Python. No hace falta Chrome.

## Instalación

```bash
git clone https://github.com/thiagoyb11/UTNFRSF-CampusVirtual-MCP.git
cd UTNFRSF-CampusVirtual-MCP
python3 -m pip install --user .
python3 scripts/smoke_mcp.py --with-lightpanda
```

La última línea comprueba la instalación sin usar tu cuenta. Si tu Python pide `--break-system-packages`, agregalo al comando de pip. Para instalar las versiones exactas del lockfile, seguí la [guía de desarrollo](docs/desarrollo.md#instalación-con-versiones-exactas).

## Configuración

Copiá `.env.example` como `.env` en la carpeta del proyecto y completá tu usuario y contraseña:

```dotenv
UTN_CAMPUS_USERNAME=tu_usuario
UTN_CAMPUS_PASSWORD=tu_contraseña
```

Las credenciales quedan solo en ese archivo, que Git ignora. El asistente nunca las ve ni las pide como parámetro. Las demás variables son opcionales y están descritas en la [guía de desarrollo](docs/desarrollo.md#configurar-el-acceso).

## Conectar a un asistente

Agregá el servidor a la configuración MCP de tu cliente (Claude Desktop, Claude Code, etc.) con [examples/mcp.json](examples/mcp.json) como modelo. `cwd` debe ser la ruta absoluta de esta carpeta, porque desde ahí se lee `.env`, y `command` debe apuntar al Python donde lo instalaste:

```json
{
  "mcpServers": {
    "utnfrsf-campus": {
      "command": "python3",
      "args": ["-m", "utnfrsf_campus_mcp"],
      "cwd": "/ruta/absoluta/UTNFRSF-CampusVirtual-MCP"
    }
  }
}
```

## Limitaciones conocidas

- Solo se listan las materias de **Grado**.
- Los inventarios de materias con formato `onetopic`, algunos modos de descarga y las variantes de entrega distintas de “subir archivos” no están validados en todos los casos (F12, F13 y F26).
- Todo se probó con una sola cuenta de estudiante.
- Si el campus limita las solicitudes (HTTP 429), el servidor hace una pausa común a todas las herramientas y responde `CAMPUS_RATE_LIMITED` con los segundos que faltan. No repite operaciones solo.
- El servidor automatiza tu cuenta: revisá lo que el asistente propone antes de autorizar una entrega.

El detalle por herramienta está en `docs/` y el trabajo pendiente en el [inventario de funcionalidades](docs/funcionalidades-pendientes.md) y el [roadmap](roadmap.md).

## Desarrollo

Ver la [guía de desarrollo](docs/desarrollo.md): arquitectura, configuración completa, controles, CI y pruebas contra el campus.

## Licencia

[MIT](LICENSE). Proyecto independiente, sin afiliación oficial con la UTN.
