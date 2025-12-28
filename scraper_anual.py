import asyncio
from playwright.async_api import async_playwright
from scraper import SIIScraper
import datetime

class SIIScraperAnual(SIIScraper):
    async def get_rcv_ultimos_12_meses(self, headless: bool = True):
        """Extrae los últimos 12 meses de RCV desde la fecha actual y los une en un solo JSON."""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=headless)
            context = await browser.new_context(
                viewport={'width': 1366, 'height': 768},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = await context.new_page()

            # Generar lista de los últimos 12 meses
            hoy = datetime.datetime.now()
            periodos = []
            for i in range(12):
                # Restar i meses a la fecha actual
                fecha_busqueda = hoy - datetime.timedelta(days=i*30) 
                # Ajuste más preciso para meses
                mes = hoy.month - i
                anio = hoy.year
                while mes <= 0:
                    mes += 12
                    anio -= 1
                periodos.append({"mes": str(mes).zfill(2), "anio": str(anio)})

            consolidado = {
                "rut": self.rut,
                "fecha_extraccion": hoy.isoformat(),
                "periodos_extraidos": len(periodos),
                "data": []
            }

            try:
                # 1. Login centralizado
                await self._login(page)

                # 2. Ir a la App de RCV
                print(f"[{self.rut}] Navegando al RCV para consolidación de últimos 12 meses...")
                await page.goto("https://www4.sii.cl/consdcvinternetui/#/index", wait_until="networkidle")

                # 3. Iterar por los periodos calculados
                for p_idx, periodo in enumerate(periodos):
                    mes_str = periodo["mes"]
                    anio_str = periodo["anio"]
                    
                    print(f"[{self.rut}] ({p_idx+1}/12) Procesando: {mes_str}/{anio_str}...")
                    
                    try:
                        await page.wait_for_selector("#periodoMes", timeout=10000)
                        
                        # Seleccionar Año (3er select)
                        selects = page.locator("select")
                        await selects.nth(2).select_option(label=anio_str)
                        
                        # Seleccionar Mes
                        await page.select_option("#periodoMes", value=mes_str)
                        
                        # Click en Consultar
                        btn_consultar = page.locator("button:has-text('Consultar')")
                        await btn_consultar.click()
                        
                        # Esperar a que la tabla se actualice
                        await asyncio.sleep(2)
                        await page.wait_for_load_state("networkidle")

                        # Extraer data
                        registros = await page.evaluate("""() => {
                            const rows = Array.from(document.querySelectorAll('table tbody tr'));
                            return rows.map(row => {
                                const cols = row.querySelectorAll('td');
                                if (cols.length >= 6) {
                                    return {
                                        tipo_doc: cols[0].innerText.trim(),
                                        cantidad: cols[1].innerText.trim(),
                                        neto: cols[3].innerText.trim(),
                                        iva: cols[4].innerText.trim(),
                                        total: cols[cols.length - 1].innerText.trim()
                                    };
                                }
                                return null;
                            }).filter(r => r !== null);
                        }""")
                        
                        consolidado["data"].append({
                            "periodo": f"{anio_str}-{mes_str}",
                            "registros": registros
                        })
                        print(f"[{self.rut}] ✅ {mes_str}/{anio_str} completado.")

                    except Exception as e:
                        consolidado["data"].append({
                            "periodo": f"{anio_str}-{mes_str}",
                            "error": str(e)
                        })
                        print(f"[{self.rut}] ⚠️ Error en {mes_str}/{anio_str}: {e}")

                return consolidado

            except Exception as e:
                print(f"[{self.rut}] ❌ Error crítico en consolidación: {str(e)}")
                return None
            finally:
                if headless:
                    await browser.close()
                else:
                    # Si no es headless, dejamos un momento para ver antes de cerrar
                    await asyncio.sleep(5)
                    await browser.close()

if __name__ == "__main__":
    # Test rápido si se ejecuta directamente
    import sys
    if len(sys.argv) > 2:
        rut = sys.argv[1]
        clave = sys.argv[2]
        scraper = SIIScraperAnual(rut, clave)
        asyncio.run(scraper.get_rcv_anual_consolidado("2024", headless=False))
