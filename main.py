from fastapi import FastAPI, HTTPException, BackgroundTasks, Header
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
import os
import uuid
import asyncio
from scraper import SIIScraper

app = FastAPI(
    title="Cerebro SII - Automatizaciones",
    description="Microservicio para automatizar trámites en el SII (Carpeta Tributaria, etc.)",
    version="1.0.0"
)

# Configuración de Seguridad Simple
API_KEY_CREDENTIAL = os.getenv("API_KEY_SCII", "mi_llave_secreta_123")

class CarpetaRequest(BaseModel):
    rut_dueño: str
    clave_sii: str
    dest_rut: str
    dest_correo: str
    dest_institucion: Optional[str] = "OTRA INSTITUCION"

class RCVRequest(BaseModel):
    rut: str
    clave: str

# Directorio para archivos generados
TEMP_DIR = "temp_pdfs"
if not os.path.exists(TEMP_DIR):
    os.makedirs(TEMP_DIR)

def cleanup_file(path: str):
    """Elimina el archivo después de un tiempo para no llenar el disco."""
    try:
        if os.path.exists(path):
            os.remove(path)
            print(f"Archivo eliminado: {path}")
    except Exception as e:
        print(f"Error al limpiar archivo: {e}")

@app.get("/")
def health_check():
    return {"status": "online", "service": "automatizaciones-sii"}

@app.post("/sii/rcv-resumen")
async def api_rcv_resumen(
    req: RCVRequest, 
    x_api_key: str = Header(None)
):
    # Validación básica de API Key
    if x_api_key != API_KEY_CREDENTIAL:
        raise HTTPException(status_code=403, detail="Acceso denegado: API Key inválida.")

    scraper = SIIScraper(req.rut, req.clave)
    
    # Ejecutar el scraper
    data = await scraper.get_rcv_resumen()
    
    if data is None:
        raise HTTPException(
            status_code=500, 
            detail="Error al extraer RCV. Verifica credenciales o el estado de la web del SII."
        )
    
    return {
        "status": "success",
        "rut": req.rut,
        "periodo": "actual",
        "resumen_compras": data
    }

@app.post("/sii/descargar-carpeta")
async def api_descargar_carpeta(
    req: CarpetaRequest, 
    background_tasks: BackgroundTasks,
    x_api_key: str = Header(None)
):
    # Validación básica de API Key
    if x_api_key != API_KEY_CREDENTIAL:
        raise HTTPException(status_code=403, detail="Acceso denegado: API Key inválida.")

    filename = f"carpeta_{req.rut_dueño.replace('-', '')}_{uuid.uuid4().hex[:6]}.pdf"
    file_path = os.path.join(TEMP_DIR, filename)
    
    scraper = SIIScraper(req.rut_dueño, req.clave_sii)
    
    datos_envio = {
        "dest_rut": req.dest_rut,
        "dest_correo": req.dest_correo,
        "dest_institucion": req.dest_institucion
    }
    
    # Ejecutar el scraper
    success = await scraper.get_carpeta_tributaria(file_path, datos_envio)
    
    if not success:
        # Intentamos borrar si quedó un archivo corrupto
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(
            status_code=500, 
            detail="Error al generar carpeta. Verifica credenciales o el estado de la web del SII."
        )
    
    # Programar eliminación del archivo en 5 minutos para dar tiempo a la descarga
    # pero no dejarlo para siempre en el servidor.
    background_tasks.add_task(cleanup_file, file_path)
    
    return FileResponse(
        path=file_path,
        filename=f"Carpeta_Tributaria_{req.rut_dueño}.pdf",
        media_type='application/pdf'
    )

if __name__ == "__main__":
    import uvicorn
    # En producción (Docker/Easypanel), el puerto lo maneja el host
    uvicorn.run(app, host="0.0.0.0", port=8000)
