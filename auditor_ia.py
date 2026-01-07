import os
import httpx
import json

class AuditorIA:
    def __init__(self):
        self.api_url = os.getenv("AI_API_URL", "https://recuperadora-api-ia-free.nojauc.easypanel.host/v1/chat/completions")
        self.api_key = os.getenv("AI_API_KEY", "mi_proxy_secreto")
    
    async def analizar_f29(self, data_scouting: dict):
        """
        Envía los datos recolectados por el scraper a la IA para obtener un análisis tributario.
        """
        
        system_prompt = """Eres un Auditor Tributario de nivel SaaS Contable. Tu tarea es analizar los datos del F29 y asesorar al cliente con máxima proactividad. 

REGLAS OBLIGATORIAS:
1. TABLA DE RESUMEN: Inicia siempre tu respuesta con una tabla markdown llamada 'Resumen Contable' que incluya: [538] Ventas, [511] Crédito Facturas, [504] Remanente Ant., [537] Crédito del Mes y [91] Total a Pagar.
2. LÓGICA DE NEGOCIO PROACTIVA:
   - Validación de Arrastre: Si ves el Código 504, comenta si es consistente (ej: 'El remanente de $X millones es una fortaleza').
   - Alerta de Pago PPM: Si el Código 91 es > 0 debido al PPM (Código 62), advierte claramente que aunque haya remanente de IVA, el PPM debe pagarse en efectivo.
3. 🚨 ALERTA DE RCV (CRÍTICO): Si el JSON muestra 'rcv_pendientes' con IVA > 0, ESTO ES LO MÁS IMPORTANTE.
   - Debes poner una sección llamada "🚨 PÉRDIDA DE DINERO DETECTADA" justo después de la tabla.
   - Informa el monto de IVA que se está perdiendo y recomienda "Aceptar" las facturas de inmediato.
4. INICIATIVA: No esperes a que te pregunten.
5. MODO EXPERTO: Usa un tono ejecutivo.

Tu objetivo es que la automatización sea útil y ahorre dinero al cliente."""

        user_content = f"Aquí están los datos recolectados para el periodo {data_scouting.get('periodo', 'N/A')}:\n\n"
        user_content += json.dumps(data_scouting, indent=2, ensure_ascii=False)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ]

        payload = {
            "model": "multi-ia-proxy", # Tu proxy gestiona el modelo real
            "messages": messages,
            "stream": False
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(self.api_url, json=payload, headers=headers)
                response.raise_for_status()
                result = response.json()
                
                # Extraer la respuesta de la IA
                return result['choices'][0]['message']['content']
        except Exception as e:
            return f"Error al conectar con el Auditor IA: {str(e)}"

    async def chat_turn(self, conversation_history: list):
        """
        Mantiene una conversación continua enviando el historial completo.
        """
        payload = {
            "model": "multi-ia-proxy",
            "messages": conversation_history,
            "stream": False
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        try:
            async with httpx.AsyncClient(timeout=40.0) as client:
                response = await client.post(self.api_url, json=payload, headers=headers)
                response.raise_for_status()
                return response.json()['choices'][0]['message']['content']
        except Exception as e:
            return f"Error en el chat: {str(e)}"

# Instancia global para ser usada por los endpoints
auditor = AuditorIA()
