# Research: GeoConfirmed.org

**Fecha de análisis**: 12 mayo 2026  
**Analista**: Claude (Sonnet 4.6)  
**Propósito**: Identificar ideas replicables para Geopolitikapp

---

## 1. Qué es GeoConfirmed

Proyecto OSINT voluntario centrado en **verificar y geolocalizar contenido visual** (fotos y vídeos) de zonas de conflicto. No es un agregador de noticias: cada punto del mapa es un evento con prueba visual verificada públicamente.

URL principal: https://geoconfirmed.org  
X/Twitter: @GeoConfirmed  
Email de contacto: contact@geoconfirmed.org

### Conflictos activos cubiertos (con volumen de datos a mayo 2026)

| Conflicto | Geolocalizaciones |
|---|---|
| Ucrania | 49.000+ |
| Israel/Gaza (7 oct) | 6.400+ |
| Siria | 1.050+ |
| Myanmar | 780+ |
| Sahel | 830+ |
| Irán | En desarrollo |
| Venezuela | En desarrollo |
| Carteles México | En desarrollo |

**Tipos de eventos verificados**: pérdidas de equipo militar, movimientos de tropas, misiles/drones, daños a infraestructura, crímenes de guerra.

---

## 2. Interfaz del mapa — controles y UX

Actualización de UI anunciada en abril 2025. Los controles identificados:

| Control | Descripción |
|---|---|
| **Selector de área/país** | Menú de navegación rápida por conflicto o región |
| **Timeline animado** | Reproducir, acumular iconos o mostrar día a día, pausar, ajustar velocidad |
| **Rango de fechas** | Filtro temporal con fecha inicio y fin |
| **Capas base** | Toggle entre topográfico y satelital |
| **Herramienta de distancias** | Medición entre dos puntos sobre el mapa |
| **Línea de frente** | Superposición de dos líneas de frente basadas en rango de fechas |
| **Filtros combinables** | Por facción, unidad militar (ORBAT), palabras clave (AND/OR/NOT), radio/polígono espacial |

Al clicar un marcador se abre un panel con: fuente original, coordenadas exactas, y la **prueba de geolocalización** (diagrama anotado con landmarks, líneas de visión y pistas visuales).

---

## 3. Sistema ORBAT — árbol de actores

Una de las features más distintivas: árbol jerárquico de unidades militares (Order of Battle) **vinculado al mapa**:

- Ver designaciones de unidades, equipamiento y última posición conocida.
- Filtrar el mapa por unidad específica (buscar un Cuerpo de Ejército muestra todas las unidades subordinadas).
- Actualizaciones colaborativas por la comunidad (con login).
- ORBAT disponibles: EE.UU., Rusia, Ucrania, Venezuela (en desarrollo).

---

## 4. Flujo de verificación y curaduría

El proceso es **100% manual y comunitario**:

1. Voluntarios monitorean Telegram, redes sociales y medios
2. Verifican la geolocalización con Google Earth, Mapillary, Sentinel Hub
3. Generan una **prueba anotada** (imagen con landmarks, líneas de visión) y la publican como thread en X
4. Otros voluntarios doble-verifican
5. Un moderador lo sube al mapa con todos los metadatos

Para contribuir: etiquetar `@GeoConfirmed` en X o enviar DM para ser voluntario de carga de datos.

---

## 5. Estructura de datos por evento

Extraído del plugin QGIS oficial y la librería `osint-geo-extractor` en PyPI:

```json
{
  "id": "string",
  "date": "datetime",
  "date_created": "datetime",
  "name": "string",
  "description": "string",
  "original_source": "string (URLs separadas por salto de línea)",
  "geolocation": "string (URLs de la prueba visual)",
  "faction": "string (nombre de facción)",
  "equipment_type": "string (categoría de equipo)",
  "is_destroyed": "boolean",
  "latitude": "float",
  "longitude": "float",
  "links": ["string"]
}
```

### Parámetros de filtrado disponibles en su API

1. **Por facción**: bando específico (Rusia, Ucrania, Hamas, etc.)
2. **Por unidad militar**: árbol ORBAT jerárquico
3. **Por palabras clave**: búsqueda booleana `AND (&)`, `OR (|)`, `NOT (!)`, agrupación `()`
4. **Por fechas**: rango personalizado o últimos N días
5. **Espacial**: radio, extensión del lienzo o límites de polígono

---

## 6. API pública

**Endpoint KML**: `https://geoconfirmed.org/api/map/ExportAsKml/{conflict}`

Conflictos disponibles: `ukraine`, `7oct`, `syria`, `myanmar`, `iran`, etc.

