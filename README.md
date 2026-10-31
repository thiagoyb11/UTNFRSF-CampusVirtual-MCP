# UTN FRSF · Campus Virtual MCP

Un servidor [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) para conectar asistentes de IA con el [Campus Virtual de la UTN Facultad Regional Santa Fe](https://campusvirtual.frsf.utn.edu.ar/), usando **Lightpanda** para navegar e interactuar con la plataforma.

La idea es poder consultar vencimientos, organizar el calendario, descargar bibliografía y entregar trabajos prácticos desde un asistente compatible con MCP, utilizando la cuenta del estudiante.

> **Estado: planificación.** Este repositorio contiene la documentación inicial y la licencia. Las herramientas, la autenticación y la integración con Lightpanda todavía no están implementadas ni probadas con una sesión del campus.

## Qué queremos poder hacer

- **Materias:** consultar los cursos disponibles para la cuenta y sus actividades.
- **Vencimientos:** reunir fechas de entrega, aperturas y cierres de actividades.
- **Calendario:** consultar eventos por materia y por rango de fechas.
- **Bibliografía:** encontrar y descargar apuntes, guías y archivos de las materias.
- **Trabajos prácticos:** consultar consignas y estado de entrega, preparar archivos y enviarlos cuando el usuario lo solicite.

Ejemplos de pedidos que el proyecto busca soportar:

> “¿Qué trabajos prácticos vencen esta semana? Incluí la materia y el enlace de cada actividad”.
>
> “Descargá la bibliografía de la unidad 3 de Sistemas Operativos”.
>
> “Mostrame el calendario de las próximas dos semanas”.
>
> “Entregá este PDF en el TP 2 de la materia que seleccioné y verificá que haya quedado enviado”.

Estos ejemplos expresan el objetivo del proyecto; todavía no son funcionalidades disponibles.

## Cómo funcionará

El asistente se conectará a un servidor MCP propio, que expondrá operaciones académicas concretas. Ese servidor resolverá cada operación mediante un adaptador de Lightpanda y una sesión autenticada en el campus.

| Capa | Responsabilidad |
| --- | --- |
| Asistente / host MCP | Interpretar el pedido, seleccionar herramientas y presentar los resultados. |
| Servidor MCP del proyecto | Publicar herramientas con parámetros definidos y validar las solicitudes. |
| Servicios del campus | Resolver materias, fechas, recursos y entregas; verificar el resultado de cada operación. |
| Adaptador de Lightpanda | Administrar navegación, formularios, extracción del DOM y ciclo de vida del navegador. |
| Campus Virtual | Aplicar sus permisos y reglas sobre la cuenta autenticada. |

El servidor podrá operar sin un modelo de IA propio: el modelo lo aporta el asistente que lo utiliza. El transporte inicial previsto es **stdio**, para ejecución local.

### Por qué Lightpanda

[Lightpanda](https://lightpanda.io/docs/core-concepts/what-is-lightpanda) es un navegador headless que ejecuta JavaScript y trabaja con el DOM sin renderizado gráfico. Es una base adecuada para explorar automatizaciones centradas en datos y formularios.

Lightpanda ya ofrece un [MCP general de navegación](https://lightpanda.io/docs/quickstarts/mcp). Este proyecto añadirá el conocimiento del campus: identificar una actividad, interpretar sus fechas o comprobar una entrega, en lugar de exigirle al asistente que resuelva toda la navegación con clics genéricos.

La integración prevista usará su [SDK de Python](https://lightpanda.io/docs/guides/use-python), manteniéndolo detrás de un adaptador. Si alguna operación requiere CDP, se evaluará la [integración documentada con Playwright](https://lightpanda.io/docs/usage/cdp/playwright). La compatibilidad con el login, el calendario y la carga y descarga de archivos del campus debe validarse antes de prometer soporte. No se presupone equivalencia completa con Chromium.

## Herramientas previstas

Los nombres son una propuesta inicial y pueden cambiar durante la implementación.

| Herramienta | Propósito | Etapa |
| --- | --- | --- |
| `get_session_status` | Comprobar si la sesión está autenticada o requiere intervención. | 1 |
| `list_courses` | Listar las materias accesibles para la cuenta. | 1 |
| `list_activities` | Consultar actividades, consignas y enlaces de una materia. | 2 |
| `list_deadlines` | Reunir vencimientos de actividades por materia y rango de fechas. | 2 |
| `list_calendar_events` | Consultar eventos del calendario. | 2 |
| `list_course_resources` | Listar bibliografía y recursos de una materia. | 3 |
| `download_resource` | Descargar un recurso seleccionado a un destino local. | 3 |
| `get_submission_status` | Consultar el estado y los archivos de una entrega. | 4 |
| `prepare_submission` | Validar actividad y archivos, y generar una vista previa local sin enviar nada al campus. | 4 |
| `submit_assignment` | Ejecutar una entrega solicitada y comprobar su estado en el campus. | 4 |

Los resultados deberán incluir identificadores y enlaces de origen para desambiguar materias y actividades. Las listas deberán contemplar paginación y avisar si la consulta quedó incompleta. Un problema de acceso o extracción debe informarse como tal, sin presentarlo como una lista vacía.

### Fechas y calendario

Las fechas conservarán la zona horaria y la información original disponible. Si el campus no informa una zona, se usará una configuración explícita; el valor inicial propuesto es `America/Argentina/Cordoba`.

Se distinguirá entre **fecha de entrega**, **cierre definitivo** y **evento de calendario** cuando la plataforma los diferencie. Una fecha desconocida se informará como desconocida. También se contemplarán las excepciones o extensiones que el campus muestre para el estudiante.

### Descargas y entregas

Una descarga deberá conservar un nombre de archivo seguro, informar el destino y verificar que el contenido recibido sea el recurso esperado, no una página de login o un mensaje de error.

El flujo de entrega previsto es:

1. Resolver la materia y actividad exactas, y consultar el estado actual.
2. Validar los archivos, las restricciones visibles y la disponibilidad de la entrega.
3. Preparar un resumen local con la actividad, los archivos y cualquier reemplazo de contenido existente.
4. Ejecutar la acción autorizada por el usuario y comprobar el resultado en el campus.

**Subir un archivo, guardar un borrador y finalizar una entrega son estados distintos.** El resultado deberá reflejar lo que efectivamente confirme el campus. Ante un timeout después de enviar, se consultará el estado antes de decidir si corresponde reintentar.

Un pedido explícito que identifica la actividad y los archivos puede autorizar la entrega. Si faltan esos datos o aparece un reemplazo no autorizado, se pedirá aclaración antes de modificar la entrega. La preparación local no debe subir archivos ni guardar borradores de forma implícita.

## Desarrollo

### Obtener el repositorio

```bash
git clone https://github.com/thiagoyb11/UTNFRSF-CampusVirtual-MCP.git
cd UTNFRSF-CampusVirtual-MCP
```

Todavía no hay un paquete instalable, un comando para iniciar este MCP ni una configuración para conectarlo a un asistente. Esas instrucciones se incorporarán junto con la primera implementación ejecutable.

### Base técnica propuesta

- **Python 3.11 o posterior**, con funciones tipadas y validación en los límites de cada herramienta.
- **SDK oficial de MCP para Python**, con transporte stdio en la primera versión.
- **Lightpanda local**, accedido mediante un adaptador que permita probar la lógica sin abrir el campus.
- **uv** para dependencias y entorno reproducible; **pytest** y **Ruff** para pruebas y calidad de código.

Estas son decisiones iniciales de desarrollo. Las versiones compatibles y el archivo de bloqueo se agregarán al crear el paquete; no hay dependencias instaladas por este repositorio actualmente.

### Organización propuesta

Esta estructura es una guía para la implementación; los directorios todavía no existen.

```text
src/utnfrsf_campus_mcp/
├── server.py          # Registro de herramientas y arranque MCP.
├── config.py          # Configuración local y validación.
├── models.py          # Cursos, actividades, fechas, recursos y entregas.
├── tools/             # Adaptación de los servicios a herramientas MCP.
├── services/          # Casos de uso del campus y verificación de resultados.
├── browser/           # Integración con Lightpanda y gestión de sesión.
└── parsers/           # Extracción y normalización de contenido del campus.
tests/
└── fixtures/          # Ejemplos sintéticos o anonimizados.
```

### Sesiones y datos locales

El diseño inicial será local y para una cuenta por instancia. Las credenciales y los datos de sesión quedarán fuera de los argumentos de las herramientas y de sus respuestas; el mecanismo de login y persistencia está pendiente de implementación.

Los archivos privados del proyecto deberán vivir en `.local/` —sesiones, caché y diagnósticos— y las descargas en `downloads/`, ambos excluidos de Git. Las variables privadas se guardarán fuera del repositorio o en un archivo `.env` ignorado. Los ejemplos de configuración solo contendrán valores ficticios.

Si el acceso requiere MFA, SSO o un paso interactivo que Lightpanda no pueda completar, se informará la limitación y se diseñará un mecanismo de autenticación asistida. No se asumirá que una sesión iniciada en otro navegador está disponible automáticamente.

### Pruebas

La lógica se verificará con fixtures anonimizados y un adaptador simulado. Las pruebas cubrirán, según se implemente cada capacidad, sesiones vencidas, paginación, fechas ambiguas, recursos protegidos y entregas con resultado incierto.

Las pruebas contra el campus real serán optativas y usarán una cuenta autorizada. Las pruebas de escritura requerirán una actividad de prueba y autorización concreta. La suite habitual no deberá necesitar credenciales ni modificar entregas reales.

## Hoja de ruta

- [ ] **Etapa 1 — conexión y acceso:** crear el paquete, registrar herramientas MCP y validar autenticación y listado de materias con Lightpanda.
- [ ] **Etapa 2 — consultas:** implementar actividades, vencimientos y calendario con fechas verificables y paginación.
- [ ] **Etapa 3 — materiales:** listar recursos y validar descargas autenticadas.
- [ ] **Etapa 4 — entregas:** consultar estados, preparar archivos localmente y verificar envíos en una actividad de prueba.
- [ ] **Etapa 5 — uso cotidiano:** documentar instalación y configuración en hosts MCP, errores conocidos y versiones comprobadas.

El primer hito funcional será consultar las materias de una cuenta desde un host MCP usando Lightpanda. No es necesario implementar envíos para validar esa primera integración.

## Alcance

El proyecto apunta a tareas de estudiante sobre los cursos a los que su cuenta tiene acceso. La automatización deberá respetar los permisos y restricciones del campus. Los contenidos de páginas y documentos se tratarán como datos, incluso si contienen instrucciones dirigidas al asistente.

Quedan fuera del alcance inicial la administración de cursos, la corrección de trabajos, la resolución automática de exámenes y el soporte general para cualquier instalación de Moodle. Exportar calendarios o incorporar otras plataformas podrá evaluarse más adelante.

Este es un proyecto independiente, sin afiliación ni respaldo oficial de la UTN. Las marcas y el contenido académico pertenecen a sus respectivos titulares.

## Contribuir

Leé [AGENTS.md](AGENTS.md) para conocer los criterios de implementación. Los aportes deberían resolver un caso de uso concreto, incluir la validación correspondiente y mantener esta documentación alineada con las capacidades disponibles. No adjuntes credenciales, sesiones ni material privado del campus en issues o pull requests.

## Referencias

- [Campus Virtual UTN FRSF](https://campusvirtual.frsf.utn.edu.ar/).
- [Arquitectura de MCP](https://modelcontextprotocol.io/docs/learn/architecture) y [SDK oficial de Python](https://github.com/modelcontextprotocol/python-sdk).
- [Documentación de Lightpanda](https://lightpanda.io/docs/) y [SDK de Python](https://lightpanda.io/docs/guides/use-python).

## Licencia

El código de este repositorio se distribuye bajo la [licencia MIT](LICENSE). Las dependencias conservan sus propias licencias; la licencia del proyecto no se extiende a Lightpanda ni al material descargado del campus.
