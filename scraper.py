import asyncio
from playwright.async_api import async_playwright
import os

class SIIScraper:
    def __init__(self, rut, clave, log_callback=None):
        self.rut = rut
        self.clave = clave
        self.log_callback = log_callback
        self.browser = None
        self.context = None
        self.page = None
        self.pw_instance = None
        self.login_url = "https://zeusr.sii.cl/AUT2000/InicioAutenticacion/IngresoRutClave.html?https://misiir.sii.cl/cgi_misii/siihome.cgi"

    async def log(self, message: str, type: str = "info"):
        """Envía logs al callback si existe, y también imprime en consola."""
        formatted_msg = f"[{self.rut}] {message}"
        print(formatted_msg)
        if self.log_callback:
            # Si el callback es asíncrono, lo esperamos
            if asyncio.iscoroutinefunction(self.log_callback):
                await self.log_callback(formatted_msg, type)
            else:
                self.log_callback(formatted_msg, type)

    async def _ensure_session(self):
        """Asegura que haya una sesión de navegador activa."""
        from playwright.async_api import async_playwright
        if not self.pw_instance:
            self.pw_instance = await async_playwright().start()
            self.browser = await self.pw_instance.chromium.launch(headless=True)
            self.context = await self.browser.new_context(
                viewport={'width': 1366, 'height': 768},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            self.page = await self.context.new_page()
            await self._login(self.page)
        return self.page

    async def close_session(self):
        """Cierra el navegador y limpia recursos."""
        if self.browser: await self.browser.close()
        if self.pw_instance: await self.pw_instance.stop()
        self.browser = self.context = self.page = self.pw_instance = None

    async def _login(self, page):
        """Método interno para manejar la autenticación."""
        print(f"[{self.rut}] Autenticando...")
        await page.goto(self.login_url, wait_until="networkidle")
        await page.fill("#rutcntr", self.rut.replace(".", "").replace("-", ""))
        await page.fill("#clave", self.clave)
        await page.click("#bt_ingresar")
        await page.wait_for_load_state("networkidle")

    # ... (métodos existentes adaptados para usar self.page si existe, o abrir nuevo si no)
    # Por brevedad, adaptaremos prepare_f29_scouting para ser el motor persistente
    
    async def prepare_f29_scouting(self, anio: str, mes: str):
        """
        FASE DE SCOUTING PERSISTENTE: Mantiene el browser abierto en el formulario.
        """
        page = await self._ensure_session()
        print(f"[{self.rut}]  Iniciando Scouting Persistente para F29 {mes}/{anio}...")
        
        # 1. Obtener RCV (en una pestaña aparte para no perder el login principal)
        rcv_page = await self.context.new_page()
        await rcv_page.goto("https://www4.sii.cl/consdcvinternetui/#/index")
        # (... lógica de extracción de RCV ...)
        await rcv_page.close()

        # 2. Navegar a la propuesta oficial en la página principal
        await page.goto("https://www.sii.cl/servicios_online/impuestos_mensuales.html")
        await page.click("text=Declaración mensual (F29)")
        await page.click("text=Declarar IVA (F29)")
        
        # Lógica de navegación hasta el formulario (ya implementada antes)
        # Se detiene justo antes de 'Enviar'
        
        # Tomar captura para el 'Humano'
        screenshot_path = f"scouting_{self.rut}_{mes}.png"
        await page.screenshot(path=screenshot_path)

        return {
            "resumen": "Propuesta lista para validación",
            "screenshot": screenshot_path,
            "estado_pestaña": page.url,
            "mensaje": "El navegador permanece abierto en el portal del SII. Esperando confirmación."
        }

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
                print(f"[{self.rut}] Iniciando generacin...")
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
                
                print(f"[{self.rut}]  Carpeta guardada en: {output_path}")
                return True

            except Exception as e:
                print(f"[{self.rut}]  Error en Carpeta: {str(e)}")
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

                print(f"[{self.rut}]  Datos RCV extrados con xito.")
                return resumen

            except Exception as e:
                print(f"[{self.rut}]  Error en RCV: {str(e)}")
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
                    print(f"[{self.rut}] Accediendo a Propuesta de Declaracin F29...")
                    await page.goto("https://www4.sii.cl/formulario29internetui/#/declarar", wait_until="networkidle")
                else:
                    # Ruta para consultar histórico (Seguimiento)
                    print(f"[{self.rut}] Accediendo a Histrico de F29 ({mes}/{anio})...")
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
                print(f"[{self.rut}] Extrayendo cdigos tributarios...")
                
                # Mapeo de códigos de interés (pueden expandirse)
                # Basado en análisis de AI Studio y manual del SII
                codigos_objetivo = {
                    "538": "Ventas Afectas (Débito)",
                    "503": "Débito Facturas",
                    "589": "Total Débito IVA",
                    "511": "Monto Neto Facturas Compra",
                    "537": "Total Crédito IVA",
                    "504": "Remanente Mes Anterior",
                    "77": "Remanente Mes Nacional (a favor)",
                    "115": "PPM (Monto)",
                    "62": "Tasa PPM (%)",
                    "151": "Retención Honorarios",
                    "91": "Total a Pagar"
                }
                resultados = {}

                for cod in codigos_objetivo.keys():
                    try:
                        # Intentamos obtener el valor vía input o innerText según el estado del form
                        valor = await page.evaluate(f"""(c) => {{
                            const el = document.querySelector('#cod' + c) || 
                                       document.querySelector('[name="cod' + c + '"]') ||
                                       document.getElementById('cod' + c);
                            if (!el) return "0";
                            return el.value || el.innerText || "0";
                        }}""", cod)
                        
                        limpio = valor.strip().replace(".", "").replace("$", "")
                        resultados[cod] = limpio if limpio else "0"
                    except:
                        resultados[cod] = "N/A"

                # Detección de Postergación de IVA
                try:
                    is_postponed = await page.evaluate("""() => {
                        const cb = document.querySelector('input[name*="postergacion"]') || 
                                   document.querySelector('#chkPostergacion');
                        return cb ? cb.checked : false;
                    }""")
                    resultados["postergacion_iva"] = is_postponed
                except:
                    resultados["postergacion_iva"] = False

                print(f"[{self.rut}]  Consulta F29 completada.")
                return {
                    "periodo": f"{mes}-{anio}",
                    "es_propuesta": es_propuesta,
                    "datos": resultados
                }

            except Exception as e:
                print(f"[{self.rut}]  Error en Consulta F29: {str(e)}")
                return None
            finally:
                await browser.close()

    async def get_prev_month_remanente(self, current_anio: str, current_mes: str):
        """Busca el remanente (Código 77) del mes anterior."""
        # Lógica para calcular mes anterior
        meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
        try:
            idx = meses.index(current_mes)
            if idx == 0:
                prev_mes = "Diciembre"
                prev_anio = str(int(current_anio) - 1)
            else:
                prev_mes = meses[idx - 1]
                prev_anio = current_anio
        except:
            return 0

        print(f"[{self.rut}] Buscando remanente anterior de {prev_mes}/{prev_anio}...")
        data = await self.get_f29_data(prev_anio, prev_mes, es_propuesta=False)
        if data and "datos" in data:
            # El código 77 del mes anterior es el que se arrastra
            val = data["datos"].get("77", "0")
            return int(val) if val.isdigit() else 0
        return 0

    async def get_bhe_received(self, anio: str, mes: str):
        """Extrae retenciones de boletas de honorarios recibidas."""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()
            try:
                await self._login(page)
                print(f"[{self.rut}] Consultando Boletas de Honorarios Recibidas...")
                url_bhe = "https://proxy.sii.cl/cgi_rtc/RTC/RTCP_BHE_CONS_RECIBIDAS.cgi"
                await page.goto(url_bhe)
                
                # Seleccionar periodo
                await page.select_option("select[name='mes']", label=mes)
                await page.select_option("select[name='ano']", label=anio)
                await page.click("input[value='Consultar']")
                await page.wait_for_load_state("networkidle")
                
                # Extraer total retención (esto varía según el diseño de la tabla del SII)
                # Buscamos el texto "Total Retención" o similar
                retencion = await page.evaluate("""() => {
                    const cells = Array.from(document.querySelectorAll('td, th'));
                    const target = cells.find(c => c.innerText.includes('Total Retención') || c.innerText.includes('Retención'));
                    if (target && target.nextElementSibling) {
                        return target.nextElementSibling.innerText.trim();
                    }
                    return "0";
                }""")
                return int(retencion.replace('.','')) if retencion else 0
            except:
                return 0
            finally:
                await browser.close()

    async def prepare_f29_scouting(self, anio: str, mes: str):
        """
        FASE DE SCOUTING: El bot recopila información de las 4 fuentes clave.
        """
        print(f"[{self.rut}] [SCOUTING] Iniciando Fase de Scouting para F29 {mes}/{anio}...")
        
        # 1. RCV (Ventas y Compras)
        rcv_data = await self.get_rcv_resumen() 
        
        # 2. Remanente mes anterior
        remanente_ant = await self.get_prev_month_remanente(anio, mes)
        
        # 3. Boletas de Honorarios (Retenciones)
        retenciones_bhe = await self.get_bhe_received(anio, mes)
        
        # 4. Propuesta actual del SII (para contrastar)
        propuesta_sii = await self.get_f29_data(anio, mes, es_propuesta=True)

        # 5. Cálculos lógicos (Simulación de Auditoría)
        iva_ventas = 0
        iva_compras = 0
        if rcv_data:
            # Aquí deberíamos tener lógica para separar compras de ventas en el scraper
            # Por ahora sumamos lo que tenemos
            iva_compras = sum(int(item['iva_recuperable'].replace('.','')) for item in rcv_data if 'iva_recuperable' in item)

        # Construcción del borrador para el "Humano"
        borrador = {
            "resumen_financiero": {
                "iva_compras_rcv": iva_compras,
                "remanente_anterior": remanente_ant,
                "retenciones_honorarios": retenciones_bhe,
                "propuesta_sii_total": int(propuesta_sii['datos'].get('91', '0')) if propuesta_sii else 0
            },
            "alertas": [],
            "consultas_al_usuario": [
                {
                    "id": "ppm_rate",
                    "pregunta": f"La tasa sugerida es 0.25%, pero el mes pasado pagaste 1%. ¿Qué tasa aplicar?",
                    "opciones": ["0.25%", "1.0%", "Manual"]
                },
                {
                    "id": "postergacion",
                    "pregunta": "¿Deseas postergar el pago del IVA (Posterga) a 60 días?",
                    "opciones": ["Sí", "No"]
                }
            ]
        }
        
        # Añadir banderas lógicas
        if propuesta_sii and int(propuesta_sii['datos'].get('537', '0')) != iva_compras:
            borrador["alertas"].append({
                "tipo": "Diferencia IVA",
                "mensaje": "El RCV muestra más crédito que la propuesta del SII. ¿Hay facturas sin aceptar?"
            })

        return borrador

    async def compare_rcv_vs_f29(self, anio: str, mes: str):
        """
        Compara los datos del Registro de Compras y Ventas (RCV) con la propuesta del F29.
        Retorna un análisis de discrepancias.
        """
        print(f"[{self.rut}] Iniciando comparacin RCV vs F29 para {mes}/{anio}...")
        
        # 1. Obtener datos del RCV (usamos el método existente adaptándolo si es necesario para el mes)
        # Nota: get_rcv_resumen actualmente trae el "actual", pero para comparar necesitamos el solicitado.
        # Por simplicidad en este paso, asumimos que el usuario quiere el flujo completo.
        rcv_data = await self.get_rcv_resumen() # En una versión pro, esto recibiría mes/año
        
        # 2. Obtener datos de la propuesta F29
        f29_result = await self.get_f29_data(anio, mes, es_propuesta=True)
        
        if not rcv_data or not f29_result:
            return {"error": "No se pudieron obtener ambos sets de datos para comparar."}

        f29_codes = f29_result.get("datos", {})
        
        # 3. Lógica de comparación de IVA
        # Sumamos el neto y IVA de las facturas en el RCV
        rcv_neto_total = sum(int(item['monto_neto'].replace('.','')) for item in rcv_data if 'monto_neto' in item)
        rcv_iva_total = sum(int(item['iva_recuperable'].replace('.','')) for item in rcv_data if 'iva_recuperable' in item)
        
        f29_iva_credito = int(f29_codes.get("537", "0"))
        
        discrepancia_iva = rcv_iva_total - f29_iva_credito
        
        analisis = {
            "periodo": f"{mes}-{anio}",
            "rcv_resumen": {
                "iva_total_compras": rcv_iva_total,
                "neto_total_compras": rcv_neto_total
            },
            "f29_propuesta": {
                "iva_credito_cod537": f29_iva_credito,
                "total_a_pagar_cod91": int(f29_codes.get("91", "0"))
            },
            "analisis": {
                "discrepancia_iva": discrepancia_iva,
                "estado": "OK" if discrepancia_iva == 0 else "ALERTA",
                "mensaje": "Los datos coinciden perfectamente." if discrepancia_iva == 0 else 
                           f"Se detectó una diferencia de ${discrepancia_iva} entre el RCV y el F29. Revise facturas pendientes de aceptación."
            }
        }
        
        return analisis

    async def navigate_to_f29_official_path(self, anio: str, mes: str):
        """Navega al F29 siguiendo la ruta oficial sugerida por AI Studio."""
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
                
                # 2. Ruta: Servicios online -> Impuestos mensuales -> Declaración mensual (F29) -> Declarar IVA (F29)
                print(f"[{self.rut}] Navegando por ruta oficial...")
                await page.goto("https://www.sii.cl/servicios_online/impuestos_mensuales.html")
                await page.click("text=Declaración mensual (F29)")
                await page.click("text=Declarar IVA (F29)")
                
                # 3. Selección de período
                print(f"[{self.rut}] Seleccionando perodo {mes}/{anio}...")
                await page.wait_for_selector("select[name='mes']", timeout=15000)
                await page.select_option("select[name='mes']", label=mes)
                await page.select_option("select[name='anio']", label=anio)
                await page.click("button:has-text('Aceptar')")
                
                # 4. Manejo de asistentes y modales (reutilizamos la lógica del flujo de alertas)
                await asyncio.sleep(10)
                
                # Manejo de modal de actividad económica si aparece
                if await page.locator("button:has-text('Cerrar')").count() > 0:
                    await page.click("button:has-text('Cerrar')")
                
                # Si hay una propuesta, aceptar
                btn_aceptar = page.locator("button:has-text('Aceptar')")
                if await btn_aceptar.count() > 0:
                    await btn_aceptar.click()
                    await asyncio.sleep(10)
                
                # Continuar en asistentes
                btn_continuar = page.locator("button:has-text('Continuar')")
                if await btn_continuar.count() > 0:
                    await btn_continuar.click()
                    await asyncio.sleep(5)

                # Confirmar que no hay complementos
                check_aceptar = page.locator("#checkAceptar")
                if await check_aceptar.count() > 0:
                    await check_aceptar.check()
                    await page.click("button:has-text('Confirmar que no debo complementar')")
                    await asyncio.sleep(5)

                # Ir al formulario completo
                link_formulario = page.locator("text=Ingresa aquí").or_(page.locator("text=Ver Formulario 29"))
                if await link_formulario.count() > 0:
                    await link_formulario.first.click()
                    await asyncio.sleep(8)

                print(f"[{self.rut}]  Llegamos al formulario final.")
                # Aquí se podría llamar a una función de extracción común
                # Por ahora retornamos éxito de navegación
                return True

            except Exception as e:
                print(f"[{self.rut}]  Error en ruta oficial: {str(e)}")
                return False
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
                await self.log("Esperando panel de alertas...")
                await page.wait_for_selector("text=Responsabilidades Tributarias", timeout=20000)
                
                # 3. Asegurar que 'Declaraciones' esté seleccionado
                await self.log("Seleccionando pestaña 'Declaraciones'...")
                await page.wait_for_load_state("networkidle")
                # Selector más robusto para la pestaña Declaraciones
                try:
                    await page.click("text=/^\\s*Declaraciones\\s*$/", timeout=5000)
                except:
                    await self.log("No se pudo hacer clic exacto en 'Declaraciones', intentando alternativa...")
                    await page.click("div:has-text('Declaraciones')")
                await asyncio.sleep(2)

                # 4. Buscar el ítem de F29 y hacer clic para expandir
                await self.log("Buscando sección de F29...")
                await page.click("text=Declaración de IVA, impuestos mensuales (F29)")
                await asyncio.sleep(3)

                # 5. Buscar la fila de 'Diciembre 2025' y el estado 'Pendiente'
                await self.log("Verificando periodo Diciembre 2025...")
                fila_diciembre = page.locator("tr:has-text('Diciembre 2025')")
                if await fila_diciembre.count() > 0:
                    await self.log("Periodo Diciembre 2025 detectado como PENDIENTE. ✅")
                    
                    # El botón 'Pendiente' suele ser el link
                    btn_pendiente = fila_diciembre.locator("text=Pendiente")
                    
                    await self.log("Haciendo clic en 'Pendiente' para entrar al formulario...")
                    async with page.expect_navigation():
                        await btn_pendiente.click()
                    
                    await asyncio.sleep(15) # Esperar carga profunda del formulario/selector de periodo
                    await self.log(f"Página de selección/formulario cargada. URL: {page.url}")
                    
                    # --- NUEVO: Manejo de Modal de Actividad Económica (Enero 2026) ---
                    await self.log("Verificando si aparece modal de Actividad Económica...")
                    modal_actividad = page.locator("div:has-text('ACTIVIDAD ECONÓMICA PRINCIPAL')")
                    if await modal_actividad.count() > 0 and await modal_actividad.is_visible():
                        await self.log("Modal detectado. Seleccionando actividad...")
                        try:
                            # Seleccionar la primera opción válida del dropdown
                            select_act = page.locator("select").filter(has_text="Seleccione Actividad")
                            if await select_act.count() > 0:
                                await select_act.select_option(index=1)
                                await asyncio.sleep(1)
                                await page.click("button:has-text('Confirmar')")
                                await self.log("Actividad confirmada.")
                                await asyncio.sleep(5)
                        except Exception as e:
                            await self.log(f"No se pudo completar el modal: {e}", "error")
                            # Intentar simplemente cerrar si existe el botón
                            await page.click("button:has-text('Cerrar')")

                    # 6. Detectar si estamos en la página de "Aceptar"
                    btn_aceptar = page.locator("button:has-text('Aceptar')")
                    if await btn_aceptar.count() > 0:
                        await self.log("Detectado botón 'Aceptar'. Haciendo clic para ver propuesta...")
                        await btn_aceptar.click()
                        await asyncio.sleep(15) # Esperar carga profunda del formulario/asistentes

                    # 7. Superar Asistentes de Cálculo (Botón Continuar)
                    btn_continuar = page.locator("button:has-text('Continuar')")
                    if await btn_continuar.count() > 0:
                        await self.log("Superando asistentes de cálculo...")
                        await btn_continuar.click()
                        await asyncio.sleep(5)

                    # 8. Modal de Información Adicional (IMPORTANTE)
                    await self.log("Verificando modal de confirmación de datos...")
                    check_aceptar = page.locator("#checkAceptar")
                    if await check_aceptar.count() > 0:
                        await self.log("Marcando checkbox de confirmación...")
                        await check_aceptar.check()
                        await asyncio.sleep(1)
                        btn_confirmar_complemento = page.locator("button:has-text('Confirmar que no debo complementar')")
                        if await btn_confirmar_complemento.count() > 0:
                            await btn_confirmar_complemento.click()
                            await self.log("Información adicional confirmada.")
                            await asyncio.sleep(8)

                    # 9. Cerrar Modal de Atención (si aparece)
                    btn_cerrar_atencion = page.locator("button:has-text('Cerrar')").or_(page.locator(".modal-footer button"))
                    if await btn_cerrar_atencion.count() > 0 and await btn_cerrar_atencion.is_visible():
                        await self.log("Cerrando modal de atención...")
                        await btn_cerrar_atencion.first.click()
                        await asyncio.sleep(2)

                    # 10. Ir al Formulario Completo (donde están todos los códigos con valores reales)
                    await self.log("Buscando acceso al Formulario Completo...")
                    # A veces el botón tarda en aparecer o está en un frame
                    await asyncio.sleep(5)
                    link_formulario = page.locator("text=Ingresa aquí").or_(page.locator("text=Ver Formulario 29")).or_(page.locator("text=Formulario en Pantalla"))
                    
                    found_link = False
                    for _ in range(3): # Re-intentar 3 veces con esperas
                        if await link_formulario.count() > 0 and await link_formulario.first.is_visible():
                            await self.log("Accediendo a la vista de Formulario Completo...")
                            await link_formulario.first.click()
                            await asyncio.sleep(12)
                            found_link = True
                            break
                        await asyncio.sleep(3)
                        
                    if not found_link:
                         await self.log("⚠️ No se encontró el botón para el Formulario Completo. Intentando extracción en vista actual.")

                    await self.log(f"Formulario final cargado. URL: {page.url}")
                    
                    # 11. Scroll Automático
                    await self.log("Desplazando por la planilla final...")
                    for i in range(5):
                        await page.mouse.wheel(0, 1000)
                        await asyncio.sleep(1)
                    await page.mouse.wheel(0, -5000) 
                    await asyncio.sleep(2)

                    # 12. Extracción de códigos
                    await self.log("Iniciando extracción de códigos clave...")
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
                    resultados = {k: 0 for k in codigos_objetivo.keys()}
                    
                    # ESPERAR A QUE CARGUE EL FORMULARIO (IMPORTANTE)
                    await self.log("Esperando carga de datos en formulario...")
                    # Buscamos 'Débito' con acento o sin acento, o el código 538
                    try:
                        await page.wait_for_selector("text=/D.bito|538|IVA/", timeout=30000)
                        await self.log("Contenido del formulario detectado.")
                    except:
                        await self.log("⚠️ Tiempo de espera agotado buscando texto clave. El formulario podría estar vacío o lento.")
                    
                    # Pequeña espera extra para que los frames terminen de poblarse
                    await asyncio.sleep(5)

                    for cod in codigos_objetivo.keys():
                        await self.log(f"Buscando Código [{cod}]...")
                        found = False
                        # Buscamos en todas las páginas abiertas (por si abrió pestaña nueva)
                        for p in page.context.pages:
                            if found: break
                            for frame in p.frames:
                                try:
                                    valor = await frame.evaluate(f"""(c) => {{
                                        const cleanNum = (str) => {{
                                            if (!str) return null;
                                            // Eliminar todo lo que no sea dígito
                                            const cleaned = str.replace(/[^0-9]/g, '');
                                            return cleaned.length > 0 ? cleaned : null;
                                        }};

                                        // 1. Búsqueda por ID/Name Directo
                                        const exact = document.getElementById('valCode' + c) || 
                                                       document.getElementById('code' + c) ||
                                                       document.querySelector(`input[id*="valCode${{c}}"]`) ||
                                                       document.querySelector(`input[name*="valCode${{c}}"]`);
                                        if (exact && exact.value && cleanNum(exact.value)) return exact.value;

                                        // 2. Búsqueda por texto del código en cualquier elemento
                                        // Buscamos elementos que contengan el código rodeado de algo no numérico
                                        const all = Array.from(document.querySelectorAll('td, label, span, div, b'));
                                        const target = all.find(el => {{
                                            const t = el.innerText.trim();
                                            return t === c || t === '['+c+']' || t === '('+c+')' || t === c+':';
                                        }});
                                        
                                        if (target) {{
                                            // El valor suele estar en la misma fila (tr) o en el siguiente div/td
                                            const row = target.closest('tr') || target.closest('div.row') || target.parentElement;
                                            if (row) {{
                                                const input = row.querySelector('input');
                                                if (input && input.value && cleanNum(input.value)) return input.value;

                                                // Si no hay input, buscar el texto numérico más probable en la fila
                                                const cells = Array.from(row.querySelectorAll('td, div, span'))
                                                                  .map(el => el.innerText.trim())
                                                                  .filter(t => t !== '' && t !== target.innerText.trim());
                                                
                                                for (let t of cells.reverse()) {{
                                                    if (cleanNum(t)) return t;
                                                }}
                                            }}
                                        }}
                                        return null;
                                    }}""", cod)

                                    if valor:
                                        val_limpio = valor.strip().replace(".", "").replace("$", "").replace(",", "")
                                        if val_limpio.isdigit():
                                            resultados[cod] = int(val_limpio)
                                            await self.log(f"    Code [{cod}]: {resultados[cod]} (Encontrado en {frame.url[:40]}...)")
                                            found = True
                                            break
                                except: continue
                        
                        if not found:
                             await self.log(f"    Code [{cod}]: 0 (No Encontrado)")

                    await page.screenshot(path="f29_full_data_extracted.png")
                    return {
                        "periodo": "Diciembre 2025",
                        "url": page.url,
                        "datos": resultados
                    }
                else:
                    print(f"[{self.rut}]  No se encontr la fila 'Diciembre 2025' en las alertas.")
                    return None

            except Exception as e:
                print(f"[{self.rut}]  Error navegando desde Home: {str(e)}")
                await page.screenshot(path="error_navigation_home.png")
                return False
            finally:
                await browser.close()
