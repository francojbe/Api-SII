# Diseño de Automatización: Validación y Declaración F29

Este documento describe la lógica técnica y de negocio para automatizar la revisión del **Formulario 29 (F29)**, integrando datos del SII con datos externos (Liquidaciones de Sueldo).

## 1. Flujo de Datos

Para validar correctamente una propuesta de F29, necesitamos dos fuentes de verdad:

1.  **Fuente Externa (Cliente/ERP):**
    *   **Impuesto Único (Código 48):** Suma total del impuesto retenido en las liquidaciones de sueldo del mes.
    *   **Retención Honorarios (Código 151):** Suma de retenciones de boletas (opcional, el SII suele tener esto bien).
    *   **Ventas Netas Internas:** Para validar que no falten facturas en el SII.

2.  **Fuente SII (Scraper):**
    *   **Propuesta F29:** Valores que el SII calcula automáticamente.

## 2. Pseudocódigo de la Lógica

A continuación, un ejemplo de cómo sería el script `validar_f29.py`.

```python
class ValidadorF29:
    def __init__(self, cliente_rut, password, mes, anio):
        self.auth = {rut: cliente_rut, pass: password}
        self.periodo = {mes: mes, anio: anio}
    
    def ejecutar_validacion(self, datos_cliente):
        """
        datos_cliente = {
            "impuesto_unico_nomima": 150000,  # Dato real de las liquidaciones
            "ventas_esperadas_iva": 4500000   # IVA débito calculado por contabilidad
        }
        """
        
        # 1. Conectar al SII y navegar a la propuesta
        browser = iniciar_navegador()
        login_sii(browser, self.auth)
        propuesta = obtener_propuesta_f29(browser, self.periodo)
        
        # 2. Extraer códigos clave del SII (Valores ejemplo)
        # Código 538: Impuesto Único de Segunda Categoría
        sii_impuesto_unico = propuesta.get_codigo(538) 
        
        # Código 538 (Débito Fiscal - Ventas)
        sii_iva_ventas = propuesta.get_codigo(589) # Suma de débitos
        
        # 3. Lógica de Comparación (El "Cerebro" del bot)
        reporte = []
        
        # --- Validación 1: Impuesto Único (Sueldos) ---
        diferencia_impuesto = abs(sii_impuesto_unico - datos_cliente["impuesto_unico_nomima"])
        
        if diferencia_impuesto > 0:
            reporte.append({
                "estado": "ALERTA",
                "item": "Impuesto Único",
                "mensaje": f"Discrepancia detectada. SII tiene ${sii_impuesto_unico}, Nominas dicen ${datos_cliente['impuesto_unico_nomima']}",
                "accion_sugerida": "Modificar manualmente el código 538 en el formulario."
            })
        else:
             reporte.append({"estado": "OK", "item": "Impuesto Único", "mensaje": "Coincide perfectamente."})
             
        # --- Validación 2: IVA Debito (Ventas) ---
        # Si el SII tiene MENOS ventas que la contabilidad, es grave (facturas no llegaron al SII).
        if sii_iva_ventas < datos_cliente["ventas_esperadas_iva"]:
             reporte.append({
                "estado": "CRITICO",
                "item": "Ventas/Débito",
                "mensaje": "El SII tiene menos ventas registradas que su contabilidad. Revise facturas rechazadas.",
            })
            
        return reporte

    def modificar_y_enviar(self, correcciones):
        """
        Solo si el usuario confirma, el bot entra a 'Editar Propuesta',
        escribe los valores correctos en los inputs y presiona 'Enviar'.
        """
        pass
```

## 3. Casos de Uso del Robot

### Caso A: Todo Coincide (Happy Path)
1. Usuario sube un Excel simple con: `Total Impuesto Único: $50.000`.
2. Bot entra al SII.
3. Bot lee Código 538 del SII -> Dice `$50.000`.
4. Bot responde: "La propuesta del SII calza con tus sueldos. ¿Deseas declarar?".
5. Usuario confirma -> Bot hace clic en "Enviar Declaración".

### Caso B: Ajuste de Sueldos (Común)
1. Usuario sube Excel: `Total Impuesto Único: $85.000` (Hubo un bono extra).
2. Bot entra al SII.
3. Bot lee Código 538 del SII -> Dice `$40.000` (El SII no sabía del bono).
4. Bot detecta diferencia.
5. Bot entra al modo edición del F29.
6. **Bot escribe `85000` en la casilla Código 538.**
7. Bot recalcula el total a pagar y pide confirmación final al usuario.

## 4. Requisitos Técnicos
*   **Mapeo de Códigos F29:** Necesitamos un diccionario que mapee conceptos a códigos del formulario (ej: `Impuesto Único` = `Casilla 48` / `Código 538`).

## 5. Tipologías de Contribuyentes a Automatizar

Para que el bot sea robusto, debemos distinguir "quién" está declarando, ya que el F29 cambia drásticamente.

