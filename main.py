import streamlit as st
import azure.cognitiveservices.speech as speechsdk
import os
import tempfile
import time
import scipy.signal
import soundfile as sf
import requests
import json

# ==============================
# CONFIGURACIÓN AZURE SPEECH
# ==============================
SPEECH_KEY = os.getenv("SPEECH_KEY") or st.secrets.get("SPEECH_KEY")
REGION = os.getenv("SPEECH_REGION") or st.secrets.get("SPEECH_REGION")

# Configuración Azure Language Service
LANGUAGE_KEY = os.getenv("LANGUAGE_KEY") or st.secrets.get("LANGUAGE_KEY")
LANGUAGE_ENDPOINT = os.getenv("LANGUAGE_ENDPOINT") or st.secrets.get("LANGUAGE_ENDPOINT")

if not SPEECH_KEY or not REGION:
    st.error("❌ No se encontraron las variables de entorno SPEECH_KEY o SPEECH_REGION.")
    st.stop()

if not LANGUAGE_KEY or not LANGUAGE_ENDPOINT:
    st.error("❌ No se encontraron las variables de entorno LANGUAGE_KEY o LANGUAGE_ENDPOINT.")
    st.stop()

# ==============================
# FUNCIÓN DE RESUMEN CON AZURE LANGUAGE
# ==============================
@st.cache_data(ttl=600)
def generar_resumen(texto, tipo="extractive"):
    """
    Genera un resumen del texto usando Azure Language Service
    tipo: 'extractive' (extrae oraciones clave) o 'abstractive' (genera resumen)
    """
    
    # URL para trabajos asíncronos
    url = f"{LANGUAGE_ENDPOINT.rstrip('/')}/language/analyze-text/jobs?api-version=2023-04-01"
    
    headers = {
        "Ocp-Apim-Subscription-Key": LANGUAGE_KEY,
        "Content-Type": "application/json"
    }
    
    if tipo == "extractive":
        # Resumen extractivo - extrae oraciones más relevantes
        body = {
            "displayName": "Extractive Summarization Task",
            "analysisInput": {
                "documents": [
                    {
                        "id": "1",
                        "language": "es",
                        "text": texto
                    }
                ]
            },
            "tasks": [
                {
                    "kind": "ExtractiveSummarization",
                    "taskName": "ExtractiveSummarization_1",
                    "parameters": {
                        "sentenceCount": 5,
                        "sortBy": "Offset"
                    }
                }
            ]
        }   
    try:
        # Enviar solicitud inicial
        response = requests.post(url, headers=headers, json=body)
        response.raise_for_status()
        
        # Obtener URL de estado del trabajo
        operation_location = response.headers.get('Operation-Location')
        if not operation_location:
            st.error("No se recibió la URL de operación")
            return None
        
        # Esperar a que el trabajo se complete (polling)
        max_attempts = 60  # 60 intentos = 1 minuto máximo
        attempt = 0
        
        while attempt < max_attempts:
            time.sleep(2)  # Esperar 2 segundos entre consultas
            
            status_response = requests.get(operation_location, headers=headers)
            status_response.raise_for_status()
            status_data = status_response.json()
            
            status = status_data.get('status')
            
            if status == 'succeeded':
                # Extraer el resumen
                tasks = status_data.get('tasks', {}).get('items', [])
                if not tasks:
                    st.error("No se encontraron tareas en la respuesta")
                    return None
                
                task_result = tasks[0].get('results', {})
                documents = task_result.get('documents', [])
                
                if not documents:
                    st.error("No se encontraron documentos en los resultados")
                    return None
                
                doc = documents[0]
                
                if tipo == "extractive":
                    # Extraer oraciones del resumen extractivo
                    sentences = doc.get('sentences', [])
                    resumen = " ".join([s['text'] for s in sentences])
                else:
                    # Extraer resumen abstractivo
                    summaries = doc.get('summaries', [])
                    resumen = " ".join([s['text'] for s in summaries])
                
                return resumen
            
            elif status == 'failed':
                errors = status_data.get('errors', [])
                error_msg = errors[0] if errors else "Error desconocido"
                st.error(f"El trabajo falló: {error_msg}")
                return None
            
            # Si está en progreso, continuar esperando
            attempt += 1
        
        st.error("Tiempo de espera agotado. El proceso tardó demasiado.")
        return None
    
    except requests.exceptions.RequestException as e:
        st.error(f"Error al generar resumen: {str(e)}")
        if hasattr(e, 'response') and hasattr(e.response, 'text'):
            st.error(f"Detalles: {e.response.text}")
        return None

