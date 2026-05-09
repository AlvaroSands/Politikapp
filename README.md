# INTEL-GEO COMMAND CENTER

Mapa geopolítico interactivo en tiempo real con interfaz de sala de mando táctica. Muestra crisis activas, tensiones bilaterales y relaciones diplomáticas globales actualizadas.

---

## Captura visual

```
┌──────────────────────────────────────────────────────────────────┐
│  ◉ INTEL-GEO COMMAND CENTER          LIVE  14:23:01 UTC          │
│                         CRISIS: 14  TENSIONES: 16  NIVEL: CRÍTICO │
├──────────────┬───────────────────────────────────────┬───────────┤
│              │                                       │ FILTROS   │
│  PANEL DE    │     GLOBO 3D CON ARCOS ANIMADOS       │ DASHBOARD │
│  INTELIGENCIA│     (MapLibre GL JS, fog, estrellas)  │           │
│              │                                       │           │
│  Al hacer    │   ● Crisis (rojo/naranja/amarillo)    │           │
│  clic en un  │   ─ ─ ─ Relaciones bilaterales        │           │
│  punto se    │   ░░░ Heatmap de densidad              │           │
│  muestran    │                                       │           │
│  los eventos │                                       │           │
│  históricos  ├───────────────────────────────────────┤           │
│              │  LÍNEA TEMPORAL ──────────●───────    │           │
└──────────────┴───────────────────────────────────────┴───────────┘
```

---

## Tecnologías

| Componente | Tecnología |
|------------|-----------|
| Servidor   | FastAPI + Uvicorn |
| Mapa       | MapLibre GL JS v4.7.1 (fork open-source de Mapbox) |
| Tiles      | CARTO Dark Matter (sin token, gratuito) |
| Geodesia   | Turf.js v7.1.0 (arcos great-circle) |
| Datos      | `datos.json` (base de datos local) |
| Fuentes RSS| BBC World, Al Jazeera, France 24, El País, NYT World |

---

## Estructura de archivos

```
MAPA-GEOPOLITICO/
├── index.html          # Interfaz web completa (mapa + UI)
├── main.py             # Servidor FastAPI
├── actualizador.py     # Script de actualización de datos vía RSS
├── datos.json          # Base de datos de crisis y relaciones
├── requirements.txt    # Dependencias Python (5 paquetes)
├── .env                # Variables de entorno (no versionado)
├── .gitignore
└── entorno_mapa/       # Entorno virtual Python (no versionado)
```

---

## Instalación y arranque

### 1. Crear entorno virtual (solo la primera vez)

```bash
python3 -m venv entorno_mapa
```

### 2. Instalar dependencias

```bash
entorno_mapa/bin/pip install -r requirements.txt
```

### 3. Arrancar el servidor

```bash
entorno_mapa/bin/python3 main.py
```

Abre el navegador en: **http://localhost:8000**

---

## Actualizar los datos

El script `actualizador.py` lee feeds RSS internacionales y clasifica las noticias automáticamente por palabras clave, sin necesidad de ninguna API de IA.

```bash
entorno_mapa/bin/python3 actualizador.py
```

**Fuentes que analiza:**
- BBC World RSS
- Al Jazeera RSS
- France 24 (español)
- El País (internacional)
- NYT World

**Lógica de clasificación:**
1. Detecta si hay dos países mencionados con una palabra de relación bilateral → crea una nueva entrada en `relaciones`
2. Detecta palabras clave de crisis conocidas → añade la noticia como actualización de esa crisis
3. Asigna nivel automáticamente: rojo (guerra/ataque), naranja (tensión/sanciones), amarillo (diplomacia/cumbre)

Para añadir noticias manualmente, editar directamente `datos.json` siguiendo la estructura descrita más abajo.

---

## Estructura de `datos.json`

### Crisis (puntos en el mapa)

```json
{
  "crisis": [
    {
      "id_crisis": "identificador-unico",
      "titulo_principal": "Nombre del conflicto",
      "lat": 48.14,
      "lng": 37.75,
      "nivel_actual": "rojo",
      "actualizaciones": [
        {
          "fecha": "2026-05-08",
          "titular": "Titular de la noticia",
          "fuente": "Nombre del medio",
          "url": "https://enlace-a-la-noticia.com"
        }
      ]
    }
  ]
}
```

