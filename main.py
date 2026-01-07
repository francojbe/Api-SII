from fastapi import FastAPI, HTTPException, BackgroundTasks, Header, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List
import os
import uuid
import asyncio
import json
from scraper import SIIScraper
from scraper_anual import SIIScraperAnual
from auditor_ia import auditor

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Cerebro SII - Automatizaciones",
    description="Microservicio para automatizar trámites en el SII (Carpeta Tributaria, etc.)",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- WEBSOCKET CONNECTION MANAGER ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_personal_message(self, message: dict, websocket: WebSocket):
        await websocket.send_json(message)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            await connection.send_json(message)

manager = ConnectionManager()

# --- LIVE AGENT WEBSOCKET ENDPOINT ---
@app.websocket("/ws/live-agent")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    scraper_instance = None
    try:
        while True:
            data = await websocket.receive_text()
            command_data = json.loads(data)
            
            if command_data.get("command") == "start_live_scout":
                rut = command_data.get("rut")
                clave = command_data.get("clave")
                
                await manager.send_personal_message({
                    "type": "log", 
                    "text": f"Iniciando agente para RUT: {rut}",
                    "log_type": "info"
                }, websocket)

                # Definir callback para el scraper
                async def scraper_logger(msg, log_type="info"):
                    await manager.send_personal_message({
                        "type": "log",
                        "text": msg,
                        "log_type": log_type
                    }, websocket)

                # Instanciar y ejecutar
                scraper_instance = SIIScraper(rut, clave, log_callback=scraper_logger)
                
                mes = command_data.get("mes")
                anio = command_data.get("anio")
                
                # Ejecutar en background para no bloquear el loop de lectura de WS
                # Usamos asyncio.create_task para que corra "en paralelo"
                task = asyncio.create_task(run_live_scout(scraper_instance, websocket, mes, anio))
                SESSIONS[rut] = {"scraper": scraper_instance, "task": task}

            elif command_data.get("command") == "confirm_f29_submission":
                rut = command_data.get("rut")
                banco = command_data.get("banco")
                if rut in SESSIONS:
                    scraper = SESSIONS[rut]["scraper"]
                    # Nota: Aquí necesitaríamos la instancia de 'page' activa.
                    # Por simplicidad en este MVP, asumimos que navigate_to_f29 dejó el browser abierto.
                    # En una versión pro, pasaríamos la página.
                    asyncio.create_task(run_final_submission(scraper, websocket, banco))
                else:
                    await manager.send_personal_message({"type": "log", "text": "❌ No hay una sesión activa para este RUT.", "log_type": "error"}, websocket)

    except WebSocketDisconnect:
        manager.disconnect(websocket)
        if scraper_instance:
             await scraper_instance.close_session()

async def run_final_submission(scraper, websocket, banco):
    try:
        # Recuperar la página del scraper (esto requiere que el scraper guarde la página)
        if not scraper.page:
            await manager.send_personal_message({"type": "log", "text": "❌ La sesión del navegador se cerró. Reinicia el scouting.", "log_type": "error"}, websocket)
            return

        result = await scraper.submit_f29(scraper.page, banco)
        if result:
            await manager.send_personal_message({
                "type": "log", 
                "text": f"✅ Declaración enviada con éxito. Folio: {result['folio']}", 
                "log_type": "success",
                "payload": result
            }, websocket)
        else:
            await manager.send_personal_message({"type": "log", "text": "❌ Falló el envío de la declaración.", "log_type": "error"}, websocket)
    except Exception as e:
        await manager.send_personal_message({"type": "log", "text": f"💥 Error en envío: {str(e)}", "log_type": "error"}, websocket)

