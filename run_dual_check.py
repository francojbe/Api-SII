import asyncio
from scraper_anual import SIIScraperAnual
import json

async def test_full_year_dual():
    rut = "257236498"
    clave = "Franco25#"
    
    print(f"🚀 Iniciando prueba de Consolidación DUAL (Compras y Ventas) para RUT: {rut}")
    scraper = SIIScraperAnual(rut, clave)
    
    try:
        # Lo corremos en headless para la consola
        resultado = await scraper.get_rcv_ultimos_12_meses(headless=True)
        
        if resultado:
            print("\n✅ EXTRACCIÓN COMPLETADA EXITOSAMENTE")
            
            # Guardamos para revisión rápida
            with open("temp_dual.json", "w", encoding="utf-8") as f:
                json.dump(resultado, f, indent=4, ensure_ascii=False)
            
            print("\n--- RESUMEN DE EXTRACCIÓN ---")
            for item in resultado['data']:
                periodo = item.get('periodo', 'N/A')
                c_count = len(item.get('compras', [])) if "compras" in item else 0
                v_count = len(item.get('ventas', [])) if "ventas" in item else 0
                print(f"📅 {periodo} -> Compras: {c_count} items | Ventas: {v_count} items")
        else:
            print("\n❌ El scraper no devolvió resultados.")
            
    except Exception as e:
        print(f"\n❌ Error durante la ejecución: {e}")

if __name__ == "__main__":
    asyncio.run(test_full_year_dual())
