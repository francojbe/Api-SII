import asyncio
from playwright.async_api import async_playwright
import os

class SIIScraper:
    def __init__(self, rut, clave):
        self.rut = rut
        self.clave = clave
        self.login_url = "https://zeusr.sii.cl/AUT2000/InicioAutenticacion/IngresoRutClave.html?https://misiir.sii.cl/cgi_misii/siihome.cgi"
        self.target_url = "https://www2.sii.cl/carpetatributaria/generarcteregular"

    async def _login(self, page):
        """Método interno para manejar la autenticación."""
        print(f"[{self.rut}] Autenticando...")
        await page.goto(self.login_url, wait_until="networkidle")
        await page.fill("#rutcntr", self.rut.replace(".", "").replace("-", ""))
        await page.fill("#clave", self.clave)
        await page.click("#bt_ingresar")
        await page.wait_for_load_state("networkidle")

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
                await self._login(page)
                
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
                btn_final = page.locator("button:visible:has-text('Ver PDF Generado'), button:visible:has-text('Generar Carpeta')")
                
                try:
                    await btn_final.first.wait_for(state="visible", timeout=20000)
                except:
                    btn_final = page.get_by_role("button").filter(has_text="PDF")

                print(f"[{self.rut}] Iniciando descarga...")
                async with page.expect_download() as download_info:
                    await btn_final.first.click()
                
                download = await download_info.value
                await download.save_as(output_path)
                
                print(f"[{self.rut}] ✅ Carpeta guardada en: {output_path}")
                return True

            except Exception as e:
                print(f"[{self.rut}] ❌ Error en Carpeta: {str(e)}")
                return False
            finally:
                await browser.close()

    async def get_rcv_resumen(self):
        """Extrae el resumen de compras (RCV) del periodo actual."""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={'width': 1366, 'height': 768},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = await context.new_page()

            try:
                # 1. Login
                await self._login(page)

                # 2. Navegar directamente al RCV
                print(f"[{self.rut}] Navegando al Registro de Compras y Ventas...")
                await page.goto("https://www4.sii.cl/consdcvinternetui/#/index", wait_until="networkidle")
                
                # 3. Click en Consultar (por defecto viene el mes actual)
                print(f"[{self.rut}] Consultando periodo actual...")
                btn_consultar = page.locator("button:has-text('Consultar')")
                await btn_consultar.click()
                await page.wait_for_load_state("networkidle")
                await asyncio.sleep(2) # Esperar a que cargue la tabla dinámica

                # 4. Extraer datos de la tabla de resumen de COMPRAS
                print(f"[{self.rut}] Extrayendo datos de la tabla...")
                
                resumen = await page.evaluate("""() => {
                    const rows = Array.from(document.querySelectorAll('table tbody tr'));
                    return rows.map(row => {
                        const cols = row.querySelectorAll('td');
                        if (cols.length >= 6) {
                            return {
                                tipo_documento: cols[0].innerText.trim(),
                                total_documentos: cols[1].innerText.trim(),
                                monto_exento: cols[2].innerText.trim(),
                                monto_neto: cols[3].innerText.trim(),
                                iva_recuperable: cols[4].innerText.trim(),
                                monto_total: cols[cols.length - 1].innerText.trim()
                            };
                        }
                        return null;
                    }).filter(r => r !== null);
                }""")

                print(f"[{self.rut}] ✅ Datos RCV extraídos con éxito.")
                return resumen

            except Exception as e:
                print(f"[{self.rut}] ❌ Error en RCV: {str(e)}")
                return None
            finally:
                await browser.close()

    async def get_f29_data(self, anio: str, mes: str, es_propuesta: bool = True):
        """
        Consulta datos del F29. 
        Si es_propuesta=True, intenta ir a la propuesta actual.
        Si es_propuesta=False, consulta el histórico para el periodo dado.
        """
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={'width': 1366, 'height': 768},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = await context.new_page()
            page.set_default_timeout(60000)

            try:
                # 1. Login
                await self._login(page)

                if es_propuesta:
                    # Ruta para ver propuesta actual (cuando el periodo está abierto)
                    print(f"[{self.rut}] Accediendo a Propuesta de Declaración F29...")
                    await page.goto("https://www4.sii.cl/formulario29internetui/#/declarar", wait_until="networkidle")
                else:
                    # Ruta para consultar histórico (Seguimiento)
                    print(f"[{self.rut}] Accediendo a Histórico de F29 ({mes}/{anio})...")
                    await page.goto("https://www4.sii.cl/consul_f29_internetui/", wait_until="networkidle")
                    
                    await asyncio.sleep(8) # Esperar GWT
                    selects = page.locator("select.gwt-ListBox")
                    await selects.first.wait_for(state="visible")
                    
                    # Seleccionar F29, Año y Mes
                    await selects.nth(0).select_option(label="Formulario 29")
                    await selects.nth(1).select_option(label=anio)
                    await selects.nth(2).select_option(label=mes)
                    
                    await page.get_by_role("button", name="Buscar Datos Ingresados").click()
                    await asyncio.sleep(5)

                # 2. Extracción de códigos (Lógica común de lectura de campos)
                # Esta parte lee los valores una vez que el formulario/detalle está cargado
                print(f"[{self.rut}] Extrayendo códigos tributarios...")
                
                # Mapeo de códigos de interés (pueden expandirse)
                # Nota: En el SII los IDs suelen ser 'codXXX'
                codigos = ["538", "589", "537", "91"]
                resultados = {}

                for cod in codigos:
                    try:
                        # Intentamos obtener el valor vía input o innerText según el estado del form
                        valor = await page.evaluate(f"""(c) => {{
                            const el = document.querySelector('#cod' + c) || document.querySelector('[name="cod' + c + '"]');
                            return el ? (el.value || el.innerText) : "0";
                        }}""", cod)
                        resultados[cod] = valor.strip()
                    except:
                        resultados[cod] = "N/A"

                print(f"[{self.rut}] ✅ Consulta F29 completada.")
                return {
                    "periodo": f"{mes}-{anio}",
                    "es_propuesta": es_propuesta,
                    "datos": resultados
                }

            except Exception as e:
                print(f"[{self.rut}] ❌ Error en Consulta F29: {str(e)}")
                return None
            finally:
                await browser.close()

    async def navigate_to_f29_from_home(self):
        """Navega al F29 utilizando las alertas de la página de inicio (Mi SII)."""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={'width': 1366, 'height': 768},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = await context.new_page()

            try:
                # 1. Login
                await self._login(page)
                
                # 2. Esperar a la Home
                print(f"[{self.rut}] Esperando panel de alertas...")
                await page.wait_for_selector("text=Responsabilidades Tributarias", timeout=20000)
                
                # 3. Asegurar que 'Declaraciones' esté seleccionado
                print(f"[{self.rut}] Seleccionando pestaña 'Declaraciones'...")
                btn_declaraciones = page.locator("div:has-text('Declaraciones')").filter(has_text="Juradas").evaluate("el => el.parentElement") # Ajuste si es necesario
                # Un selector más robusto basado en texto exacto
                await page.click("text=/^\\s*Declaraciones\\s*$/")
                await asyncio.sleep(2)

                # 4. Buscar el ítem de F29 y hacer clic para expandir
                print(f"[{self.rut}] Buscando sección de F29...")
                await page.click("text=Declaración de IVA, impuestos mensuales (F29)")
                await asyncio.sleep(3)

                # 5. Buscar la fila de 'Diciembre 2025' y el estado 'Pendiente'
                print(f"[{self.rut}] Verificando periodo Diciembre 2025...")
                fila_diciembre = page.locator("tr:has-text('Diciembre 2025')")
                if await fila_diciembre.count() > 0:
                    print(f"[{self.rut}] 🚨 Periodo Diciembre 2025 detectado como PENDIENTE.")
                    
                    # El botón 'Pendiente' suele ser el link
                    btn_pendiente = fila_diciembre.locator("text=Pendiente")
                    
                    print(f"[{self.rut}] Haciendo clic en 'Pendiente' para entrar al formulario...")
                    async with page.expect_navigation():
                        await btn_pendiente.click()
                    
                    await asyncio.sleep(15) # Esperar carga profunda del formulario/selector de periodo
                    print(f"[{self.rut}] ✅ Página de selección/formulario cargada. URL: {page.url}")
                    
                    # --- NUEVO: Manejo de Modal de Actividad Económica (Enero 2026) ---
                    print(f"[{self.rut}] Verificando si aparece modal de Actividad Económica...")
                    modal_actividad = page.locator("div:has-text('ACTIVIDAD ECONÓMICA PRINCIPAL')")
                    if await modal_actividad.count() > 0 and await modal_actividad.is_visible():
                        print(f"[{self.rut}] 🚨 Modal detectado. Seleccionando actividad...")
                        try:
                            # Seleccionar la primera opción válida del dropdown
                            select_act = page.locator("select").filter(has_text="Seleccione Actividad")
                            if await select_act.count() > 0:
                                await select_act.select_option(index=1)
                                await asyncio.sleep(1)
                                await page.click("button:has-text('Confirmar')")
                                print(f"[{self.rut}] Actividad confirmada.")
                                await asyncio.sleep(5)
                        except Exception as e:
                            print(f"[{self.rut}] No se pudo completar el modal: {e}")
                            # Intentar simplemente cerrar si existe el botón
                            await page.click("button:has-text('Cerrar')")

                    # 6. Detectar si estamos en la página de "Aceptar"
                    btn_aceptar = page.locator("button:has-text('Aceptar')")
                    if await btn_aceptar.count() > 0:
                        print(f"[{self.rut}] Detectado botón 'Aceptar'. Haciendo clic para ver propuesta...")
                        await btn_aceptar.click()
                        await asyncio.sleep(15) # Esperar carga profunda del formulario/asistentes

                    # 7. Superar Asistentes de Cálculo (Botón Continuar)
                    btn_continuar = page.locator("button:has-text('Continuar')")
                    if await btn_continuar.count() > 0:
                        print(f"[{self.rut}] Superando asistentes de cálculo...")
                        await btn_continuar.click()
                        await asyncio.sleep(5)

                    # 8. Modal de Información Adicional (IMPORTANTE)
                    print(f"[{self.rut}] Verificando modal de confirmación de datos...")
                    check_aceptar = page.locator("#checkAceptar")
                    if await check_aceptar.count() > 0:
                        print(f"[{self.rut}] Marcando checkbox de confirmación...")
                        await check_aceptar.check()
                        await asyncio.sleep(1)
                        btn_confirmar_complemento = page.locator("button:has-text('Confirmar que no debo complementar')")
                        if await btn_confirmar_complemento.count() > 0:
                            await btn_confirmar_complemento.click()
                            print(f"[{self.rut}] Información adicional confirmada.")
                            await asyncio.sleep(8)

                    # 9. Cerrar Modal de Atención (si aparece)
                    btn_cerrar_atencion = page.locator("button:has-text('Cerrar')").or_(page.locator(".modal-footer button"))
                    if await btn_cerrar_atencion.count() > 0 and await btn_cerrar_atencion.is_visible():
                        print(f"[{self.rut}] Cerrando modal de atención...")
                        await btn_cerrar_atencion.first.click()
                        await asyncio.sleep(2)

                    # 10. Ir al Formulario Completo (donde están todos los códigos con valores reales)
                    print(f"[{self.rut}] Buscando acceso al Formulario Completo...")
                    link_formulario = page.locator("text=Ingresa aquí").or_(page.locator("text=Ver Formulario 29"))
                    if await link_formulario.count() > 0:
                        print(f"[{self.rut}] Accediendo a la vista de Formulario Completo...")
                        await link_formulario.first.click()
                        await asyncio.sleep(10)
                        
                        # Cerrar modal de atención que suele re-aparecer en el form completo
                        if await btn_cerrar_atencion.count() > 0:
                            await btn_cerrar_atencion.first.click()
                            await asyncio.sleep(2)

                    print(f"[{self.rut}] ✅ Formulario final cargado. URL actual: {page.url}")
                    
                    # 11. Scroll Automático
                    print(f"[{self.rut}] 📜 Desplazando por la planilla final...")
                    for i in range(5):
                        await page.mouse.wheel(0, 1000)
                        await asyncio.sleep(1)
                    await page.mouse.wheel(0, -5000) 
                    await asyncio.sleep(2)

                    # 12. Extracción de códigos
                    print(f"[{self.rut}] 🔍 Iniciando extracción de códigos clave...")
                    codigos_objetivo = {
                        "538": "Impuesto Único",
                        "589": "IVA Débito (Total)",
                        "503": "Débito Facturas",
                        "511": "IVA Crédito E-Factura",
                        "537": "Crédito Periodo",
                        "504": "Remanente Mes Ant.",
                        "77": "Remanente Mes Sig.",
                        "91": "Total a Pagar",
                        "62": "PPM Neto"
                    }
                    resultados = {}

                    for cod, desc in codigos_objetivo.items():
                        try:
                            valor = await page.evaluate(f"""(c) => {{
                                // 1. Buscar el elemento que contiene el código exacto
                                const allElements = Array.from(document.querySelectorAll('td, div, span, b'));
                                const codeElement = allElements.find(el => el.innerText.trim() === c);
                                
                                if (codeElement) {{
                                    // En el formulario completo del SII, el valor suele estar en la misma fila (tr)
                                    // o en el siguiente div/td.
                                    const row = codeElement.closest('tr');
                                    if (row) {{
                                        // Buscar cualquier input en la fila
                                        const input = row.querySelector('input');
                                        if (input && input.value) return input.value;
                                        
                                        // Si no hay input, buscar una celda con números
                                        const cells = Array.from(row.querySelectorAll('td, div'));
                                        const valueCell = cells.find(el => /[0-9]/.test(el.innerText) && el.innerText.trim() !== c);
                                        if (valueCell) return valueCell.innerText;
                                    }}
                                    
                                    // Búsqueda por proximidad si no hay fila clara
                                    const nextEl = codeElement.nextElementSibling;
                                    if (nextEl && nextEl.querySelector('input')) return nextEl.querySelector('input').value;
                                }}
                                
                                // 2. Intento por ID o Atributo (fallback)
                                const byId = document.getElementById('cod' + c) || 
                                             document.querySelector(`input[id*="cod${{c}}"]`) ||
                                             document.querySelector(`input[name*="cod${{c}}"]`);
                                if (byId) return byId.value || byId.innerText;
                                
                                return "0";
                            }}""", cod)
                            
                            val_limpio = valor.strip().replace(".", "").replace("$", "") if valor else "0"
                            # Si es solo texto no numérico, resetear a 0
                            if not any(char.isdigit() for char in val_limpio): val_limpio = "0"
                            
                            print(f"   🔹 [{cod}] {desc}: {val_limpio}")
                            resultados[cod] = val_limpio
                        except:
                            resultados[cod] = "0"

                    await page.screenshot(path="f29_full_data_extracted.png")
                    return {
                        "periodo": "Diciembre 2025",
                        "url": page.url,
                        "datos": resultados
                    }
                else:
                    print(f"[{self.rut}] ⚠️ No se encontró la fila 'Diciembre 2025' en las alertas.")
                    return None

            except Exception as e:
                print(f"[{self.rut}] ❌ Error navegando desde Home: {str(e)}")
                await page.screenshot(path="error_navigation_home.png")
                return False
            finally:
                await browser.close()