async def run_live_scout(scraper, websocket, mes=None, anio=None):
    try:
        # Ejecutamos la navegación compleja
        result = await scraper.navigate_to_f29_from_home(mes, anio)
        
        if result:
             # GUARDAR CONTEXTO PARA EL CHAT POST-EJECUCIÓN
             rut_limpio = scraper.rut  # Asegurarnos de tener el RUT
             
             # Simulamos un scouting básico si no tenemos datos reales aún
             # Idealmente navigate_to_f29_from_home debería devolver los datos extraídos
             # Usar datos reales del scraper si devolvió un diccionario
             scouting_data = result if isinstance(result, dict) else {
                 "resumen": "Navegación en vivo completada exitosamente.",
                 "estado": "Formulario F29 accedido",
                 "rut": rut_limpio,
                 "datos": {}
             }
             
             # Obtener el análisis de la IA automáticamente
             await manager.send_personal_message({"type": "log", "text": "🤖 Solicitando análisis al Auditor IA...", "log_type": "info"}, websocket)
             analisis_ia = await auditor.analizar_f29(scouting_data)
             
             # Prompt enriquecido con los datos extraídos para el chat posterior
             datos_txt = json.dumps(scouting_data.get('datos', {}), indent=2)
             sys_prompt = f"""Eres un Auditor Tributario de nivel SaaS Contable. Acabas de realizar una nevegación EN VIVO para el RUT {rut_limpio}.
             Se extrajeron los siguientes datos:
             {datos_txt}
             
             Usa estos valores para el chat. Si el usuario pregunta qué hacer, guíalo según el análisis previo:
             {analisis_ia}
             """
             
             SESSION_CONTEXT[rut_limpio] = {
                 "scouting_data": scouting_data,
                 "base_system_prompt": sys_prompt,
                 "last_analysis": analisis_ia
             }

             await manager.send_personal_message({
                "type": "log",
                "text": "✅ Proceso finalizado con éxito.",
                "log_type": "success",
                "payload": {
                    "scouting": scouting_data,
                    "analisis_ia": analisis_ia
                }
            }, websocket)
             # Aquí podríamos enviar los datos finales si los tuviéramos
        else:
             await manager.send_personal_message({
                "type": "log",
                "text": "❌ El proceso finalizó sin resultados o con error.",
                "log_type": "error"
            }, websocket)
            
    except Exception as e:
        await manager.send_personal_message({
            "type": "log",
            "text": f"💥 Error crítico en agente: {str(e)}",
            "log_type": "error"
        }, websocket)
    finally:
        # Mantener la sesión abierta para permitir interacción (ej: enviar declaración)
        # await scraper.close_session()
        pass

# Configuración de Seguridad Simple
API_KEY_CREDENTIAL = os.getenv("API_KEY_SCII", "mi_llave_secreta_123")

# GESTOR DE SESIONES ACTIVAS (En memoria para esta fase de test)
# Estructura: { "rut": SIIScraperInstance }
# Estructura: { "rut": SIIScraperInstance }
SESSIONS = {}
# Estructura: { "rut": { "scouting_data": dict, "history": list } }
SESSION_CONTEXT = {}

class ChatRequest(BaseModel):
    rut: str
    message: str
    history: list

class CarpetaRequest(BaseModel):
    rut_dueño: str
    clave_sii: str
    dest_rut: str
    dest_correo: str
    dest_institucion: Optional[str] = "OTRA INSTITUCION"

class RCVRequest(BaseModel):
    rut: str
    clave: str

class RCVAnualRequest(BaseModel):
    rut: str
    clave: str

class F29Request(BaseModel):
    rut: str
    clave: str
    anio: str
    mes: str
    es_propuesta: Optional[bool] = True

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

@app.post("/sii/rcv-anual-consolidado")
async def api_rcv_anual(
    req: RCVAnualRequest, 
    x_api_key: str = Header(None)
):
    if x_api_key != API_KEY_CREDENTIAL:
        raise HTTPException(status_code=403, detail="Acceso denegado: API Key inválida.")

    scraper = SIIScraperAnual(req.rut, req.clave)
    data = await scraper.get_rcv_ultimos_12_meses()
    
    if data is None:
        raise HTTPException(
            status_code=500, 
            detail="Error al extraer RCV anual. Verifica credenciales o el estado de la web del SII."
        )
    
    return {
        "status": "success",
        "data": data
    }

