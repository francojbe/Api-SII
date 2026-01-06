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
        
        system_prompt = """Eres un Auditor Tributario de nivel SaaS Contable. Tu tarea es analizar los datos del F29 y asesorar al cliente.
Basado en los datos:
1. Ventas: Si las ventas (Código 538/589) son $0, pregunta si falta emitir algún documento de último minuto.
2. Compras: Indica el IVA crédito nuevo (Código 511). Pregunta si hay facturas 'Pendientes' en el RCV que no se sumaron.
3. Pago (Código 91): Si hay un monto a pagar (ej: por PPM), avisa claramente el monto. 
4. Sugerencia estratégica: Si el pago es bajo (ej: < $1.000), sugiere aumentar el PPM voluntariamente para ahorrar para la Operación Renta.
5. Remanente: Comenta si el remanente (Código 504/77) es una fortaleza para los próximos meses.

Sé ejecutivo, proactivo y usa un tono de experto financiero. Resume siempre: IVA Débito, IVA Crédito, Remanente y Total a Pagar.
"""

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
