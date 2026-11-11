<p align="right"><a href="README.md">English</a> · <a href="README.zh-CN.md">简体中文</a> · <a href="README.ja.md">日本語</a> · <strong>Español</strong></p>

# Ruin Everything

### Dale el navegador a tu agente. Recupera tu tiempo.

**Tu agente hace clic. Ruin mantiene el trabajo en marcha.**

Ruin Everything es un **entorno local de Chrome para agentes de navegador**. Tu agente aprovecha las sesiones, cookies y extensiones del perfil compartido, trabaja en pestañas en segundo plano y continúa los pasos de acceso y verificación compatibles. Abre sitios, rellena formularios, lee páginas y devuelve pruebas de lo que ocurrió.

<img src="docs/figures/core-workflow.svg" alt="A: el agente maneja Chrome compartido mediante Ruin en segundo plano. B: reutiliza accesos locales y procesa verificaciones compatibles. C: la confirmación del sitio aporta pruebas; los comprobantes de Ashby se pueden guardar." width="100%">

<p align="center">
  <a href="https://github.com/yuki4266/ruin-everything/stargazers"><img src="docs/figures/badges/stars.svg" alt="Estrellas en GitHub"></a>
  <a href="#quickstart"><img src="docs/figures/badges/python.svg" alt="Python 3.11 o posterior"></a>
  <a href="#connect-an-agent-over-mcp"><img src="docs/figures/badges/mcp.svg" alt="MCP mediante stdio"></a>
  <a href="LICENSE"><img src="docs/figures/badges/license.svg" alt="Licencia MIT"></a>
</p>

