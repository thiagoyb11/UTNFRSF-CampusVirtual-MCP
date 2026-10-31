# UTN FRSF · Campus Virtual MCP

Un servidor MCP para conectar asistentes de inteligencia artificial con el [Campus Virtual de la UTN Facultad Regional Santa Fe](https://campusvirtual.frsf.utn.edu.ar/).

Su objetivo es facilitar las tareas cotidianas del estudiante desde un asistente, usando su cuenta del campus.

> Proyecto en desarrollo. El inicio de sesión ya está disponible; las consultas y entregas siguen en implementación.

La herramienta `login()` usa el usuario y la contraseña configurados en el `.env` privado. Podés probarla desde un cliente MCP como Inspector; las instrucciones están en la [guía de desarrollo](docs/desarrollo.md).

## Funciones previstas

- Consultar materias, actividades y consignas.
- Revisar fechas de entrega y eventos del calendario.
- Descargar bibliografía, apuntes y otros materiales.
- Enviar trabajos prácticos y consultar el estado de las entregas.

## Cómo funciona

El asistente recibe un pedido en lenguaje natural, como “¿qué trabajos vencen esta semana?” o “descargá la bibliografía de esta materia”. A través de MCP, solicita las acciones necesarias al servidor.

El servidor utiliza [Lightpanda](https://lightpanda.io/), un navegador que funciona en segundo plano, para acceder al campus, consultar información o realizar la acción solicitada. Luego devuelve el resultado al asistente.

El acceso se limita a las materias y recursos disponibles para la cuenta del estudiante.

## Estructura

```text
src/utnfrsf_campus_mcp/
├── server.py       # Arranque del servidor MCP.
├── config.py       # Configuración desde .env y variables de entorno.
├── models.py       # Modelos de datos.
├── browser/        # Integración con Lightpanda.
├── parsers/        # Extracción de información del campus.
├── services/       # Lógica de las funcionalidades.
└── tools/          # Herramientas expuestas al asistente.
docs/               # Documentación de desarrollo.
examples/           # Ejemplos de configuración MCP.
.env.example        # Plantilla de configuración local.
pyproject.toml      # Paquete y dependencias.
uv.lock             # Versiones de dependencias.
roadmap.md          # Plan de implementación.
AGENTS.md           # Guía para agentes de desarrollo.
```

Documentación técnica: [desarrollo local](docs/desarrollo.md) · [roadmap](roadmap.md).

## Licencia

[MIT](LICENSE). Proyecto independiente, sin afiliación oficial con la UTN.
