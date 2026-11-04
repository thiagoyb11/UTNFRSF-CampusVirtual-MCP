"""Catálogo del estado real de cada herramienta MCP (F45).

Este módulo es la fuente única del nivel de validación que publica `get_server_info`.
Al agregar, ampliar o verificar una herramienta, actualizá su entrada en el mismo
cambio que el código y que `docs/funcionalidades-pendientes.md`.

Reglas para mantenerlo:

- Una entrada por herramienta registrada; las pruebas fallan si falta o sobra alguna.
- `status` y `verified_on` solo cambian con evidencia documentada en `docs/`.
- `pending` enumera límites conocidos, no promesas de implementación.
- Los textos se escriben en español y no incluyen datos personales ni IDs privados.
"""

from datetime import date

from utnfrsf_campus_mcp.models import Capability

# Inventario detallado de pendientes, relativo a la raíz del repositorio.
PENDING_FEATURES_DOC = "docs/funcionalidades-pendientes.md"

# Fecha de la verificación real de login, materias, calendario, recursos,
# descargas y entregas documentada en docs/.
_CAMPUS_CHECK_2026_10_31 = date(2026, 10, 31)
_CAMPUS_CHECK_2026_11_04 = date(2026, 11, 4)


CAPABILITIES: tuple[Capability, ...] = (
    # --- Diagnóstico y sesión -------------------------------------------------
    Capability(
        tool="get_server_info",
        feature_ids=["F45"],
        effect="none",
        status="local_tests",
        verified_on=None,
        scope="Versión, zona horaria y estado declarado de cada herramienta registrada.",
        pending=[
            "No comprueba la sesión ni la disponibilidad actual del campus.",
        ],
        docs="docs/desarrollo.md",
    ),
    Capability(
        tool="login",
        feature_ids=["F42"],
        effect="session",
        status="campus_verified",
        verified_on=_CAMPUS_CHECK_2026_10_31,
        scope="Inicio de sesión con credenciales de .env y sesión compartida en memoria.",
        pending=[
            "Sin persistencia entre ejecuciones ni herramienta de estado o cierre de sesión.",
            "La recuperación de sesiones vencidas no se validó en el campus.",
        ],
        docs="docs/desarrollo.md",
    ),
    # --- Descubrimiento y agenda ----------------------------------------------
    Capability(
        tool="list_courses",
        feature_ids=["F01"],
        effect="campus_read",
        status="campus_verified",
        verified_on=_CAMPUS_CHECK_2026_10_31,
        scope="Materias de My courses → Grado, incluidos años anteriores.",
        pending=[
            "Sin búsqueda ni filtros (F02).",
            "Excluye Ingreso, Extensión y el catálogo general.",
        ],
        docs="docs/materias.md",
    ),
    Capability(
        tool="list_monthly_activities",
        feature_ids=["F07", "F08"],
        effect="campus_read",
        status="campus_verified",
        verified_on=_CAMPUS_CHECK_2026_10_31,
        scope="Eventos de un mes del calendario, con filtro opcional de vencimientos.",
        pending=[
            "Consulta un solo mes; sin rangos arbitrarios (F07) ni filtro por materia (F08).",
            "No determina qué trabajos siguen pendientes (F09).",
        ],
        docs="docs/calendario.md",
    ),
    # --- Materiales -----------------------------------------------------------
    Capability(
        tool="get_course_resources",
        feature_ids=["F12", "F13"],
        effect="campus_read",
        status="campus_partial",
        verified_on=_CAMPUS_CHECK_2026_10_31,
        scope="Enlaces de secciones, carpetas, recursos y consignas de una materia.",
        pending=[
            "Verificada en materias topics; falta validar onetopic (F12).",
            "Falta validar recursos individuales con forceview (F13).",
        ],
        docs="docs/recursos.md",
    ),
    Capability(
        tool="download_resources",
        feature_ids=["F16", "F17", "F18"],
        effect="local_write",
        status="campus_partial",
        verified_on=_CAMPUS_CHECK_2026_10_31,
        scope="Descarga de 1 a 10 archivos observados de un módulo a downloads/.",
        pending=[
            "La verificación real cubrió PDF y XLSX; otros tipos solo tienen pruebas locales.",
            "Sin lotes de varios módulos ni sincronización incremental (F16, F18).",
        ],
        docs="docs/descargas.md",
    ),
    # --- Entregas -------------------------------------------------------------
    Capability(
        tool="get_submission_status",
        feature_ids=["F05", "F10"],
        effect="campus_read",
        status="campus_verified",
        verified_on=_CAMPUS_CHECK_2026_11_04,
        scope="Estado (new sin entrega), archivos y evidencia textual de una tarea assign.",
        pending=[
            "No devuelve consigna completa ni plazos efectivos (F05, F10).",
            "Una tarea vencida no muestra su fecha límite en esta vista.",
        ],
        docs="docs/entregas.md",
    ),
    Capability(
        tool="prepare_submission",
        feature_ids=["F19"],
        effect="local_read",
        status="local_tests",
        verified_on=None,
        scope="Validación local de archivos con nombre, tamaño y SHA-256.",
        pending=[
            "No consulta los límites de la actividad en el campus (F19).",
        ],
        docs="docs/entregas.md",
    ),
    Capability(
        tool="upload_files",
        feature_ids=["F26", "F27"],
        effect="campus_write",
        status="campus_verified",
        verified_on=_CAMPUS_CHECK_2026_10_31,
        scope="Carga temporal a una tarea assign sin entrega previa, con bytes comprobados.",
        pending=[
            "Rechaza tareas con archivos existentes; sin edición ni reemplazo (F21).",
            "Recibos válidos 30 minutos y solo dentro del mismo proceso.",
        ],
        docs="docs/entregas.md",
    ),
    Capability(
        tool="submit_assignment",
        feature_ids=["F26", "F27"],
        effect="campus_write",
        status="campus_partial",
        verified_on=_CAMPUS_CHECK_2026_10_31,
        scope="Guardado de una carga verificada y confirmación final opcional.",
        pending=[
            "Real: guardado que envía directamente. Borradores y confirmación final, locales.",
            "Faltan otras configuraciones reales de tareas (F26).",
        ],
        docs="docs/entregas.md",
    ),
)


def capability_names() -> set[str]:
    """Devuelve los nombres de herramientas declarados en el catálogo."""
    return {capability.tool for capability in CAPABILITIES}
