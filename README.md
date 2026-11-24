# Tamo online?

Monitorea si tu tienda está **online u offline** en **PedidosYa**, **Rappi** y **Rappi Turbo**, usando los links públicos que ve el cliente (sin login ni credenciales). Avisa con notificaciones del navegador cuando algo no va como se espera según el horario del local.

## Cómo funciona
- **Programa local (Python, Windows)**: un servidor liviano en `http://127.0.0.1:8765` lee las plataformas desde tu conexión doméstica cada 2 minutos (configurable, con variación aleatoria), detecta cambios y guarda el historial en `estado.json`.
- **Web** (HTML/CSS/JS puro): se publica en GitHub Pages desde `/docs` y consulta la API local cada 15 s. También se sirve en `http://localhost:8765` como respaldo.
- Lectura: primero HTTP simple (httpx) buscando el JSON embebido (`__NEXT_DATA__`, JSON-LD, estado inicial); si no alcanza, Playwright con Chromium.
- Cada plataforma es un archivo en `server/adapters/`. Para sumar otra, copiá uno, cambiá `clave`, `nombre` y las claves a buscar, y exportá `ADAPTADOR = MiClase()`. Se detecta sola.

## Estados
| Estado | Color | Significado |
|---|---|---|
| Online | verde | Abierta |
| Online + etiqueta "Online fuera de horario" | verde con borde ámbar | Abierta cuando debería estar cerrada (notifica) |
| Offline (debería estar abierta) | rojo/terracota | Cerrada dentro de su horario (notifica) |
| Cerrada (fuera de horario) | marrón apagado | Cerrada y debe estar cerrada (normal) |
| Sin datos | ámbar | No se pudo leer; el motivo aparece en letra chica |

Zona horaria: `America/Argentina/Buenos_Aires`.

## Requisitos
Windows, Python 3.10+ (con "Add python.exe to PATH") e internet.

## Subir el proyecto al repo `guerrasur/tamonline`
1. Subí todo el contenido de esta carpeta a la rama `main` (`git push origin main`).
2. En GitHub: **Settings → Pages → Build and deployment → Deploy from a branch → `main` / carpeta `/docs`**.
3. La web queda en `https://guerrasur.github.io/tamonline/`.

## Primer uso
1. Doble clic en `iniciar_app.bat`. La primera vez crea el entorno virtual, instala dependencias y Chromium, y crea el acceso directo **"Tamo online"** en el Escritorio (Windows no permite "?" en nombres de archivo). Ese acceso directo arranca sin ventana de consola.
2. Se abre el navegador con una pantalla de configuración: nombre del local y links de cada plataforma (cualquiera puede quedar vacío).
3. Después se edita todo desde el botón **Ajustes** (más locales, intervalo, sonido, qué web abrir).
4. Si ya hay otra instancia corriendo (puerto 8765 ocupado), solo se abre el navegador.

Con varios locales aparecen pestañas arriba; con uno solo no hay selector. `config.json` queda solo en tu PC (está en `.gitignore` y el actualizador no lo toca).

## Horarios
El adaptador intenta leer el horario publicado en la página. Si no lo logra, cargalo a mano en **Ajustes → Horarios manuales** (por local, plataforma y día, con varios tramos; un cierre menor que la apertura significa que pasa la medianoche, ej. 18:00 a 02:00). El horario manual tiene prioridad.

## Notificaciones
- La web pide permiso la primera vez; si lo rechazás, queda un botón visible para activarlo.
- Se notifica cuando: a) una tienda queda offline dentro de su horario; b) una tienda está online fuera de horario; c) hay "sin datos" durante 3 verificaciones seguidas (configurable). Abrir o cerrar según lo esperado no notifica, y no se repite la misma notificación mientras el estado no cambie.
- El detector vive en el programa local; la web, al abrirse, muestra los últimos 50 eventos.
- **Las notificaciones funcionan con la web abierta en una pestaña.** El navegador puede limitar pestañas en segundo plano: conviene dejarla **fijada**.
- Sonido corto opcional en Ajustes. Modo demo: `?demo=1` (por ejemplo `http://localhost:8765/?demo=1`).

## Actualización automática
En cada arranque `updater.py` compara `VERSION` local con el `VERSION` de la rama `main`. Si es mayor, descarga el ZIP del repo y reemplaza los archivos, conservando `config.json`, `estado.json` y `logs/`. Sin internet o si falla, sigue con la versión instalada. **Para publicar una versión nueva: editá `VERSION` (ej. `1.0.1`) y subilo a `main`.**

## Limitaciones conocidas
- **No hay garantía de que PedidosYa o Rappi permitan la lectura automática.** Pueden bloquear, pedir captcha o cambiar su página. En ese caso la tarjeta muestra **Sin datos** con el motivo y la app sigue funcionando.
- Las claves JSON buscadas en cada adaptador son una estimación; hay que validarlas contra las páginas reales (ver abajo).
- Chrome/Edge pueden pedir permiso de **acceso a la red local** al usar la web desde GitHub Pages. Si lo bloquean, usá `http://localhost:8765`.
- La web de Pages (https) llama a `127.0.0.1`; la app envía los encabezados CORS y de red privada necesarios.

## Diagnóstico
Mirá la carpeta `logs/`:
- `servidor.log`: errores generales.
- `pedidosya.log`, `rappi.log`, `rappi_turbo.log`: método usado (http/playwright), código HTTP, resultado y motivo.
- `<plataforma>_<local>_ultima.html`: última página que no se pudo interpretar. Buscá ahí cómo informa la tienda si está abierta y ajustá `claves_abierto` / `claves_cerrado` (o `analizar`) en el adaptador correspondiente.

## API
`GET /api/status` · `GET/POST /api/config` · `POST /api/refresh` · `GET /api/version`
