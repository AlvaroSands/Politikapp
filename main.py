from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import uvicorn
import json

app = FastAPI()

@app.get("/api/noticias")
async def api_noticias():
    # El motor web solo lee la base de datos, ¡súper rápido y seguro!
    try:
        with open("datos.json", "r", encoding="utf-8") as f:
            noticias = json.load(f)
            return noticias
    except Exception as e:
        print(f"Error leyendo la base de datos: {e}")
        return []

@app.get("/", response_class=HTMLResponse)
async def pagina_principal():
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()

if __name__ == "__main__":
    # Importante: para servidores en la nube, solemos usar un puerto dinámico, 
    # pero para local dejamos el 8000. Luego el servidor en la nube lo adaptará.
    import os
    puerto = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=puerto)