**Librerías que consumen la API**:
- Python: `osint-geo-extractor` ([PyPI](https://pypi.org/project/osint-geo-extractor/)) — función `get_geoconfirmed_data()`
- QGIS: plugin oficial ([plugins.qgis.org](https://plugins.qgis.org/plugins/geoconfirmed_qgis/))

**Filtrado server-side**: la API soporta filtrado en servidor para datasets grandes, no hay que descargar todo.

---

## 7. Stack tecnológico visible

| Componente | Tecnología |
|---|---|
| Hosting | Azure (geoconfirmed.azurewebsites.net como backup) |
| API | REST con exportación KML y GeoPackage |
| Mapa | Multi-basemap (topográfico + satélite) |
| Filtrado | Server-side |
| Código fuente | Cerrado (no hay repositorio público) |

---

## 8. Modelo de negocio y ética de uso

- **Sin fines de lucro, voluntario**
- Donaciones vía Buy Me a Coffee para imágenes satelitales y servidores
- Declaran públicamente: datos *"free to use"* para investigaciones de DDHH, académicas y de policy
- *"They share their data in a direct manner so others can use them for their investigations"*
- Sin cookies, sin datos personales almacenados

**Condiciones para uso ético** (si integramos como fuente):

1. Atribución visible en cada marcador: "Verificado por GeoConfirmed ↗"
2. No redistribuir el dataset como propio
3. Rate limit conservador: máximo 1 fetch/hora por mapa
4. Cache local: guardar KML descargado, no golpear CDN en cada request
5. Aviso por email a contact@geoconfirmed.org antes de poner en producción

---

## 9. Ideas trasladables a Geopolitikapp

### Alta prioridad

| Idea | Descripción | Esfuerzo estimado |
|---|---|---|
| **Timeline animado con modos** | Play/pause/velocidad + toggle "acumular vs día por día". Máximo impacto visual. | Medio (solo `index.html`) |
| **Árbol de actores vinculado al mapa** | Jerarquía países → alianzas → organizaciones → grupos armados. Clic filtra el mapa. | Alto (nuevo `actores.json` + `index.html` + `actualizador.py`) |
| **Iconografía por tipo de evento** | Iconos SVG distintos por tipo (armed/diplo/econ/cyber/intel) en lugar de círculos de color | Bajo–Medio (solo `index.html`) |
| **Toggle de capa de estado geopolítico** | Equivalente al frontline: polígonos de sanciones activas, zonas de conflicto, bloqueos. Sincronizado con el cursor temporal. | Alto (nuevos GeoJSON + `index.html`) |

### Media prioridad

| Idea | Descripción | Esfuerzo estimado |
|---|---|---|
| **Búsqueda con operadores booleanos** | Parser JS para `ucrania & misiles & !otan` en topbar. Atajo `/`. | Bajo (solo `index.html`) |
| **Panel de detalle enriquecido** | Mostrar explícitamente las fuentes y el proceso de verificación en el popup. | Bajo (solo `index.html`) |
| **Threads / análisis en profundidad** | Sección de análisis vinculada a los marcadores del mapa. | Alto (nuevo backend) |

### Diferencias estratégicas a mantener

| Lo que GeoConfirmed hace | Lo que nosotros hacemos diferente |
|---|---|
| Solo eventos con prueba visual | Cubrimos crisis sin representación visual (sanciones, diplomacia, economía) |
| 100% verificación manual | Flujo RSS automatizado + revisión humana → escala mejor |
| Solo conflictos armados + OSINT | Cubrimos crisis económicas, diplomáticas, cibernéticas |
| Sin canal de distribución | Briefings Telegram para suscriptores |

---

## 10. Fuentes consultadas

- [GeoConfirmed.org](https://geoconfirmed.org/)
- [GeoConfirmed QGIS Plugin](https://plugins.qgis.org/plugins/geoconfirmed_qgis/)
- [GitHub — GeoConfirmed-QGIS (Silverfish94)](https://github.com/Silverfish94/GeoConfirmed-QGIS)
- [GitHub — osint-geo-extractor](https://github.com/conflict-investigations/osint-geo-extractor)
- [Google Maps Mania — Geolocating Visual Media in Conflict Zones](https://googlemapsmania.blogspot.com/2024/10/geolocating-visual-media-in-conflict.html)
- [ThreadReaderApp — @GeoConfirmed threads](https://threadreaderapp.com/user/GeoConfirmed)
- [GeoConfirmed UI Update anuncio (abril 2025)](https://x.com/GeoConfirmed/status/1914765173425840400)
- [GeoConfirmed anuncio mejoras workflow (mayo 2025)](https://x.com/GeoConfirmed/status/1955230043174584697)
