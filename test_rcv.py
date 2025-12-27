import requests
import json

# Configuración
API_URL = "http://localhost:8000/sii/rcv-resumen"
API_KEY = "mi_llave_secreta_123"

payload = {
    "rut": "25723649-8",
    "clave": "Franco25#"
}

headers = {
    "x-api-key": API_KEY,
    "Content-Type": "application/json"
}

print("--- Probando Extracción de RCV ---")
try:
    response = requests.post(API_URL, json=payload, headers=headers)
    if response.status_code == 200:
        print("✅ Éxito!")
        print(json.dumps(response.json(), indent=4, ensure_ascii=False))
    else:
        print(f"❌ Error {response.status_code}")
        print(response.text)
except Exception as e:
    print(f"❌ Error de conexión: {e}")
