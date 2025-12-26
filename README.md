# SII Carpeta Tributaria Scraper

Este proyecto permite automatizar la descarga de la **Carpeta Tributaria Electrónica** del SII (Chile).

## Requisitos
- Python 3.8+
- Playwright

## Instalación

1. Instalar dependencias:
   ```bash
   pip install -r requirements.txt
   ```

2. Instalar el navegador necesario:
   ```bash
   playwright install chromium
   ```

## Ejecución

Corre el servidor:
```bash
python main.py
```

La API estará disponible en `http://localhost:8000`.

## Uso (POST /descargar-carpeta)

Envía un JSON con tus credenciales:

```json
{
  "rut": "12345678-9",
  "clave": "tu_clave_sii"
}
```

La respuesta será directamente el archivo PDF listo para guardar.

---
**Nota de Seguridad:** Este script maneja credenciales sensibles. Asegúrate de correrlo en un entorno seguro y nunca exponer el puerto 8000 a internet sin seguridad adicional (HTTPS, API Keys, etc.).
