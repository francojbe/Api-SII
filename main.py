from fastapi import FastAPI, HTTPException, BackgroundTasks, Header, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List
import os
import uuid
import asyncio
import json
from datetime import datetime, timedelta, timezone
from scraper import SIIScraper
from scraper_anual import SIIScraperAnual
from auditor_ia import auditor

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Cerebro SII - Automatizaciones",
    description="Microservicio para automatizar trÃ¡mites en el SII (Carpeta Tributaria, etc.)",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- HELPER PARA LOGS CON HORA CHILE ---
def get_chile_time():
    return datetime.now(timezone(timedelta(hours=-3))).strftime("%Y-%m-%d %H:%M:%S")

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
                    # Nota: AquÃ­ necesitarÃ­amos la instancia de 'page' activa.
                    # Por simplicidad en este MVP, asumimos que navigate_to_f29 dejÃ³ el browser abierto.
                    # En una versiÃ³n pro, pasarÃ­amos la pÃ¡gina.
                    asyncio.create_task(run_final_submission(scraper, websocket, banco))
                else:
                    await manager.send_personal_message({"type": "log", "text": "âŒ No hay una sesiÃ³n activa para este RUT.", "log_type": "error"}, websocket)

    except WebSocketDisconnect:
        manager.disconnect(websocket)
        if scraper_instance:
             await scraper_instance.close_session()

async def run_final_submission(scraper, websocket, banco):
    try:
        # Recuperar la pÃ¡gina del scraper (esto requiere que el scraper guarde la pÃ¡gina)
        if not scraper.page:
            await manager.send_personal_message({"type": "log", "text": "âŒ La sesiÃ³n del navegador se cerrÃ³. Reinicia el scouting.", "log_type": "error"}, websocket)
            return

        result = await scraper.submit_f29(scraper.page, banco)
        if result:
            await manager.send_personal_message({
                "type": "log", 
                "text": f"âœ… DeclaraciÃ³n enviada con Ã©xito. Folio: {result['folio']}", 
                "log_type": "success",
                "payload": result
            }, websocket)
        else:
            await manager.send_personal_message({"type": "log", "text": "âŒ FallÃ³ el envÃ­o de la declaraciÃ³n.", "log_type": "error"}, websocket)
    except Exception as e:
        await manager.send_personal_message({"type": "log", "text": f"ðŸ’¥ Error en envÃ­o: {str(e)}", "log_type": "error"}, websocket)

