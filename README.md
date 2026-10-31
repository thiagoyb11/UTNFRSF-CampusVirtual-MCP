# UTN FRSF · Campus Virtual MCP

Un servidor MCP para conectar asistentes de inteligencia artificial con el [Campus Virtual de la UTN Facultad Regional Santa Fe](https://campusvirtual.frsf.utn.edu.ar/).

Su objetivo es facilitar las tareas cotidianas del estudiante desde un asistente, usando su cuenta del campus.

> Proyecto en desarrollo. Las funcionalidades todavía no están disponibles.

## Funciones previstas

- Consultar materias, actividades y consignas.
- Revisar fechas de entrega y eventos del calendario.
- Descargar bibliografía, apuntes y otros materiales.
- Enviar trabajos prácticos y consultar el estado de las entregas.

## Cómo funciona

El asistente recibe un pedido en lenguaje natural, como “¿qué trabajos vencen esta semana?” o “descargá la bibliografía de esta materia”. A través de MCP, solicita las acciones necesarias al servidor.

El servidor utiliza [Lightpanda](https://lightpanda.io/), un navegador que funciona en segundo plano, para acceder al campus, consultar información o realizar la acción solicitada. Luego devuelve el resultado al asistente.

El acceso se limita a las materias y recursos disponibles para la cuenta del estudiante.

## Licencia

[MIT](LICENSE). Proyecto independiente, sin afiliación oficial con la UTN.
