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
        
        system_prompt = """Eres un Auditor Tributario experto en el sistema chileno (SII) y en la declaración mensual F29.
Tu misión es analizar los datos que el bot de scraping ha recolectado y entregar un resumen humano, claro y ejecutivo.

Debes seguir estas reglas:
1. Valida si el reajuste del remanente (Código 504) es correcto según la UTM de los dos meses.
2. Compara el RCV con la Propuesta del SII para detectar discrepancias en el Crédito Fiscal.
3. Identifica si hay retenciones de honorarios (BHE) que deban ser pagadas.
4. Genera una lista de 'Alertas' (Flags) si encuentras riesgos.
5. Genera una lista de 'Consultas al Usuario' (decisiones estratégicas).

Habla en un tono profesional pero cercano, directo al grano.
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
