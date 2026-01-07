import asyncio
from scraper import SIIScraper
import sys

# Forzamos codificación UTF-8 para consola
sys.stdout.reconfigure(encoding='utf-8')

async def main():
    print("--- INICIANDO DIAGNÓSTICO SIMPLE ---")
    scraper = SIIScraper("257236498", "Franco25#")
    
    try:
        # 1. Login
        page = await scraper._ensure_session()
        print("✅ Login correcto.")

        # 2. Ir a Propuesta F29 directamente
        print("➡️  Yendo a Propuesta F29...")
        await page.goto("https://www4.sii.cl/propuestaf29ui/#/")
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(5)

        # 3. Intentar detectar el año/mes (Periodo actual)
        # A veces aparece una tabla de periodos.
        print("👀  Buscando estado del periodo...")
        # Check if we see "Continuar" or specific period buttons
        # Just dump this state first just in case
        await page.screenshot(path="debug_step1_propuesta.png")

        # Intentar flujo "automático" de clicks comunes
        # Click en diciembre si existe, o 'Continuar'
        try:
            # Selector genérico para botón de accion en la tabla de periodos
            # Buscamos un botón que diga "Declarar" o "Pendiente" o el icono
            # La lógica del scraper original usa selectores muy especificos, intentemos reutilizar la visual
            pass 
        except:
             pass
        
        # Para saltarnos la complejidad, vamos a usar el scraper.navigate_to_f29_from_home
        # PERO necesitamos que NO cierre el browser.
        # Como no puedo modificar el scraper ahora mismo sin reiniciar uvicorn potencialmente (aunque es un script aparte),
        # voy a COPY-PASTE la parte crítica de la navegación del scraper.py aquí para ajustarla.
        
        print("⚠️  Intentando navegación directa al Formulario RFI...")
        # URL Final: https://www4.sii.cl/rfiInternet/?origen=PROPUESTA&accionPpta=PPTA-F29-COMPLETA
        await page.goto("https://www4.sii.cl/rfiInternet/?origen=PROPUESTA&accionPpta=PPTA-F29-COMPLETA")
        await asyncio.sleep(8) # Espera larga para carga de scripts
        
        print("📸  Tomando foto del Formulario Final...")
        await page.screenshot(path="debug_final_form.png")
        
        print("💾  Guardando HTML completo...")
        html = await page.content()
        with open("f29_dump.html", "w", encoding="utf-8") as f:
            f.write(html)
            
        print("✅  Dump finalizado. Archivo: f29_dump.html")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        await scraper.close_session()

if __name__ == "__main__":
    asyncio.run(main())
