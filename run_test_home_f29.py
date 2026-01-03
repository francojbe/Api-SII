import asyncio
from scraper import SIIScraper

async def run_f29_from_home():
    rut = "257236498"
    clave = "Franco25#"
    
    print(f"🚀 Iniciando prueba: Navegación F29 desde Home Alerts para RUT: {rut}")
    scraper = SIIScraper(rut, clave)
    
    resultado = await scraper.navigate_to_f29_from_home()
    
    if resultado:
        print("\n🎉 ¡EXTRACCIÓN COMPLETADA!")
        print(f"📅 Periodo: {resultado['periodo']}")
        print("📊 Datos extraídos:")
        for cod, valor in resultado['datos'].items():
            print(f"   🔹 Código {cod}: {valor}")
        
        print("\n📸 Revisa 'f29_extracted_proposal.png' para validar visualmente.")
    else:
        print("\n❌ No se pudo extraer información del F29.")

if __name__ == "__main__":
    asyncio.run(run_f29_from_home())
