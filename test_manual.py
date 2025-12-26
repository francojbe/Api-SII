import asyncio
from scraper import SIIScraper
import os

# ==========================================
# CONFIGURACIÓN DE PRUEBA (EDITA AQUÍ)
# ==========================================

# 1. Tus credenciales del SII
RUT_DUEÑO = "12.345.678-9"
CLAVE_SII = "TU_CLAVE_AQUI"

# 2. Datos del destinatario
DEST_RUT = "12.345.678-9"
DEST_NOMBRE = "" # Se autocompletará al presionar Enter en el RUT
DEST_CORREO = "tu@correo.com"
DEST_INSTITUCION = "OTRA INSTITUCION" # Nombre para 'Otra Institución'

# ==========================================

async def ejecutar_prueba():
    print(f"🚀 Iniciando prueba completa para RUT: {RUT_DUEÑO}")
    
    scraper = SIIScraper(RUT_DUEÑO, CLAVE_SII)
    
    datos_envio = {
        "dest_rut": DEST_RUT,
        "dest_correo": DEST_CORREO,
        "dest_institucion": DEST_INSTITUCION
    }
    
    nombre_archivo = f"carpeta_final_{RUT_DUEÑO.replace('.', '')}.pdf"
    
    exito = await scraper.get_carpeta_tributaria(nombre_archivo, datos_envio)
    
    if exito:
        print(f"\n✅ ¡PRUEBA EXITOSA!")
        print(f"📂 Archivo generado: {os.path.abspath(nombre_archivo)}")
    else:
        print("\n❌ La prueba falló.")
        print("🔍 Revisa las capturas de pantalla para ver el error.")

if __name__ == "__main__":
    asyncio.run(ejecutar_prueba())