# ==============================
# FUNCIÓN DE TRANSCRIPCIÓN CON DIARIZACIÓN
# ==============================
@st.cache_data(ttl=600)
def transcribir_audio_con_diarizacion(file_path, _progress_bar, _status_text):
    """Transcribe audios con diarización (identificación de hablantes) usando Azure Speech SDK"""
    
    speech_config = speechsdk.SpeechConfig(subscription=SPEECH_KEY, region=REGION)
    
    # Configurar idioma (ajusta según necesites)
    speech_config.speech_recognition_language = "es-ES"
    
    # ACTIVAR DIARIZACIÓN - Método correcto
    speech_config.set_property(
        speechsdk.PropertyId.SpeechServiceConnection_LanguageIdMode, "Continuous"
    )
    speech_config.request_word_level_timestamps()
    
    # Habilitar diarización del hablante
    speech_config.set_property_by_name("DiarizationEnabled", "true")
    speech_config.set_property_by_name("MaxSpeakerCount", "10")  # Máximo de hablantes a detectar
    
    # Configurar audio de entrada
    audio_config = speechsdk.audio.AudioConfig(filename=file_path)
    
    # Usar ConversationTranscriber para diarización
    conversation_transcriber = speechsdk.transcription.ConversationTranscriber(
        speech_config=speech_config,
        audio_config=audio_config
    )
    
    transcripcion_completa = []
    progreso = 0
    done = False
    error_msg = None

    def transcribed_cb(evt):
        """Callback cuando se reconoce un segmento con hablante"""
        nonlocal progreso
        if evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
            speaker_id = evt.result.speaker_id if hasattr(evt.result, 'speaker_id') else "Desconocido"
            text = evt.result.text
            offset = evt.result.offset / 10_000_000  # Convertir a segundos
            duration = evt.result.duration / 10_000_000
            
            transcripcion_completa.append({
                'speaker': speaker_id,
                'offset': offset,
                'duration': duration,
                'text': text
            })
            
            progreso = min(progreso + 0.02, 1.0)
            _progress_bar.progress(progreso)
            _status_text.text(f"🎤 Hablante {speaker_id}: {text[:50]}...")

    def session_stopped_cb(evt):
        """Callback cuando termina la sesión"""
        nonlocal done
        done = True

    def canceled_cb(evt):
        """Callback en caso de error"""
        nonlocal done, error_msg
        if evt.reason == speechsdk.CancellationReason.Error:
            error_msg = f"Error: {evt.error_details}"
        done = True

    # Conectar callbacks
    conversation_transcriber.transcribed.connect(transcribed_cb)
    conversation_transcriber.session_stopped.connect(session_stopped_cb)
    conversation_transcriber.canceled.connect(canceled_cb)

    # Iniciar transcripción
    conversation_transcriber.start_transcribing_async()
    
    # Esperar hasta que termine
    while not done:
        time.sleep(0.5)
    
    conversation_transcriber.stop_transcribing_async()
    
    if error_msg:
        st.error(f"❌ {error_msg}")
    
    _progress_bar.progress(1.0)
    return transcripcion_completa

# ==============================
# CONVERSIÓN MP3 → WAV SIN FFMPEG
# ==============================
@st.cache_data(ttl=600)
def convertir_a_wav_si_es_necesario(uploaded_file):
    """Convierte MP3 o WAV subido a WAV PCM 16 kHz mono, sin ffmpeg ni audioread"""
    temp_input = tempfile.NamedTemporaryFile(delete=False, suffix=f"_{uploaded_file.name}")
    temp_input.write(uploaded_file.read())
    temp_input.flush()

    temp_wav = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")

    if uploaded_file.name.lower().endswith(".mp3"):
        st.info("🎧 Convirtiendo MP3 a WAV PCM (16 kHz mono)...")

        try:
            data, sr = sf.read(temp_input.name)
        except RuntimeError:
            st.error("⚠️ Tu instalación de soundfile/libsndfile no soporta MP3. Instala 'ffmpeg' o convierte el audio a WAV manualmente.")
            st.stop()

        if data.ndim > 1:
            data = data.mean(axis=1)

        if sr != 16000:
            num_samples = round(len(data) * 16000 / sr)
            data = scipy.signal.resample(data, num_samples)
            sr = 16000

        sf.write(temp_wav.name, data, sr, subtype='PCM_16')

    else:
        with open(temp_input.name, "rb") as src, open(temp_wav.name, "wb") as dst:
            dst.write(src.read())

    return temp_wav.name

