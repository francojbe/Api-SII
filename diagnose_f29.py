import asyncio
from scraper import SIIScraper
import os

async def run_diagnosis():
    # Credenciales de prueba (Extraídas de tu entorno de dev)
    RUT = "257236498"
    CLAVE = "Franco25#" 
    
    print(f"🔍 Iniciando Diagnóstico de Extracción para RUT: {RUT}")
    scraper = SIIScraper(RUT, CLAVE)
    
    try:
        page = await scraper._ensure_session()
        
        # Usamos la navegación PROBADA del scraper real
        print("🚀 Ejecutando navegación robusta (Scraper Logic)...")
        resultado_nav = await scraper.navigate_to_f29_from_home()
        
        if not resultado_nav:
            print("❌ La navegación falló según el scraper.")
            return

        print("✅ Navegación reportada como exitosa. Analizando HTML in-situ...")
        # El browser ya debería estar en el formulario final
        
        print("📸 Tomando foto de evidencia...")
        await page.screenshot(path="debug_f29_structure.png", full_page=True)

        print("\n🧪 EXTRAYENDO HTML DE LA FILA 504 (REMANENTE):")
        # Script JS de inspección profunda
        html_dump = await page.evaluate("""() => {
            const dumpRow = (code) => {
                // Buscamos cualquier cosa que tenga el código [code]
                const allElements = Array.from(document.querySelectorAll('*'));
                const label = allElements.find(el => el.innerText && el.innerText.includes('[' + code + ']') && el.children.length === 0);
                
                if (!label) return `❌ No encontré el texto [${code}]`;
                
                // Subir hasta encontrar el TR
                const row = label.closest('tr');
                if (!row) return `⚠️ Encontré el label [${code}] pero no está dentro de un TR. Parent: <${label.parentElement.tagName}>`;
                
                return `✅ HTML ENCONTRADO PARA [${code}]:\n` + row.outerHTML;
            };
            
            return {
                code504: dumpRow('504'),
                code538: dumpRow('538'),
                code91: dumpRow('91')
            };
        }""")
        
        print(html_dump['code538'])
        print("\n" + "="*50 + "\n")
        print(html_dump['code504'])
        print("\n" + "="*50 + "\n")
        print(html_dump['code91'])

    except Exception as e:
        print(f"💥 Error en diagnóstico: {e}")
    finally:
        await scraper.close_session()

if __name__ == "__main__":
    asyncio.run(run_diagnosis())