async def run_live_scout(scraper, websocket, mes=None, anio=None):
    try:
        # 1. Ejecutamos la navegaciÃ³n del F29 (Propuesta)
        result_f29 = await scraper.navigate_to_f29_from_home(mes, anio)
        
        # 2. Cruce de datos con el Registro de Compras (RCV) para detectar facturas pendientes
        # Esto es el "Siguiente Nivel"
        rcv_data = await scraper.check_pending_rcv(mes, anio)
        
        if result_f29:
             # GUARDAR CONTEXTO PARA EL CHAT POST-EJECUCIÃ“N
             rut_limpio = scraper.rut
             
             # Consolidar datos para la IA
             scouting_data = result_f29 if isinstance(result_f29, dict) else {
                 "resumen": "NavegaciÃ³n en vivo completada exitosamente.",
                 "estado": "Formulario F29 accedido",
                 "rut": rut_limpio,
                 "datos": {}
             }
             # Inyectar datos del RCV en el scouting
             scouting_data["rcv_pendientes"] = rcv_data if rcv_data else {"total_pendientes": 0, "iva_pendiente": 0}
             
             # Obtener el anÃ¡lisis de la IA automÃ¡ticamente
             await manager.send_personal_message({"type": "log", "text": "ðŸ¤– Solicitando anÃ¡lisis al Auditor IA...", "log_type": "info"}, websocket)
             analisis_ia = await auditor.analizar_f29(scouting_data)
             
             # Prompt enriquecido con los datos extraÃ­dos para el chat posterior
             datos_txt = json.dumps(scouting_data.get('datos', {}), indent=2)
             rcv_txt = json.dumps(scouting_data.get('rcv_pendientes', {}), indent=2)
             
             sys_prompt = f"""Eres un Auditor Tributario de nivel SaaS Contable. Acabas de realizar una nevegaciÃ³n EN VIVO para el RUT {rut_limpio}.
             Se extrajeron los siguientes datos del F29:
             {datos_txt}
             
             Y estos datos del Registro de Compras (RCV):
             {rcv_txt}
             
             Usa estos valores para el chat. Si ves facturas pendientes en el RCV, advierte que se estÃ¡ perdiendo IVA crÃ©dito.
             Si el usuario pregunta qué hacer, guíalo según el análisis previo:
             {analisis_ia}
             """
             
             SESSION_CONTEXT[rut_limpio] = {
                 "scouting_data": scouting_data,
                 "base_system_prompt": sys_prompt,
                 "last_analysis": analisis_ia
             }


             await manager.send_personal_message({
                 "type": "log",
                 "text": "✅ Auditoría de Agente Proactivo completada con éxito.",
                 "log_type": "success",
                 "payload": {
                     "scouting": scouting_data,
                     "analisis_ia": analisis_ia
                 }
             }, websocket)

             # ENVIAR EL ANÃLISIS COMO MENSAJE DE CHAT (Para que aparezca en el globo)
             # Usamos mÃºltiples campos para asegurar compatibilidad con el frontend
             await manager.send_personal_message({
                 "type": "chat",
                 "text": analisis_ia,
                 "message": analisis_ia,
                 "reply": analisis_ia,
                 "content": analisis_ia,
                 "sender": "ai"
             }, websocket)
             # AquÃ­ podrÃ­amos enviar los datos finales si los tuviÃ©ramos
        else:
             await manager.send_personal_message({
                "type": "log",
                "text": "âŒ El proceso finalizÃ³ sin resultados o con error.",
                "log_type": "error"
            }, websocket)
            
    except Exception as e:
        await manager.send_personal_message({
            "type": "log",
            "text": f"ðŸ’¥ Error crÃ­tico en agente: {str(e)}",
            "log_type": "error"
        }, websocket)
    finally:
        # Mantener la sesiÃ³n abierta para permitir interacciÃ³n (ej: enviar declaraciÃ³n)
        # await scraper.close_session()
        pass

# ConfiguraciÃ³n de Seguridad Simple
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
    rut_dueno: str
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
    """Elimina el archivo despuÃ©s de un tiempo para no llenar el disco."""
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
    # ValidaciÃ³n bÃ¡sica de API Key
    if x_api_key != API_KEY_CREDENTIAL:
        raise HTTPException(status_code=403, detail="Acceso denegado: API Key invÃ¡lida.")

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
    # ValidaciÃ³n bÃ¡sica de API Key
    if x_api_key != API_KEY_CREDENTIAL:
        raise HTTPException(status_code=403, detail="Acceso denegado: API Key invÃ¡lida.")

    filename = f"carpeta_{req.rut_dueno.replace('-', '')}_{uuid.uuid4().hex[:6]}.pdf"
    file_path = os.path.join(TEMP_DIR, filename)
    
    scraper = SIIScraper(req.rut_dueno, req.clave_sii)
    
    datos_envio = {
        "dest_rut": req.dest_rut,
        "dest_correo": req.dest_correo,
        "dest_institucion": req.dest_institucion
    }
    
    # Ejecutar el scraper
    success = await scraper.get_carpeta_tributaria(file_path, datos_envio)
    
    if not success:
        # Intentamos borrar si quedÃ³ un archivo corrupto
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(
            status_code=500, 
            detail="Error al generar carpeta. Verifica credenciales o el estado de la web del SII."
        )
    
    # Programar eliminaciÃ³n del archivo en 5 minutos para dar tiempo a la descarga
    # pero no dejarlo para siempre en el servidor.
    background_tasks.add_task(cleanup_file, file_path)
    
    return FileResponse(
        path=file_path,
        filename=f"Carpeta_Tributaria_{req.rut_dueno}.pdf",
        media_type='application/pdf'
    )