### A. Persona Natural con Boletas (Segunda Categoría Pura)
*   **Quién es:** Médico, Abogado, Programador Freelance que emite boletas.
*   **Complejidad:** Baja.
*   **Puntos Críticos en F29:**
    *   **PPM (Pago Provisional Mensual):** Deben declarar un % voluntario u obligatorio sobre sus ingresos brutos.
    *   **Retenciones:** Verificar si sus clientes le retuvieron el % o si ellos deben pagarlo (Autoretención).

### B. Empresa Pyme / Servicios (Primera Categoría - Sin Sueldos)
*   **Quién es:** Agencia de publicidad, consultora pequeña, tienda online unipersonal.
*   **Complejidad:** Media.
*   **Puntos Críticos en F29:**
    *   **IVA (Débito vs Crédito):** El cruce clásico de facturas.
    *   **IVA Postergado:** Muchos optan por pagar el IVA a los 2 meses. El bot debe saber marcar esa opción.

### C. Empleadores (El caso "Sueldos Altos")
*   **Quién es:** Cualquier empresa (Pyme o Grande) que tenga trabajadores contratados.
*   **Complejidad:** Alta.
*   **Puntos Críticos en F29:**
    *   **Impuesto Único (Línea 48 / Cod 538):** Aquí entra lo que mencionaste. Si tiene gerentes o sueldos sobre ~13.5 UTM ($880.000 aprox), la empresa debe RETENER un impuesto y pagarlo en el F29.
    *   **Subsidios:** A veces hay créditos por contratación que se descuentan aquí.

### D. Casos Especiales (Complejidad Extrema)
*   **Exportadores:** Recuperan IVA (IVA Exportador).
*   **Activos Fijos:** Compras de maquinaria que tienen tratamiento especial de IVA.
*   **Cambio de Sujeto:** Cuando el comprador retiene el IVA (ej: venta de chatarra, harina, carne).

## 6. Estrategia de Identificación del Contribuyente

Toda la razón: El bot **DEBE** saber con quién está tratando antes de pedir datos o validar. No podemos pedirle "Liquidaciones de Sueldo" a un dentista que trabaja solo.

### Método A: Configuración Explícita (Perfilamiento)
Al dar de alta al cliente en el sistema, definimos su "Perfil Tributario":
*   `[x] Primera Categoría (Empresa)`
*   `[ ] Segunda Categoría (Persona)`
*   `[x] Empleador (Tiene sueldos)` -> **Activa validación de Impuesto Único.**

### Método B: Auto-Descubrimiento (Scraping de "Mi SII")
El bot puede deducir el perfil consultando datos básicos en el SII al iniciar:
1.  **Consulta de Giros:** Si tiene giros comerciales -> Es Empresa (Requiere IVA).
2.  **Historia de F29:** Si en los últimos 6 meses ha declarado Código 538 -> Es Empleador (Requiere validación de sueldos).
3.  **Cartola Tributaria:** Verificamos si tiene inicio de actividades en 1ra o 2da categoría.

**Recomendación:** Usar un híbrido. Configuración inicial + Validación histórica automática.

## 7. Flujo de Trabajo (User Experience)

Para que esto sea útil para un contador, el bot no debe ser una "caja negra". El flujo ideal sería:

1.  **Carga de Insumos:** El usuario sube un archivo (Excel/JSON) o el sistema se conecta a la API de Remuneraciones.
    *   *Ejemplo de carga:* `{ "rut": "76...-0", "periodo": "2025-12", "impuesto_unico": 542000 }`
2.  **Pre-Vuelo (Drafting):** El bot entra al SII, navega a la propuesta y extrae todos los códigos.
3.  **Tablero de Diferencias:** El bot presenta una tabla comparativa:
    | Concepto | Valor SII | Valor Real (User) | Diferencia | Estado |
    | :--- | :--- | :--- | :--- | :--- |
    | IVA Ventas | $1.200.000 | $1.200.000 | $0 | ✅ |
    | Impuesto Único | $0 (Propuesta) | $542.000 | -$542.000 | ⚠️ CORREGIR |
4.  **Ejecución de Corrección:** El usuario presiona "Aplicar Correcciones". El bot vuelve al SII, edita el formulario, escribe `542000` en el código 538 y guarda el borrador.
5.  **Declaración Final:** El usuario revisa el borrador final en el sitio del SII (o el bot le envía un PDF) y da el OK para "Pagar/Enviar".

## 8. Alertas y Bitácora de Auditoría

Cada vez que el bot detecta que tiene que cambiar un valor del SII por uno "Real", debe generar una entrada en un log de seguridad:

*   **Log ID #452:** *"Se modificó Código 538 de $0 a $542.000 según archivo 'remuneraciones_dic.xlsx'. Razón: SII no detectó retenciones de sueldos altos automáticamente."*

Esto es vital porque ante una auditoría del SII, el contador debe saber **por qué** se ignoró la propuesta automática.