# ==============================
# INTERFAZ STREAMLIT CON TABS
# ==============================
st.title("🎙️ Transcriptor con Diarización de Hablantes")
st.markdown("Sube un archivo de audio (MP3 o WAV) y obtén una transcripción con **identificación de hablantes** y timestamps usando Azure Speech SDK.")

# Configuración en sidebar
with st.sidebar:
    st.header("⚙️ Configuración")
    max_speakers = st.slider("Máximo de hablantes a detectar:", 2, 10, 5)
    idioma = st.selectbox("Idioma:", [
        ("es-ES", "Español (España)"),
        ("es-MX", "Español (México)"),
        ("en-US", "Inglés (EE.UU.)"),
        ("en-GB", "Inglés (Reino Unido)"),
    ], format_func=lambda x: x[1])

audio_file = st.file_uploader("🎵 Sube tu archivo de audio:", type=["wav", "mp3"])

# Inicializar session_state para mantener los resultados
if 'resultado' not in st.session_state:
    st.session_state.resultado = None
if 'resumen' not in st.session_state:
    st.session_state.resumen = None

if audio_file is not None:
    st.audio(audio_file)
    wav_path = convertir_a_wav_si_es_necesario(audio_file)

    st.success("✅ Archivo convertido correctamente.")

    tab_transcribir, tab_resumen, tab_exportar = st.tabs(["📝 Transcribir", "📊 Resumen", "💾 Exportar"])

    with tab_transcribir:
        if st.button("🎙️ Iniciar Transcripción con Diarización", type="primary"):
            with st.spinner("Transcribiendo audio con identificación de hablantes... esto puede tardar ⏳"):
                progress_bar = st.progress(0)
                status_text = st.empty()
                st.session_state.resultado = transcribir_audio_con_diarizacion(wav_path, progress_bar, status_text)
                st.session_state.resumen = None  # Reset resumen al hacer nueva transcripción

            if st.session_state.resultado:
                st.markdown("### 📝 Transcripción con Hablantes Identificados")
                
                # Agrupar por hablante para mostrar estadísticas
                hablantes = {}
                for item in st.session_state.resultado:
                    speaker = item['speaker']
                    if speaker not in hablantes:
                        hablantes[speaker] = []
                    hablantes[speaker].append(item)
                
                # Mostrar resumen
                st.info(f"🎭 **Hablantes detectados:** {len(hablantes)}")
                
                # Mostrar transcripción
                for item in st.session_state.resultado:
                    speaker_color = ["🔵", "🟢", "🟠", "🟣", "🟡", "🔴"][hash(item['speaker']) % 6]
                    st.write(
                        f"{speaker_color} **Hablante {item['speaker']}** "
                        f"[{item['offset']:.2f}s - {item['offset'] + item['duration']:.2f}s]"
                    )
                    st.write(f"   {item['text']}")
                    st.divider()
            else:
                st.error("No se obtuvo ninguna transcripción.")
        
        # Mostrar transcripción si ya existe en session_state
        elif st.session_state.resultado:
            st.markdown("### 📝 Transcripción con Hablantes Identificados")
            
            # Agrupar por hablante para mostrar estadísticas
            hablantes = {}
            for item in st.session_state.resultado:
                speaker = item['speaker']
                if speaker not in hablantes:
                    hablantes[speaker] = []
                hablantes[speaker].append(item)
            
            # Mostrar resumen
            st.info(f"🎭 **Hablantes detectados:** {len(hablantes)}")
            
            # Mostrar transcripción
            for item in st.session_state.resultado:
                speaker_color = ["🔵", "🟢", "🟠", "🟣", "🟡", "🔴"][hash(item['speaker']) % 6]
                st.write(
                    f"{speaker_color} **Hablante {item['speaker']}** "
                    f"[{item['offset']:.2f}s - {item['offset'] + item['duration']:.2f}s]"
                )
                st.write(f"   {item['text']}")
                st.divider()

    with tab_resumen:
        if st.session_state.resultado:
            st.markdown("### 📊 Resumen de la Conversación")
            
            if st.button("📝 Generar Resumen", type="primary"):
                with st.spinner("Generando resumen con Azure Language Service..."):
                    # Obtener texto completo de la transcripción
                    texto_completo = " ".join([item['text'] for item in st.session_state.resultado])
                    
                    # Generar resumen extractivo
                    st.session_state.resumen = generar_resumen(texto_completo, tipo="extractive")
                    
                    if st.session_state.resumen:
                        st.success("✅ Resumen generado correctamente")
            
            # Mostrar resumen si existe
            if st.session_state.resumen:
                st.markdown("#### 📄 Resumen:")
                st.info(st.session_state.resumen)
                
                # Opción para descargar resumen
                st.download_button(
                    label="⬇️ Descargar Resumen",
                    data=st.session_state.resumen,
                    file_name="resumen_conversacion.txt",
                    mime="text/plain"
                )
                
                # Estadísticas adicionales
                st.markdown("#### 📈 Estadísticas:")
                col1, col2, col3 = st.columns(3)
                
                texto_completo = " ".join([item['text'] for item in st.session_state.resultado])
                
                with col1:
                    st.metric("Palabras originales", len(texto_completo.split()))
                with col2:
                    st.metric("Palabras en resumen", len(st.session_state.resumen.split()))
                with col3:
                    reduccion = (1 - len(st.session_state.resumen.split()) / len(texto_completo.split())) * 100
                    st.metric("Reducción", f"{reduccion:.1f}%")
        else:
            st.info("Primero realiza la transcripción para poder generar un resumen.")

    with tab_exportar:
        if st.session_state.resultado:
            def formato_tiempo(segundos):
                horas = int(segundos // 3600)
                minutos = int((segundos % 3600) // 60)
                segs = int(segundos % 60)
                milis = int((segundos - int(segundos)) * 1000)
                return f"{horas:02}:{minutos:02}:{segs:02},{milis:03}"

            def generar_srt(transcripcion):
                srt_lines = []
                for i, item in enumerate(transcripcion, start=1):
                    start = formato_tiempo(item['offset'])
                    end = formato_tiempo(item['offset'] + item['duration'])
                    speaker = f"Hablante {item['speaker']}"
                    srt_lines.append(f"{i}\n{start} --> {end}\n[{speaker}] {item['text']}\n")
                return "\n".join(srt_lines)

            def generar_vtt(transcripcion):
                vtt_lines = ["WEBVTT\n"]
                for item in transcripcion:
                    start = formato_tiempo(item['offset']).replace(",", ".")
                    end = formato_tiempo(item['offset'] + item['duration']).replace(",", ".")
                    speaker = f"Hablante {item['speaker']}"
                    vtt_lines.append(f"{start} --> {end}\n<v {speaker}>{item['text']}\n")
                return "\n".join(vtt_lines)
            
            def generar_txt(transcripcion):
                txt_lines = []
                for item in transcripcion:
                    tiempo = formato_tiempo(item['offset'])
                    speaker = f"Hablante {item['speaker']}"
                    txt_lines.append(f"[{tiempo}] {speaker}: {item['text']}")
                return "\n\n".join(txt_lines)

            formato = st.selectbox("Elige formato de exportación:", ["SRT", "VTT", "TXT"])
            
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("📥 Exportar", type="primary"):
                    if formato == "SRT":
                        contenido = generar_srt(st.session_state.resultado)
                        nombre = "transcripcion_diarizacion.srt"
                        mime = "text/plain"
                    elif formato == "VTT":
                        contenido = generar_vtt(st.session_state.resultado)
                        nombre = "transcripcion_diarizacion.vtt"
                        mime = "text/vtt"
                    else:
                        contenido = generar_txt(st.session_state.resultado)
                        nombre = "transcripcion_diarizacion.txt"
                        mime = "text/plain"

                    st.download_button(
                        label=f"⬇️ Descargar {nombre}",
                        data=contenido,
                        file_name=nombre,
                        mime=mime
                    )
            
            with col2:
                # Vista previa
                with st.expander("👁️ Vista previa"):
                    if formato == "SRT":
                        st.text(generar_srt(st.session_state.resultado)[:500] + "...")
                    elif formato == "VTT":
                        st.text(generar_vtt(st.session_state.resultado)[:500] + "...")
                    else:
                        st.text(generar_txt(st.session_state.resultado)[:500] + "...")
        else:
            st.info("Primero realiza la transcripción para poder exportar.")