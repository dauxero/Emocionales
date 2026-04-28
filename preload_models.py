"""
Pre-descarga los modelos de Hugging Face durante el build de Docker
para que el contenedor no dependa de llamadas externas en tiempo de ejecución.
"""

from transformers import pipeline

EMOTION_MODEL = "pysentimiento/robertuito-emotion-analysis"
ZERO_SHOT_MODEL = "MoritzLaurer/mDeBERTa-v3-base-mnli-xnli"

print(f"⬇️  Descargando modelo de emociones: {EMOTION_MODEL}")
pipeline("text-classification", model=EMOTION_MODEL)
print("  ✅ Listo")

print(f"⬇️  Descargando modelo zero-shot: {ZERO_SHOT_MODEL}")
pipeline("zero-shot-classification", model=ZERO_SHOT_MODEL)
print("  ✅ Listo")

print("🎉 Todos los modelos descargados exitosamente.")
