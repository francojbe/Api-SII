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
        
        system_prompt = """Eres un Auditor Tributario de nivel SaaS Contable. Tu tarea es analizar los datos del F29 y asesorar al cliente de forma personalizada.
Analiza los datos recibidos (Ventas, Compras, PPM, Remanentes) y:
1. Identifica anomalías o inconsistencias.
2. Explica claramente la situación del IVA (Crédito vs Débito) y el saldo final.
3. Si hay pagos pendientes (Código 91), indica el monto y el concepto.
4. Sugiere acciones estratégicas basadas estrictamente en los números encontrados.
5. Mantén un tono profesional, experto y directo. Básate solo en los datos proporcionados ahora.
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