[Empezar](#quickstart) · [Funciones principales](#core-features) · [Casos de uso](#real-workflows) · [Verificación](#verification) · [Referencia técnica en inglés](docs/runtime-reference.md)

## Menos supervisión. Más trabajo terminado.

El agente llega a una pantalla de acceso. Aparece un código en el correo. Tras pulsar Enviar, sale otra verificación. Luego termina la conversación y nadie sabe si la solicitud llegó.

**Ruin se ocupa de los pasos del navegador que interrumpen la tarea.** El panel A muestra el navegador compartido; el B, el acceso y la verificación; el C, un resultado que puedes comprobar.

<a id="core-features"></a>

| Función principal | Qué ganas |
| --- | --- |
| **Tu Chrome, listo para trabajar** | Navegar, hacer clic, escribir, seleccionar y extraer texto entre sitios. Conserva el perfil, las cookies y las extensiones entre sesiones del agente. |
| **Un agente que te deja trabajar** | Las pestañas se abren en segundo plano y siguen siendo interactivas, sin cambiar tu aplicación en primer plano ni reemplazar pestañas ajenas a la tarea. |
| **Reutiliza tus accesos** | El almacén local registra accesos manuales con contraseña y puede rellenar un formulario coincidente después. Las copias de cookies y Web Storage ayudan a restaurar el estado al reiniciar Chrome. El sitio decide cuándo caduca. |
| **Continúa tras la verificación** | Los flujos compatibles manejan códigos recientes de correo, SMS y retos visuales en la pestaña original. Si el reto sigue pendiente, el resultado lo indica. |
| **Menos registros repetidos** | Un perfil local rellena formularios compatibles de registro y contacto. La recuperación opcional de Workday/iCIMS maneja errores reconocidos y solicitudes de restablecimiento de contraseña. |
| **Pruebas que puedes consultar después** | El observador de Ashby guarda la confirmación de envío por URL del puesto. Puedes recuperar el comprobante incluso con Chrome cerrado. |

La navegación general usa `ruin_browser`; los sitios de abajo son ejemplos de automatización adicional. El agente planifica la tarea y Ruin ejecuta las acciones en el navegador.

### Adjuntar un archivo local

Llama a `ruin_browser(operation="upload")` o a su alias `set_files` con la URL exacta de la pestaña en `site` y la ruta absoluta en `file_path`. En el panel A, puedes omitir `selector` si hay un único campo de archivo entre la página y todos sus marcos. Si hay varios, indica el campo deseado. El panel B muestra también cómo seleccionar una zona de arrastre. Las pruebas de navegador verifican ambas vías, incluido un campo oculto en un marco anidado.

<img src="docs/figures/upload.svg" alt="El archivo local llega al campo o a la zona de arrastre seleccionados. El sitio muestra el adjunto antes del envío." width="100%">

<a id="quickstart"></a>
<a id="use-a-shared-local-chrome-window"></a>

## Tu primera tarea en tres pasos

<img src="docs/figures/local-chrome.svg" alt="Conexiones independientes comparten un perfil local de Chrome y conservan la pestaña original de la tarea." width="100%">

### 1. Inicia el navegador compartido

Necesitas **Python 3.11+, Google Chrome y [uv](https://docs.astral.sh/uv/getting-started/installation/)**. Estos pasos usan el código actual de GitHub para incluir las funciones descritas aquí.

```sh
uvx --from 'ruin-everything @ git+https://github.com/yuki4266/ruin-everything.git@main' ruin browser
```

Ruin inicia Chrome o se conecta a él en `127.0.0.1:9222`. El perfil persistente es `~/.ruin-everything/canvas-browser`. Inicia sesión en los sitios que necesitas **dentro de ese perfil**; no se importan los accesos de otro perfil de Chrome. El navegador y sus pestañas permanecen abiertos al terminar el comando.

<a id="connect-an-agent-over-mcp"></a>

### 2. Conecta tu agente

Añade esta configuración al cliente MCP y reinicia la conexión. El cliente debe poder ejecutar `uvx`.

```json
{
  "mcpServers": {
    "ruin-everything": {
      "command": "uvx",
      "args": [
        "--isolated", "--refresh", "--from",
        "ruin-everything @ git+https://github.com/yuki4266/ruin-everything.git@main",
        "ruin-mcp"
      ],
      "env": { "RUIN_AUTO_UPDATE": "0" }
    }
  }
}
```

Para usar el paquete publicado, sustituye la fuente Git por `ruin-everything`. Las actualizaciones de Git se cargan al iniciar de nuevo el servidor; las funciones de PyPI dependen de la versión publicada. [Detalles de instalación y actualización](docs/runtime-reference.md#how-updates-reach-your-machine).

<a id="first-mcp-call"></a>

### 3. Dale una tarea

> Use Ruin to open https://example.org and tell me the page title and visible links.

El punto de entrada es `ruin_browser(operation="navigate", url="https://example.org")`. Las llamadas siguientes usan la URL actual devuelta. El servidor MCP de Ruin no necesita una clave API; el agente usa su propia conexión al modelo. La CLI independiente y opcional dirigida por un modelo requiere las dependencias agent y `OPENAI_API_KEY`.

Para los asistentes de registro y cuenta, usa una instalación persistente del repositorio y ejecuta `ruin identity`. Selecciona la pestaña del editor abierta en segundo plano para añadir tus datos y decidir si activas el registro automático. `ruin ats-setup` activa por separado la recuperación de contraseñas ATS. [Configuración](docs/runtime-reference.md#local-account-registration).

<a id="real-workflows"></a>
<a id="institutional-sign-in-in-the-background"></a>

## Dónde te ahorra trabajo

<img src="docs/figures/post-action.svg" alt="Tras una acción en la pestaña original se inspeccionan retos visuales y se intentan los pasos compatibles; el comprobante del sitio acredita el envío." width="100%">

| Quieres… | Ayuda adicional de Ruin | Verificación hasta ahora |
| --- | --- | --- |
| **Pasar un reto visual de selección de personal** | Procesar el rompecabezas compatible de ZhongAn/Moka o el control de rotación de Feishu Jobs. | Se observaron contadores reales de reenvío de SMS en ambos; ZhongAn también mostró su página de éxito y el historial de solicitud. |
| **Completar la verificación por correo de Greenhouse** | Buscar un mensaje nuevo de Outlook que coincida con el empleador y la petición, e introducir el código en la pestaña original. | Pruebas simuladas en navegador; compatibilidad real con empleadores y cuentas de Outlook aún sin verificar. |
| **Recuperar una cuenta de Workday o iCIMS** | Usar datos locales, registro y activación compatibles, y recuperación opcional con intentos limitados. | Pruebas simuladas e inspección de un diálogo real de Workday. Los diseños varían entre organizaciones. |
| **Saber si una solicitud de Ashby se envió** | Esperar la confirmación oficial y guardar un comprobante para ese puesto. | Pruebas locales de comprobantes e integración del navegador. Sin registro, el resultado es desconocido. |
| **Acceder a un artículo a través de Duke** | Seguir los flujos institucionales compatibles de IEEE, ACM y Springer; continuar formularios Duke ya rellenados y pantallas de confianza de dispositivo Duo. | Búsqueda IEEE, redirección a Duke y acceso a PDF reales; ACM y Springer cubiertos con pruebas simuladas. |

La compatibilidad corresponde a flujos concretos. Algunos retos visuales necesitan un modelo de visión local de Ollama; leer SMS requiere acceso a macOS Messages; los flujos de correo necesitan Outlook Web con sesión iniciada. Las aprobaciones por teléfono y otras comprobaciones pueden requerir tu intervención. [Requisitos y comandos](docs/runtime-reference.md).

Para enviar un formulario autorizado, usa `ruin_action` con la URL actual exacta y el texto visible del botón. Comprueba si aparece una verificación tras el clic. **Superar un reto es un paso; el comprobante del sitio demuestra el envío.**

### Introducir un código en varias casillas

El panel A muestra cómo Ruin identifica el SMS o el correo de Outlook compatible con la solicitud. El panel B muestra cómo pega el código y completa las casillas que faltan. La verificación telefónica de Ctrip se comprobó en el sitio real. Ambas vías de entrada se probaron con react-otp-input 3.1.1.

<img src="docs/figures/split-otp.svg" alt="Ruin pega el código o completa las casillas individualmente y comprueba su valor conjunto en la pestaña original." width="100%">

## Seis herramientas. Un navegador compartido.

<img src="docs/figures/challenge-routing.svg" alt="La URL exacta del puesto permite identificar el proveedor de verificación y conservar el formulario original." width="100%">

| Herramienta | Para qué sirve |
| --- | --- |
| `ruin_browser` | Listar pestañas, navegar, inspeccionar, leer, hacer clic, rellenar, pulsar teclas y seleccionar opciones. |
| `ruin_action` | Enviar un formulario autorizado y manejar verificaciones posteriores compatibles; omitir el botón para continuar. |
| `ruin_auto_register` | Continuar pasos compatibles de registro, cuenta o acceso por SMS con el perfil local. |
| `inspect_application_challenge` | Identificar un reto de Greenhouse/Ashby o localizar una pestaña de solicitud compatible. |
| `get_ashby_receipt` | Consultar pruebas de envío guardadas sin abrir Chrome. |
| `watch_ashby_receipt` | Esperar la confirmación en la pestaña original de Ashby y guardarla. |

[Instrucciones para agentes](AGENTS.md) · [CLI y comportamiento detallado](docs/runtime-reference.md) · [Configuración de acceso de confianza](docs/trusted-auth.md)

## Tu equipo. Tu estado del navegador.

<img src="docs/figures/local-auth-vault.svg" alt="El acceso manual se guarda en un archivo local privado; los accesos coincidentes usan el ejecutor; las cookies y Web Storage permiten restaurar otra sesión de Chrome." width="100%">

La ejecución del navegador y el manejo de credenciales son locales. **El almacén automático guarda contraseñas en texto plano** en `~/.ruin/auth_vault.json`, con permisos exclusivos del propietario (`0600`); no aparecen en los resultados de herramientas del agente. Las cookies y Web Storage también se guardan localmente. `RUIN_LOCAL_AUTH_VAULT=0` desactiva el inicio automático del proceso de escucha para ese cliente. [Comportamiento y límites del almacén](docs/runtime-reference.md#local-auth-vault).

El agente conectado puede enviar texto de las páginas a su proveedor de modelos. Las sesiones caducan y algunas verificaciones necesitan una persona. Ruin conserva el estado y retoma los pasos compatibles; no promete acceso permanente ni éxito en todos los sitios.

<a id="verification"></a>

## Qué se ha comprobado

<img src="docs/figures/checks.svg" alt="Las pruebas locales comprueban el comportamiento del entorno; las observaciones reales cubren flujos específicos de sitios." width="100%">

**Comprobación actual:** pasaron las 103 pruebas de regresión locales, la compilación de fuente y wheel y la validación estricta de Twine. También se comprobaron el éxito inicial, la recuperación en el segundo y tercer intento y el fallo persistente. No se repitieron los flujos de sitios reales.

<img src="docs/figures/build-retry.svg" alt="La instalación de Chromium permite tres intentos; un fallo persistente detiene la compilación y solo las comprobaciones exitosas permiten publicar." width="100%">

El fallo de CI ocurrió al descargar fuentes adicionales por errores DNS de los repositorios de Ubuntu. El runner ya disponía de las bibliotecas compartidas de Chromium. Ahora CI instala Chromium directamente y valida el entorno con la suite de regresión del navegador (figura A–C). Las descargas permiten tres intentos, con esperas de 15 y 30 segundos y un límite de 30 minutos para el paso. Las pruebas y las comprobaciones del paquete habilitan la publicación en PyPI. [Resultados de CI](https://github.com/yuki4266/ruin-everything/actions/workflows/publish.yml).

Las pruebas locales cubren sesiones compartidas, pestañas en segundo plano, captura y restauración de accesos, separación entre organizaciones, rutas de verificación y almacenamiento de comprobantes. La tabla distingue observaciones reales de pruebas simuladas. La referencia describe las condiciones y límites de cada comprobación.

Ejecuta la suite de regresión desde el repositorio de desarrollo:

```sh
python -m pip install -e '.[agent]'
python -m playwright install chromium
RUIN_AUTO_UPDATE=0 RUIN_RULE_UPDATES=0 python -m unittest discover -s tests -v
```

Las ilustraciones son SVG originales y editables hechos con Rough.js y Kalam. [Fuentes de las figuras](docs/figures) · [Contribuir](CONTRIBUTING.md) · [Plan de desarrollo](PLAN.md) · [Licencia MIT](LICENSE)

<a id="community"></a>

## Ponlo a trabajar. Cuéntanos dónde se atasca.

<img src="docs/figures/community.svg" alt="Informa de un fallo reproducible, comparte un flujo que funciona o contribuye con una mejora en GitHub." width="100%">

[Informar de un fallo](https://github.com/yuki4266/ruin-everything/issues/new?template=bug.yml) · [Compartir un flujo](https://github.com/yuki4266/ruin-everything/discussions/categories/show-and-tell) · [Proponer una función](https://github.com/yuki4266/ruin-everything/discussions/categories/ideas)

**Si Ruin te ahorró otra ronda de supervisión del navegador, [dale una estrella](https://github.com/yuki4266/ruin-everything).**