@app.post("/sii/f29-datos")
async def api_f29_datos(
    req: F29Request, 
    x_api_key: str = Header(None),
    ruta_oficial: Optional[bool] = False
):
    if x_api_key != API_KEY_CREDENTIAL:
        raise HTTPException(status_code=403, detail="Acceso denegado: API Key inválida.")

    scraper = SIIScraper(req.rut, req.clave)
    
    # Elección de estrategia de navegación
    if req.es_propuesta:
        if ruta_oficial:
            print(f"[{req.rut}] Iniciando navegacin por ruta oficial (Servicios Online)...")
            success = await scraper.navigate_to_f29_official_path(req.anio, req.mes)
            if not success:
                raise HTTPException(status_code=500, detail="Error en navegación por ruta oficial.")
            # Después de navegar, extraemos los datos (asumiendo que navigate dejó la página lista)
            # Nota: get_f29_data podría ser refactorizado para extraer de la página actual, 
            # pero por ahora get_f29_data hace su propio browser context.
            # Para esta demo, usamos get_f29_data directamente que es lo más estable.
            data = await scraper.get_f29_data(req.anio, req.mes, es_propuesta=True)
        else:
            print(f"[{req.rut}] Iniciando extracción desde panel de alertas (Home)...")
            data = await scraper.navigate_to_f29_from_home(req.mes, req.anio)
    else:
        # Consulta histórica tradicional
        data = await scraper.get_f29_data(req.anio, req.mes, es_propuesta=False)
    
    if data is None:
        raise HTTPException(
            status_code=500, 
            detail="Error al extraer datos del F29. Verifica si el periodo está disponible o las credenciales."
        )
    
    return {
        "status": "success",
        "data": data
    }

@app.post("/sii/f29-scouting")
async def api_f29_scouting(
    req: F29Request, 
    x_api_key: str = Header(None)
):
    if x_api_key != API_KEY_CREDENTIAL:
        raise HTTPException(status_code=403, detail="Acceso denegado: API Key inválida.")

    # Reutilizar o crear sesión persistente
    if req.rut not in SESSIONS:
        SESSIONS[req.rut] = SIIScraper(req.rut, req.clave)
    
    scraper = SESSIONS[req.rut]
    
    # Obtener los datos técnicos del scouting
    scouting_data = await scraper.prepare_f29_scouting(req.anio, req.mes)
    
    # ENVIAR A TU API DE IA (Easypanel)
    print(f"[{req.rut}] Solicitando anlisis a Auditor IA en Easypanel...")
    
    # SYSTEM PROMPT INICIAL
    sys_prompt = f"""Eres un Auditor Tributario experto. Analiza estos datos del SII para el RUT {req.rut} (Periodo {req.mes}/{req.anio}).
    
    Datos Técnicos:
    {scouting_data}
    
    Tu objetivo es guiar al usuario para validar su F29. Sé breve y estratégico. Si ves discrepancias, alértalas.
    """
    
    # Iniciar historial de contexto
    SESSION_CONTEXT[req.rut] = {
        "scouting_data": scouting_data,
        "base_system_prompt": sys_prompt
    }

    analisis_ia = await auditor.analizar_f29(scouting_data)
    
    return {
        "status": "success",
        "session_active": True,
        "scouting": scouting_data,
        "analisis_ia": analisis_ia
    }

@app.post("/sii/chat-interaction")
async def api_chat_interaction(
    req: ChatRequest,
    x_api_key: str = Header(None)
):
    if x_api_key != API_KEY_CREDENTIAL:
        raise HTTPException(status_code=403, detail="Acceso denegado")

    if req.rut not in SESSION_CONTEXT:
        raise HTTPException(status_code=404, detail="No hay contexto de auditoría. Ejecuta el Scouting primero.")
    
    context = SESSION_CONTEXT[req.rut]
    
    # Construir historial enriquecido con el System Prompt
    full_history = [{"role": "system", "content": context["base_system_prompt"]}] + req.history
    
    # Añadir mensaje actual del usuario
    full_history.append({"role": "user", "content": req.message})

    print(f"[{req.rut}] Procesando mensaje de chat...")
    respuesta_ia = await auditor.chat_turn(full_history)
    
    return {
        "status": "success",
        "reply": respuesta_ia
    }

@app.post("/sii/session-close")
async def api_session_close(
    req: RCVRequest, # Usamos RCVRequest por simplicidad ya que solo pide rut/clave
    x_api_key: str = Header(None)
):
    if x_api_key != API_KEY_CREDENTIAL:
        raise HTTPException(status_code=403, detail="Acceso denegado: API Key inválida.")

    if req.rut in SESSIONS:
        scraper = SESSIONS[req.rut]
        await scraper.close_session()
        del SESSIONS[req.rut]
        return {"status": "success", "message": f"Sesión cerrada para el RUT {req.rut}"}
    
    return {"status": "info", "message": "No había una sesión activa para este RUT."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
