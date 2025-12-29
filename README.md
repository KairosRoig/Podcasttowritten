# Prollecto 🎙️

**Prollecto** es un conjunto de utilidades y demos para procesamiento de audio y voz, incluyendo scripts para síntesis y reproducción, así como una demo en Streamlit.

## 🧩 Características
- Scripts para generación y reproducción de **audio/voz** (p. ej. `voz.py`, `voz2.py`) 🎧
- Demo interactiva con **Streamlit** (archivo de configuración en `.streamlit/`) 🖥️
- Contiene utilidades para integración con APIs y experimentos multimedia 🔌

## 🚀 Requisitos
- Python 3.8+ (recomendado 3.10+)
- Dependencias listadas en `requirements.txt`
- Opcional: **Git** para control de versiones y despliegue

## ⚙️ Instalación
1. Crear y activar un entorno virtual (recomendado):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1  # PowerShell
```

2. Instalar dependencias:

```bash
pip install -r requirements.txt
```

## 🧪 Ejecución / Uso
- Ejecutar la demo Streamlit (si está configurada):

```bash
streamlit run main.py
```

- Ejecutar scripts de voz directamente (ejemplos):

```bash
python voz2.py
python voz.py
```

> Consulta los comentarios dentro de cada archivo para parámetros específicos o variables de entorno que deban suministrarse (por ejemplo, claves de API en `.env` o `.streamlit/secrets.toml`).

## 📝 Organización del repositorio
- `voz.py`, `voz2.py` — scripts de audio/voz
- `main.py` — entrada principal para demo Streamlit (si aplica)
- `.streamlit/` — configuración y secretos de Streamlit
- `requirements.txt` — dependencias del proyecto

## 🤝 Contribuir
1. Haz un fork del repositorio
2. Crea una rama feature: `git checkout -b feature/nombre`
3. Envía un pull request explicando los cambios

## 📬 Contacto
Para dudas o colaboración: `j.roigmartin@gmail.com`

