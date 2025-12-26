import asyncio
from scraper import SIIScraper
import os

async def test_reach():
    # Usamos credenciales falsas solo para ver si el script llega al login y maneja el error correctamente
    scraper = SIIScraper("12345678-5", "clave_falsa")
    print("Iniciando prueba de conectividad...")
    success = await scraper.get_carpeta_tributaria("test.pdf")
    if not success:
        print("La prueba terminó (con error esperado por credenciales falsas).")
        if os.path.exists("error_123456785.png"):
            print(">>> Se capturó el pantallazo del login. El navegador y el sigilo (stealth) están funcionando.")
    else:
        print("La prueba tuvo un resultado inesperado.")

if __name__ == "__main__":
    asyncio.run(test_reach())
