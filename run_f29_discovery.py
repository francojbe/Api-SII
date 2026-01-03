import asyncio
from playwright.async_api import async_playwright
from scraper import SIIScraper
import json

async def discover_f29_state():
    rut = "257236498"
    clave = "Franco25#"
    
    print(f"🕵️ Iniciando Descubrimiento F29 para RUT: {rut}")
    scraper = SIIScraper(rut, clave)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True) 
        context = await browser.new_context(
            viewport={'width': 1366, 'height': 768},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        try:
            # 1. Login
            await scraper._login(page)
            await asyncio.sleep(5)
            
            # 2. Navegar a Declarar (URL directa que intentamos antes)
            print("🚀 Navegando a Declarar F29...")
            await page.goto("https://www4.sii.cl/formulario29internetui/#/declarar", wait_until="networkidle")
            await asyncio.sleep(15) # Tiempo extra para GWT
            
            print(f"📍 URL Actual: {page.url}")
            
            # 3. Inspección Profunda de Frames y Contenido
            print("🚀 Analizando contenido y frames...")
            frames = page.frames
            for i, f in enumerate(frames):
                try:
                    f_text = await f.evaluate("() => document.body.innerText")
                    if "Periodo" in f_text or "2025" in f_text or "Enero" in f_text:
                        print(f"✅ Frame {i} parece tener contenido relevante:")
                        print(f"| {f_text[:200].strip()}...")
                except:
                    pass

            # Listar botones visibles
            botones = await page.evaluate("""() => {
                return Array.from(document.querySelectorAll('button, a, input[type="button"]'))
                            .filter(el => el.offsetParent !== null) // Solo visibles
                            .map(el => el.innerText || el.value)
                            .filter(t => t && t.trim().length > 0);
            }""")
            print(f"🔘 Botones Visibles: {botones[:15]}")

            # Tomar captura final
            await page.screenshot(path="f29_discovery_final.png")
            print("📸 Captura final guardada.")

        except Exception as e:
            print(f"❌ Error: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(discover_f29_state())
