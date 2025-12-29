import streamlit as st
import requests, os

SPEECH_KEY = os.getenv("SPEECH_KEY") or st.secrets.get("SPEECH_KEY")
REGION = os.getenv("SPEECH_REGION") or st.secrets.get("SPEECH_REGION")
TRANSLATOR_KEY = os.getenv("TRANSLATOR_KEY") or st.secrets.get("TRANSLATOR_KEY")
TRANSLATOR_REGION = os.getenv("TRANSLATOR_REGION") or st.secrets.get("TRANSLATOR_REGION")

if not SPEECH_KEY or not REGION:
    st.error("❌ No se encontraron las variables de entorno SPEECH_KEY o SPEECH_REGION.")
    st.stop()


# Obtener las variables desde variables de entorno o secrets como fallback
SPEECH_KEY = os.getenv("SPEECH_KEY") or st.secrets.get("SPEECH_KEY")
REGION = os.getenv("REGION") or st.secrets.get("REGION")
TRANSLATOR_KEY = os.getenv("TRANSLATOR_KEY") or st.secrets.get("TRANSLATOR_KEY")
TRANSLATOR_REGION = os.getenv("TRANSLATOR_REGION") or st.secrets.get("TRANSLATOR_REGION")

st.title("🎤 Audio con Azure Speech")


tab1, tab2,tab3 = st.tabs(["Transcripción", " Texto a Voz","Texto ingles a voz en español"])
with tab1:
    audio_file = st.file_uploader("Sube un archivo de audio:", type=["wav"], help="El archivo debe estar en formato WAV, 16kHz, mono")
    if audio_file is not None:
        st.audio(audio_file, format="audio/wav")
        with st.spinner("Transcribiendo audio..."):
            speech_to_text_url = f"https://{REGION}.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1?language=es-ES"
            headers = {
                "Ocp-Apim-Subscription-Key": SPEECH_KEY,
                "Content-Type": "audio/wav; codecs=audio/pcm; samplerate=16000"
            }
            audio_data = audio_file.read()
            response = requests.post(speech_to_text_url, headers=headers, data=audio_data)
            if response.status_code == 200:
                result = response.json()
                if "DisplayText" in result:
                    st.markdown("### Texto transcrito:")
                    st.write(result["DisplayText"])
                else:
                    st.error("No se pudo transcribir el audio.")
            else:
                st.error(f"Error en la transcripción: {response.status_code} - {response.text}")
with tab2:
    st.markdown("### Convertir Texto a Voz")
    texto_voz = st.text_input("Introduce el texto que quieres convertir a voz:")
    
    @st.cache_data(ttl=600)
    def get_available_voices():
        available_voices = []
        try:
            voices_url = f"https://{REGION}.tts.speech.microsoft.com/cognitiveservices/voices/list"
            rv = requests.get(voices_url, headers={"Ocp-Apim-Subscription-Key": SPEECH_KEY}, timeout=5)
            if rv.status_code == 200:
                voices_json = rv.json()
                for v in voices_json:
                    locale = v.get("Locale") or v.get("locale") or v.get("LocaleName")
                    short = v.get("ShortName") or v.get("Name") or v.get("shortName")
                    if locale and short and str(locale).lower().startswith("es"):
                        available_voices.append(short)
        except Exception:
            pass
        if not available_voices:
            available_voices = ["es-ES-ElviraNeural"]
        return available_voices

    if texto_voz:  
        tts_url = f"https://{REGION}.tts.speech.microsoft.com/cognitiveservices/v1"
        available_voices = get_available_voices()

        voice = st.selectbox("Selecciona la voz:", available_voices, index=0)
        
        
        if st.button("🔊 Generar Audio"):

            ssml = f"""<speak version='1.0' xml:lang='es-ES'>
            <voice xml:lang='es-ES' name='{voice}'>
                {texto_voz}
            </voice>
            </speak>"""
        
            headers = {
                "Ocp-Apim-Subscription-Key": SPEECH_KEY,
                "Content-Type": "application/ssml+xml",
                "X-Microsoft-OutputFormat": "audio-16khz-128kbitrate-mono-mp3",
                "User-Agent": "curso-ia-speech-ejemplo"
            }

            with st.spinner("Generando audio..."):
                try:
                    tts_resp = requests.post(tts_url, headers=headers, data=ssml.encode("utf-8"))
                    
                    if tts_resp.status_code == 200:
                        st.audio(tts_resp.content, format="audio/mp3")
                        st.success("¡Audio generado con éxito!")
                    else:
                        st.error(f"Error al generar el audio: {tts_resp.status_code}")
                        # Mostrar texto de error y sugerir voces disponibles
                        try:
                            st.write(tts_resp.json())
                        except Exception:
                            st.write(tts_resp.text)
                        st.info("Voces disponibles (filtradas por 'es-'): ")
                        st.write(available_voices)
                except Exception as e:
                    st.error(f"Error inesperado: {str(e)}")
with tab3:
    st.markdown("### Convertir Texto en Inglés a Voz en Español")
    texto_ingles = st.text_input("Introduce el texto en inglés que quieres convertir a voz en español:")
    
    if texto_ingles:  
        # Traducir el texto al español usando Translator
        translate_url = f"https://api.cognitive.microsofttranslator.com/translate?api-version=3.0&to=es"
        headers_translate = {
            "Ocp-Apim-Subscription-Key": TRANSLATOR_KEY,
            "Ocp-Apim-Subscription-Region": TRANSLATOR_REGION,
            "Content-Type": "application/json"
        }
        body_translate = [{"text": texto_ingles}]
        
        try:
            translate_resp = requests.post(translate_url, headers=headers_translate, json=body_translate)
            translate_resp.raise_for_status()
            translated_text = translate_resp.json()[0]["translations"][0]["text"]
                        
            tts_url = f"https://{REGION}.tts.speech.microsoft.com/cognitiveservices/v1"
            voice = "es-ES-ElviraNeural" 
            
            ssml = f"""<speak version='1.0' xml:lang='es-ES'>
                <voice xml:lang='es-ES' name='{voice}'>
                    {translated_text}
                </voice>
            </speak>"""
            
            headers_tts = {
                "Ocp-Apim-Subscription-Key": SPEECH_KEY,
                "Content-Type": "application/ssml+xml",
                "X-Microsoft-OutputFormat": "audio-16khz-128kbitrate-mono-mp3",
                "User-Agent": "curso-ia-speech-ejemplo"
            }
            
            with st.spinner("Generando audio..."):
                tts_resp = requests.post(tts_url, headers=headers_tts, data=ssml.encode("utf-8"))
                    
                if tts_resp.status_code == 200:
                    st.audio(tts_resp.content, format="audio/mp3")
                    st.success("¡Audio generado con éxito!")
                else:
                    st.error(f"Error al generar el audio: {tts_resp.status_code}")
                    st.write(tts_resp.text)
        except requests.exceptions.RequestException as e:
            st.error(f"Error al traducir el texto: {e}")

