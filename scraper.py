import asyncio
from playwright.async_api import async_playwright
import os

class SIIScraper:
    def __init__(self, rut, clave):
        self.rut = rut
        self.clave = clave
        self.login_url = "https://zeusr.sii.cl/AUT2000/InicioAutenticacion/IngresoRutClave.html?https://misiir.sii.cl/cgi_misii/siihome.cgi"
        self.target_url = "https://www2.sii.cl/carpetatributaria/generarcteregular"

    async def get_carpeta_tributaria(self, output_path, datos_envio=None):
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={'width': 1366, 'height': 768},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = await context.new_page()

            try:
                # 1. Login
                print(f"[{self.rut}] Autenticando...")
                await page.goto(self.login_url, wait_until="networkidle")
                await page.fill("#rutcntr", self.rut.replace(".", "").replace("-", ""))
                await page.fill("#clave", self.clave)
                await page.click("#bt_ingresar")
                await page.wait_for_load_state("networkidle")
                
                # 2. Navegar a la página de generación
                print(f"[{self.rut}] Navegando a Carpeta...")
                await page.goto(self.target_url, wait_until="networkidle")

                # 3. Primer Continuar
                print(f"[{self.rut}] Iniciando generación...")
                await page.get_by_role("button", name="Continuar").first.click()
                await page.wait_for_load_state("networkidle")

                # 4. RELLENAR FORMULARIO
                data = datos_envio or {
                    "dest_rut": self.rut,
                    "dest_correo": "test@test.cl"
                }

                print(f"[{self.rut}] Ingresando RUT...")
                rut_input = page.locator("input[placeholder*='12.345.678-9']")
                await rut_input.evaluate(f"el => {{ el.value = '{data['dest_rut']}'; el.dispatchEvent(new Event('input', {{ bubbles: true }})); el.dispatchEvent(new Event('change', {{ bubbles: true }})); }}")
                await rut_input.focus()
                await page.keyboard.press("Enter")
                
                print(f"[{self.rut}] Esperando autocompletado...")
                nombre_input = page.locator("input[placeholder*='Ingresa Nombre']").first
                await page.wait_for_function('el => el.value !== ""', arg=await nombre_input.element_handle(), timeout=10000)

                print(f"[{self.rut}] Completando datos...")
                await page.fill("input[placeholder*='Ingrese correo']", data['dest_correo'])
                await page.fill("input[placeholder*='Repite el correo']", data['dest_correo'])
                await page.select_option("select", index=1)
                
                # Checkbox de Autorización
                await page.evaluate("() => { const cbs = document.querySelectorAll('input[type=\"checkbox\"]'); cbs[cbs.length-1].click(); }")
                await asyncio.sleep(2)

                print(f"[{self.rut}] Enviando formulario...")
                btn_cont = page.locator("button:has-text('Continuar')")
                await btn_cont.evaluate("el => { el.disabled = false; el.click(); }")
                
                # --- MANEJO DEL MODAL ---
                print(f"[{self.rut}] Confirmando en ventana emergente...")
                try:
                    btn_aceptar = page.locator("button:visible:has-text('Aceptar')")
                    await btn_aceptar.first.wait_for(state="visible", timeout=10000)
                    await btn_aceptar.first.click()
                    await page.wait_for_load_state("networkidle")
                except:
                    # Intento alternativo via JS
                    await page.evaluate("() => { const buttons = Array.from(document.querySelectorAll('button')); const btn = buttons.find(b => b.innerText.includes('Aceptar') && b.offsetParent !== null); if(btn) btn.click(); }")
                    await asyncio.sleep(2)

                # 5. Descarga Final (Botón Verde "Ver PDF Generado")
                print(f"[{self.rut}] Descargando resultado final...")
                # El botón final puede ser 'Generar Carpeta' o 'Ver PDF Generado' según el paso
                btn_final = page.locator("button:visible:has-text('Ver PDF Generado'), button:visible:has-text('Generar Carpeta')")
                
                try:
                    await btn_final.first.wait_for(state="visible", timeout=20000)
                except:
                    # Si no aparece, quizás ya estamos en la pantalla final pero el texto es ligeramente distinto
                    btn_final = page.get_by_role("button").filter(has_text="PDF")

                print(f"[{self.rut}] Iniciando descarga...")
                async with page.expect_download() as download_info:
                    await btn_final.first.click()
                
                download = await download_info.value
                await download.save_as(output_path)
                
                print(f"[{self.rut}] ✅ ¡MISIÓN CUMPLIDA! Archivo guardado en: {output_path}")
                return True

            except Exception as e:
                print(f"[{self.rut}] ❌ Error en el proceso: {str(e)}")
                await page.screenshot(path="error_final_absoluto.png")
                return False
            finally:
                await browser.close()
