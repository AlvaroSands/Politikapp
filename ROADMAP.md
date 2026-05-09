# ROADMAP — Intel-Geo Command Center

> Contexto para Claude Code: lee este archivo antes de cualquier tarea de desarrollo.
> Refleja la sesión de planificación del 9 de mayo de 2026.

---

## Visión del proyecto

Convertir el mapa geopolítico local en un **servicio web público, automático y de referencia** para consultar noticias de geopolítica en tiempo real. El objetivo a medio plazo es que sea un sitio consultado habitualmente y que tenga presencia en X/Twitter como fuente de información geopolítica.

---

## Estado actual (mayo 2026)

| Componente | Estado |
|---|---|
| Mapa 3D interactivo (MapLibre GL JS v4) | Funcionando en local |
| Backend FastAPI + Uvicorn (`main.py`) | Funcionando en local |
| Actualizador RSS (`actualizador.py`) | Funcionando, ejecución manual |
| `datos.json` con 14+ crisis cubiertas | Completo |
| `requirements.txt` | Completo |
| `.gitignore` correctamente configurado | Listo |
| Git inicializado | Listo |
| GitHub | **Pendiente** — crear cuenta |
| Deploy en Railway | **Pendiente** |
| Dominio propio | **Pendiente** — Cloudflare Registrar |

---

## Infraestructura objetivo

### 1. Dominio
- Registrar en **Cloudflare Registrar** (~10 €/año, sin markup)
- DNS gestionado desde Cloudflare (integra perfectamente con Railway)
- Apuntar el dominio al servicio Railway mediante un CNAME

### 2. Hosting del backend
- **Railway** (opción principal) — detecta Python/FastAPI automáticamente, deploy desde GitHub con cada `git push`
- Alternativas descartadas: Render (hiberna en plan gratuito), Fly.io (requiere Dockerfile)
- Comando de arranque para producción: `uvicorn main:app --host 0.0.0.0 --port $PORT`
- Las variables de entorno (`.env`) se configuran en el panel de Railway, **nunca** se suben a GitHub

### 3. GitHub
- Crear cuenta en github.com
- Subir el repositorio (ya tiene git inicializado y `.gitignore` correcto)
- Railway se conecta al repo y hace deploy automático en cada push a `main`

---

## Tareas de desarrollo pendientes

### Alta prioridad — para el deploy

- [x] Crear `railway.toml` en la raíz del proyecto ✓
- [x] Verificar y completar `requirements.txt` (añadido `apscheduler==3.10.4`) ✓
- [ ] **Crear cuenta en GitHub** y hacer el primer push
- [ ] Conectar repositorio de GitHub con Railway
- [ ] (Opcional) Configurar `NEWS_API_KEY` en el panel de Railway si se añade NewsAPI en el futuro

### Media prioridad — auto-actualización en producción

~~`actualizador.py` ahora se ejecuta manualmente.~~ **Resuelto: APScheduler integrado en `main.py`** — el actualizador corre automáticamente cada 3 horas al arrancar el servidor.

- [x] **APScheduler integrado** en `main.py` con patrón `lifespan` moderno (FastAPI 0.135+) ✓
- [x] `ejecutar_actualizacion()` en `actualizador.py` ya era importable sin cambios ✓
- [x] Frecuencia decidida: **cada 3 horas** ✓
- [ ] Añadir más fuentes RSS: Reuters, Financial Times, Foreign Policy, El Confidencial Internacional

### Media prioridad — ampliación del sitio web

El objetivo es que sea un sitio con múltiples secciones, no solo el mapa:

- [ ] **Landing page** — presentación del proyecto, misión y metodología
- [ ] **Sección de análisis** — artículos o resúmenes editoriales por región
- [ ] **Sección por regiones** — filtrado geográfico (Europa, Oriente Medio, Asia-Pacífico, África, Américas)
- [ ] **Sección de tendencias** — qué crisis han escalado o desescalado esta semana
- [ ] **Newsletter o alertas** — suscripción por email (opcional, futuro)
- [ ] Navegación entre secciones (menú/header persistente)

### Baja prioridad — crecimiento y visibilidad

- [ ] Crear cuenta en **X/Twitter** para el proyecto
- [ ] Definir estrategia de contenido: posts automáticos cuando hay una crisis nueva, hilos de análisis
- [ ] **SEO básico**: meta tags descriptivos, Open Graph (para que los links en redes se vean bien), `sitemap.xml`
- [ ] **Analytics de privacidad**: Plausible o Umami (alternativas a Google Analytics sin cookies)
- [ ] Monetización a futuro: Ko-fi, Patreon, newsletter de pago, publicidad contextual

---

## Arquitectura objetivo (producción)

```
                         ┌─────────────────────────────────────────────┐
                         │              Railway (cloud)                 │
                         │                                              │
  Usuario                │  ┌──────────────┐     ┌─────────────────┐  │
  Browser ──────────────►│  │   FastAPI     │────►│   datos.json    │  │
                         │  │  (main.py)   │     │  (base de datos) │  │
                         │  └──────────────┘     └────────┬────────┘  │
                         │         ▲                       ▲            │
                         │         │                       │            │
                         │  ┌──────┴────────┐    ┌────────┴────────┐  │
                         │  │  APScheduler  │───►│  actualizador.py │  │
                         │  │  (cada 3h)    │    │  (parser RSS)    │  │
                         │  └──────────────┘    └────────┬────────┘  │
                         │                               │             │
                         └───────────────────────────────┼─────────────┘
                                                         │
                                           ┌─────────────▼──────────────┐
                                           │      Fuentes RSS externas   │
                                           │  BBC · Al Jazeera · Reuters │
                                           │  Foreign Policy · France 24  │
                                           └────────────────────────────┘

  DNS: Cloudflare → CNAME → Railway
  Auto-deploy: git push main → GitHub → Railway build
```

---

## Fuentes de noticias a considerar

| Fuente | Tipo | Coste |
|---|---|---|
| BBC World, Al Jazeera, France 24 | RSS | Gratis |
| Reuters | RSS | Gratis |
| Foreign Policy | RSS | Gratis |
| The Economist (world) | RSS | Gratis |
| GDELT Project | API | Gratis |
| NewsAPI.org | API | Gratis hasta 100 req/día |
| El Confidencial Internacional | RSS | Gratis |

---

## Notas importantes para Claude Code

1. **Nunca subir `.env` a GitHub** — las claves van en el panel de Railway como variables de entorno
2. **Nunca subir `entorno_mapa/`** — Railway instala las dependencias desde `requirements.txt`
3. `entorno_mapa/` está en `.gitignore` intencionalmente — no eliminar esa línea
4. El mapa consulta `/datos.json` cada 60 segundos — la auto-actualización ya está en el frontend
5. Los tiles de CARTO son gratuitos y no requieren token
6. MapLibre GL JS es open-source, sin límites de uso
7. El puerto lo asigna Railway mediante la variable `$PORT` — `main.py` ya lo lee correctamente con `os.environ.get("PORT", 8000)`

---

*Roadmap generado el 9 de mayo de 2026 — pulido y completado en la misma sesión*