**Niveles válidos:** `rojo` · `naranja` · `amarillo`

### Relaciones (arcos entre países)

```json
{
  "relaciones": [
    {
      "id_relacion": "identificador-unico",
      "origen": {
        "nombre": "EE.UU.",
        "lat": 38.8951,
        "lng": -77.0364
      },
      "destino": {
        "nombre": "Irán",
        "lat": 35.6892,
        "lng": 51.389
      },
      "tipo": "militar",
      "nivel": "rojo",
      "fecha": "2026-05-07",
      "titular": "Descripción de la relación/incidente",
      "fuente": "Medio de comunicación",
      "url": "https://enlace"
    }
  ]
}
```

**Tipos válidos:** `militar` · `diplomática` · `comercial` · `territorial`

---

## Funciones de la interfaz

### Mapa
- **Globo 3D** con efecto de espacio y estrellas (fog en MapLibre v4)
- **Arcos great-circle animados** entre países (señal fluyendo a lo largo del arco)
- **Marcadores de 3 anillos pulsantes** tipo radar para cada crisis
- **Heatmap** de densidad de crisis (visible al alejar el zoom)
- Zoom, rotación y navegación libre

### Paneles
| Panel | Ubicación | Función |
|-------|-----------|---------|
| Panel de inteligencia | Izquierda | Muestra eventos históricos al clicar un punto o arco |
| Panel de controles | Derecha | Filtros + dashboard de distribución global |
| Línea temporal | Abajo centro | Slider para filtrar eventos por fecha |
| Barra superior | Arriba | Reloj UTC, contadores, nivel global de amenaza |

### Filtros disponibles
- **Nivel de alerta:** Crítico (rojo) / Alto (naranja) / Moderado (amarillo)
- **Tipo de relación:** Militar / Diplomático / Comercial / Territorial
- Afectan simultáneamente a marcadores, arcos y heatmap

### Auto-refresh
El mapa consulta `/datos.json` cada 60 segundos. Si los datos cambian (porque se ejecutó `actualizador.py`), se actualiza automáticamente sin recargar la página.

---

## Estado del mundo cubierto (mayo 2026)

| Crisis | Nivel | Área |
|--------|-------|------|
| Guerra Rusia-Ucrania + alto el fuego Trump | 🔴 Rojo | Europa del Este |
| Irán / Bloqueo Ormuz + negociaciones nucleares | 🔴 Rojo | Oriente Medio |
| Gaza — bloqueo humanitario total | 🔴 Rojo | Oriente Medio |
| Guerra civil Sudán — ataques con drones | 🔴 Rojo | África |
| Sahel — yihadismo y AES | 🔴 Rojo | África Occidental |
| Mar Rojo — ataques hutíes | 🔴 Rojo | Mar Rojo |
| Haití — colapso institucional | 🔴 Rojo | Caribe |
| Ecuador — estado de excepción | 🔴 Rojo | Sudamérica |
| India-Pakistán — Operación Sindoor + agua | 🟠 Naranja | Asia del Sur |
| Corea del Norte — misiles + tecnología rusa | 🟠 Naranja | Asia-Pacífico |
| Crisis energética Europa | 🟠 Naranja | Europa |
| Taiwán — presión militar china | 🟡 Amarillo | Asia-Pacífico |
| Caída de Orbán en Hungría | 🟡 Amarillo | Europa |
| China — estrategia energética global | 🟡 Amarillo | Asia |

---

## Despliegue en producción

El servidor FastAPI es compatible con cualquier plataforma que acepte Python:

**Railway / Render / Fly.io:**
```bash
# Comando de arranque
entorno_mapa/bin/python3 main.py
# o
uvicorn main:app --host 0.0.0.0 --port $PORT
```

**Variables de entorno:**
```
PORT=8000   # puerto (opcional, por defecto 8000)
```

---

## Notas de desarrollo

- El `.env` contiene claves de API antiguas (eliminadas); el actualizador ya no las necesita.
- El `importador_masivo.py` está en `.gitignore` por haber contenido claves hardcodeadas; ya no es necesario.
- Los tiles de CARTO son gratuitos y no requieren registro. Límite: uso razonable.
- MapLibre GL JS es open-source (fork de Mapbox GL JS), sin tokens ni límites.

---

*Última actualización: 9 de mayo de 2026*
