import asyncio
from playwright.async_api import async_playwright
from scraper import SIIScraper
import json

async def discover_home_alerts():
    rut = "257236498"
    clave = "Franco25#"
    
    print(f"🕵️ Análisis de Alertas en Home para RUT: {rut}")
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
            # Esperar a que la Home cargue completamente
            print("⏳ Esperando carga de la Home (Mi SII)...")
            await page.wait_for_selector("text=Responsabilidades Tributarias", timeout=20000)
            
            print(f"📍 URL Actual: {page.url}")
            
            # 2. Extraer información de "Responsabilidades Tributarias"
            print("🔍 Buscando cuadro de 'Declaraciones'...")
            
            alert_data = await page.evaluate("""() => {
                const results = {};
                // Buscamos contenedores que tengan texto relacionado
                const items = Array.from(document.querySelectorAll('div, a, span'))
                                   .filter(el => el.innerText.includes('Declaraciones') || el.innerText.includes('Declaraciones Juradas') || el.innerText.includes('Pagos'));
                
                // Intentamos encontrar el número específico asociado a 'Declaraciones'
                // Basado en la estructura típica de esa sección
                const boxes = document.querySelectorAll('.cuadro, .card, div');
                const declaracionesBox = Array.from(boxes).find(b => b.innerText.includes('Declaraciones') && !b.innerText.includes('Juradas'));
                
                if (declaracionesBox) {
                    results.found = true;
                    results.fullText = declaracionesBox.innerText.trim();
                    // Intentamos separar el número
                    const lines = declaracionesBox.innerText.split('\\n').map(l => l.trim()).filter(l => l !== "");
                    results.details = lines;
                } else {
                    results.found = false;
                }
                
                return results;
            }""")
            
            if alert_data['found']:
                print(f"✅ ¡Detectado!: {alert_data['fullText'].replace('\\n', ' ')}")
                print(f"📊 Desglose: {alert_data['details']}")
            else:
                print("❌ No se encontró el cuadro de 'Declaraciones' con el texto esperado.")

            # 3. Ver si hay un link específico en ese número "1"
            print("🖱️ Buscando si el número '1' es clickable...")
            link_selector = "text=1" # Un poco genérico, afinemos
            clickable_elements = await page.evaluate("""() => {
                return Array.from(document.querySelectorAll('a, button'))
                            .filter(el => el.innerText.includes('1') && el.offsetParent !== null)
                            .map(el => ({ text: el.innerText.trim(), href: el.href || 'JS Action' }));
            }""")
            print(f"🔗 Elementos clickables con '1': {clickable_elements}")

            # 4. Tomar captura del área de interés
            await page.screenshot(path="home_alerts_detected.png")
            print("📸 Captura de alertas guardada.")

        except Exception as e:
            print(f"❌ Error durante el análisis: {e}")
            # Si falla el selector, tomamos captura igual para debug
            await page.screenshot(path="error_home_discovery.png")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(discover_home_alerts())