@app.post("/sii/rcv-anual-consolidado")
async def api_rcv_anual(
    req: RCVAnualRequest, 
    x_api_key: str = Header(None)
):
    if x_api_key != API_KEY_CREDENTIAL:
        raise HTTPException(status_code=403, detail="Acceso denegado: API Key invÃ¡lida.")

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
        raise HTTPException(status_code=403, detail="Acceso denegado: API Key invÃ¡lida.")

    scraper = SIIScraper(req.rut, req.clave)
    
    # ElecciÃ³n de estrategia de navegaciÃ³n
    if req.es_propuesta:
        if ruta_oficial:
            print(f"[{get_chile_time()}] [{req.rut}] Iniciando navegacin por ruta oficial (Servicios Online)...")
            success = await scraper.navigate_to_f29_official_path(req.anio, req.mes)
            if not success:
                raise HTTPException(status_code=500, detail="Error en navegaciÃ³n por ruta oficial.")
            # DespuÃ©s de navegar, extraemos los datos (asumiendo que navigate dejÃ³ la pÃ¡gina lista)
            # Nota: get_f29_data podrÃ­a ser refactorizado para extraer de la pÃ¡gina actual, 
            # pero por ahora get_f29_data hace su propio browser context.
            # Para esta demo, usamos get_f29_data directamente que es lo mÃ¡s estable.
            data = await scraper.get_f29_data(req.anio, req.mes, es_propuesta=True)
        else:
            print(f"[{get_chile_time()}] [{req.rut}] Iniciando extracciÃ³n desde panel de alertas (Home)...")
            data = await scraper.navigate_to_f29_from_home(req.mes, req.anio)
    else:
        # Consulta histÃ³rica tradicional
        data = await scraper.get_f29_data(req.anio, req.mes, es_propuesta=False)
    
    if data is None:
        raise HTTPException(
            status_code=500, 
            detail="Error al extraer datos del F29. Verifica si el periodo estÃ¡ disponible o las credenciales."
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
        raise HTTPException(status_code=403, detail="Acceso denegado: API Key invÃ¡lida.")

    # Reutilizar o crear sesiÃ³n persistente
    if req.rut not in SESSIONS:
        SESSIONS[req.rut] = SIIScraper(req.rut, req.clave)
    
    scraper = SESSIONS[req.rut]
    
    # Obtener los datos tÃ©cnicos del scouting
    scouting_data = await scraper.prepare_f29_scouting(req.anio, req.mes)
    
    # ENVIAR A TU API DE IA (Easypanel)
    print(f"[{req.rut}] Solicitando anlisis a Auditor IA en Easypanel...")
    
    # SYSTEM PROMPT INICIAL
    sys_prompt = f"""Eres un Auditor Tributario experto. Analiza estos datos del SII para el RUT {req.rut} (Periodo {req.mes}/{req.anio}).
    
    Datos TÃ©cnicos:
    {scouting_data}
    
    Tu objetivo es guiar al usuario para validar su F29. SÃ© breve y estratÃ©gico. Si ves discrepancias, alÃ©rtalas.
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
        raise HTTPException(status_code=404, detail="No hay contexto de auditorÃ­a. Ejecuta el Scouting primero.")
    
    context = SESSION_CONTEXT[req.rut]
    
    # Construir historial enriquecido con el System Prompt
    full_history = [{"role": "system", "content": context["base_system_prompt"]}] + req.history
    
    # AÃ±adir mensaje actual del usuario
    full_history.append({"role": "user", "content": req.message})

    print(f"[{get_chile_time()}] [{req.rut}] Procesando mensaje de chat...")
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
        raise HTTPException(status_code=403, detail="Acceso denegado: API Key invÃ¡lida.")

    if req.rut in SESSIONS:
        scraper = SESSIONS[req.rut]
        await scraper.close_session()
        del SESSIONS[req.rut]
        return {"status": "success", "message": f"SesiÃ³n cerrada para el RUT {req.rut}"}
    
    return {"status": "info", "message": "No habÃ­a una sesiÃ³n activa para este RUT."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
