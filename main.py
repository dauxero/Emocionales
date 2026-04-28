"""
Microservicio de Análisis Emocional — Diario Emocional
Detecta emociones y nivel de riesgo psicológico en textos en español
usando modelos de Hugging Face (pysentimiento + zero-shot classification).

Alineado con el "Kit de Emociones" de la plataforma educativa:
  • 8 Emociones Núcleo (Plutchik / Goleman / OMS)
  • 3 Niveles de Intensidad (Leve / Moderado / Intenso)
  • 3 Rutas de Acompañamiento (Verde / Ámbar / Rojo)
  • Refuerzo positivo y gamificación
"""

from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from transformers import pipeline

# ══════════════════════════════════════════════
#  CONSTANTES Y CONFIGURACIÓN
# ══════════════════════════════════════════════

EMOTION_MODEL = "pysentimiento/robertuito-emotion-analysis"
ZERO_SHOT_MODEL = "MoritzLaurer/mDeBERTa-v3-base-mnli-xnli"

# ── Mapeo: etiquetas del modelo → 8 Emociones Núcleo del Kit ──
EMOTION_MAP_ES = {
    "joy":      {"es": "Alegría",               "emoji": "😊", "category": "positiva"},
    "sadness":  {"es": "Tristeza",              "emoji": "😢", "category": "negativa"},
    "fear":     {"es": "Miedo",                 "emoji": "😰", "category": "negativa"},
    "anger":    {"es": "Ira",                   "emoji": "😠", "category": "negativa"},
    "disgust":  {"es": "Desgano/Desmotivación", "emoji": "😞", "category": "negativa"},
    "surprise": {"es": "Sorpresa",              "emoji": "😲", "category": "neutra"},
    "others":   {"es": "Neutral",               "emoji": "😐", "category": "neutra"},
}

# ── Etiquetas zero-shot de riesgo (ampliadas para contexto escolar) ──
RISK_LABELS = [
    # Alto riesgo
    "ideación suicida",
    "autolesión",
    # Riesgo medio — psicológico
    "depresión",
    "ansiedad",
    # Riesgo medio — escolar
    "acoso escolar",
    "ciberacoso",
    "exclusión social",
    "violencia",
    # Positivos (ancla de contraste)
    "bienestar",
    "tranquilidad",
]

HIGH_RISK_LABELS = {"ideación suicida", "autolesión"}
MEDIUM_RISK_LABELS = {"depresión", "ansiedad", "acoso escolar",
                       "ciberacoso", "exclusión social", "violencia"}
POSITIVE_LABELS = {"bienestar", "tranquilidad"}
NEGATIVE_EMOTIONS = {"sadness", "anger", "fear", "disgust"}
POSITIVE_EMOTIONS = {"joy"}

# ── Mensajes de refuerzo positivo / gamificación ──
POSITIVE_REINFORCEMENT = [
    "🌟 ¡Excelente! Reconocer emociones positivas es una fortaleza.",
    "🏅 ¡Llevas un gran registro! Cada entrada en tu diario te hace más consciente de ti mismo/a.",
    "💪 Sentirte bien es importante. Recuerda este momento cuando tengas un día difícil.",
    "🎯 ¡Sigue así! Escribir sobre tus emociones mejora tu inteligencia emocional.",
    "🌈 Compartir lo bueno también cuenta. ¿Le has dicho a alguien lo que te hizo feliz hoy?",
]

# Almacén global de pipelines
models: dict = {}


# ══════════════════════════════════════════════
#  FUNCIONES AUXILIARES
# ══════════════════════════════════════════════

def _classify_intensity(score: float) -> dict:
    """Clasifica el score de la emoción en niveles del Kit de Emociones."""
    if score >= 0.70:
        return {"level": "Intenso", "emoji": "🔥", "value": 3}
    if score >= 0.40:
        return {"level": "Moderado", "emoji": "⚡", "value": 2}
    return {"level": "Leve", "emoji": "🌱", "value": 1}


def _get_positive_reinforcement(emotion_en: str, score: float) -> list[str]:
    """Devuelve mensajes de refuerzo cuando la emoción es positiva."""
    if emotion_en not in POSITIVE_EMOTIONS:
        return []

    import random
    random.seed(int(score * 10000))  # Determinístico por score
    count = 2 if score >= 0.7 else 1
    return random.sample(POSITIVE_REINFORCEMENT, k=min(count, len(POSITIVE_REINFORCEMENT)))


def _determine_alert(
    dominant: dict,
    risk_scores: dict[str, float],
    student_age_range: str | None,
) -> tuple[str, str, str, list[str], str, bool]:
    """
    Determina el nivel de alerta según el Kit de Emociones.
    Retorna: (nivel, emoji, descripción, recomendaciones, ruta, requires_follow_up)
    """

    max_high = max((risk_scores.get(l, 0) for l in HIGH_RISK_LABELS), default=0)
    max_med = max((risk_scores.get(l, 0) for l in MEDIUM_RISK_LABELS), default=0)
    emo = dominant["label"]
    emo_score = dominant["score"]
    emo_es = EMOTION_MAP_ES.get(emo, {}).get("es", emo)

    # Detectar etiquetas escolares activas
    school_labels_active = [
        l for l in ["acoso escolar", "ciberacoso", "exclusión social", "violencia"]
        if risk_scores.get(l, 0) > 0.35
    ]

    # ════════════════════════════════════════════
    # 🔴 ROJO — Ruta de Alerta Inmediata
    # ════════════════════════════════════════════
    if max_high > 0.45:
        return (
            "Rojo", "🔴",
            "Se han detectado indicadores de alto riesgo. "
            "Es necesario activar el protocolo de acompañamiento inmediato.",
            [
                "🚨 Activar protocolo: notificar al orientador/psicólogo escolar.",
                "Contactar al acudiente o adulto responsable del estudiante.",
                "Habla con un adulto de confianza o profesional de salud mental.",
                "Línea de crisis (México): 800 290 0024",
                "Línea de la vida (Colombia): 106",
                "Teléfono de la Esperanza (España): 717 003 717",
                "No estás solo/a. Pedir ayuda es un acto de valentía.",
            ],
            "Alerta a orientador escolar — Intervención inmediata",
            True,
        )

    if emo in NEGATIVE_EMOTIONS and emo_score > 0.6 and max_med > 0.5:
        extra = []
        if school_labels_active:
            extra = [
                f"⚠️ Se detectaron señales de: {', '.join(school_labels_active)}.",
                "Reportar al comité de convivencia escolar para investigación.",
            ]
        return (
            "Rojo", "🔴",
            f"Se detecta una emoción intensa de '{emo_es}' combinada con "
            "indicadores de riesgo significativos.",
            [
                "🚨 Notificar al orientador/psicólogo escolar.",
                "Considera hablar con un profesional de salud mental.",
                "Comparte cómo te sientes con alguien de confianza.",
                "Recuerda que las emociones intensas son temporales.",
                *extra,
            ],
            "Alerta a orientador escolar — Seguimiento prioritario",
            True,
        )

    # ════════════════════════════════════════════
    # 🟡 ÁMBAR — Ruta de Actividades de Bienestar
    # ════════════════════════════════════════════
    if max_med > 0.4 or (emo in NEGATIVE_EMOTIONS and emo_score > 0.5):
        activities = [
            "🧘 Tómate un momento para respirar profundamente (prueba 4-7-8).",
            "📝 Escribe más sobre cómo te sientes; ayuda a procesar emociones.",
            "🗣️ Habla con alguien de confianza sobre lo que estás viviendo.",
            "🎵 Prueba actividades de bienestar: caminar, escuchar música, dibujar.",
        ]

        if school_labels_active:
            activities.append(
                f"📋 Se detectaron posibles señales de: {', '.join(school_labels_active)}. "
                "Si esto persiste, se recomienda informar al orientador."
            )

        # Recomendación por edad
        if student_age_range in ("6-9", "10-13"):
            activities.append(
                "👨‍👩‍👧 Comparte lo que sientes con tu familia o tu profesor/a de confianza."
            )

        return (
            "Ámbar", "🟡",
            f"Se detectan señales que merecen atención. "
            f"Emoción predominante: '{emo_es}'.",
            activities,
            "Actividades de bienestar — Seguimiento sugerido",
            False,
        )

    # ════════════════════════════════════════════
    # 🟢 VERDE — Ruta de Refuerzo Positivo
    # ════════════════════════════════════════════
    return (
        "Verde", "🟢",
        f"No se detectan señales de riesgo significativas. "
        f"Emoción predominante: '{emo_es}'.",
        [
            "✨ ¡Sigue escribiendo en tu diario! Es una excelente práctica.",
            "🔍 Reflexiona sobre lo que te hace sentir bien.",
            "🤝 Comparte tus experiencias positivas con otros.",
            "🎯 Reconocer tus emociones es el primer paso para la inteligencia emocional.",
        ],
        "Refuerzo positivo — Sin intervención requerida",
        False,
    )


# ══════════════════════════════════════════════
#  LIFESPAN: carga / descarga de modelos
# ══════════════════════════════════════════════
@asynccontextmanager
async def lifespan(_app: FastAPI):
    print("🔄 Cargando modelos de IA …")

    models["emotion"] = pipeline(
        "text-classification",
        model=EMOTION_MODEL,
        top_k=None,
        device=-1,
    )
    print(f"  ✅ Emociones: {EMOTION_MODEL}")

    models["zero_shot"] = pipeline(
        "zero-shot-classification",
        model=ZERO_SHOT_MODEL,
        device=-1,
    )
    print(f"  ✅ Zero-shot: {ZERO_SHOT_MODEL}")
    print("🚀 Servicio listo.")

    yield

    models.clear()
    print("👋 Modelos liberados.")


# ══════════════════════════════════════════════
#  APP FASTAPI
# ══════════════════════════════════════════════
app = FastAPI(
    title="Diario Emocional — API de Análisis",
    description=(
        "Microservicio de IA para detectar emociones y nivel de riesgo "
        "psicológico en textos en español. Alineado con el Kit de Emociones "
        "de la plataforma educativa."
    ),
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ══════════════════════════════════════════════
#  ESQUEMAS PYDANTIC
# ══════════════════════════════════════════════
class TextRequest(BaseModel):
    text: str = Field(
        ...,
        min_length=3,
        max_length=5000,
        examples=["Hoy me siento muy solo y no quiero seguir"],
    )
    student_age_range: str | None = Field(
        default=None,
        description="Rango de edad del estudiante: '6-9', '10-13', '14-17'",
        examples=["10-13"],
    )
    context: str | None = Field(
        default=None,
        description="Contexto de la entrada: 'diario', 'check-in', 'actividad'",
        examples=["diario"],
    )


class EmotionDetail(BaseModel):
    label_en: str
    label_es: str
    emoji: str
    category: str
    score: float


class IntensityDetail(BaseModel):
    level: str
    emoji: str
    value: int


class RiskDetail(BaseModel):
    label: str
    score: float
    is_school_related: bool


class RouteDetail(BaseModel):
    name: str
    requires_follow_up: bool


class AnalysisResponse(BaseModel):
    text: str
    timestamp: str
    context: str | None
    student_age_range: str | None

    # Emoción principal
    dominant_emotion: EmotionDetail
    intensity: IntensityDetail
    all_emotions: list[EmotionDetail]

    # Riesgo
    risk_analysis: list[RiskDetail]

    # Alerta y ruta de acompañamiento
    alert_level: str
    alert_emoji: str
    alert_description: str
    route: RouteDetail
    recommendations: list[str]

    # Gamificación
    positive_reinforcement: list[str]


# ══════════════════════════════════════════════
#  ENDPOINTS
# ══════════════════════════════════════════════
@app.get("/", tags=["General"])
async def root():
    return {
        "service": "Diario Emocional — API de Análisis",
        "version": "2.0.0",
        "kit": "Kit de Emociones — Plataforma Educativa",
        "status": "running",
        "docs_url": "/docs",
    }


@app.get("/health", tags=["General"])
async def health():
    loaded = "emotion" in models and "zero_shot" in models
    return {
        "status": "healthy" if loaded else "loading",
        "models": {
            "emotion": EMOTION_MODEL if "emotion" in models else "not loaded",
            "zero_shot": ZERO_SHOT_MODEL if "zero_shot" in models else "not loaded",
        },
    }


@app.get("/emotions", tags=["Referencia"])
async def list_emotions():
    """Devuelve las 8 emociones núcleo del Kit y sus metadatos."""
    return {
        "kit_version": "Kit de Emociones — Plataforma Educativa",
        "base_framework": "Plutchik / Goleman / OMS",
        "emotions": [
            {"en": key, **value}
            for key, value in EMOTION_MAP_ES.items()
        ],
        "intensity_levels": [
            {"level": "Leve",     "emoji": "🌱", "range": "score < 0.40",  "value": 1},
            {"level": "Moderado", "emoji": "⚡", "range": "0.40 ≤ score < 0.70", "value": 2},
            {"level": "Intenso",  "emoji": "🔥", "range": "score ≥ 0.70",  "value": 3},
        ],
        "alert_levels": [
            {"level": "Verde", "emoji": "🟢", "route": "Refuerzo positivo"},
            {"level": "Ámbar", "emoji": "🟡", "route": "Actividades de bienestar"},
            {"level": "Rojo",  "emoji": "🔴", "route": "Alerta a orientador escolar"},
        ],
    }


@app.post("/analyze", response_model=AnalysisResponse, tags=["Análisis"])
async def analyze_text(request: TextRequest):
    """
    Analiza el texto de un diario emocional y devuelve:
    - Emoción predominante (en español, con nivel de intensidad)
    - Indicadores de riesgo psicológico y escolar
    - Nivel de alerta y ruta de acompañamiento (Verde / Ámbar / Rojo)
    - Refuerzo positivo (gamificación) para emociones positivas
    """
    if "emotion" not in models or "zero_shot" not in models:
        raise HTTPException(
            status_code=503,
            detail="Los modelos aún se están cargando. Intenta en unos segundos.",
        )

    text = request.text.strip()

    # ── 1. Análisis de emociones ──
    emo_raw = models["emotion"](text)
    emotions = sorted(emo_raw[0], key=lambda x: x["score"], reverse=True)
    dominant = emotions[0]

    # ── 2. Clasificación zero-shot de riesgo ──
    zs = models["zero_shot"](text, RISK_LABELS, multi_label=True)
    risk_scores = dict(zip(zs["labels"], zs["scores"]))
    risk_sorted = sorted(risk_scores.items(), key=lambda x: x[1], reverse=True)

    # ── 3. Nivel de alerta y ruta de acompañamiento ──
    level, emoji, desc, recs, route_name, follow_up = _determine_alert(
        dominant, risk_scores, request.student_age_range
    )

    # ── 4. Intensidad ──
    intensity = _classify_intensity(dominant["score"])

    # ── 5. Refuerzo positivo ──
    reinforcement = _get_positive_reinforcement(dominant["label"], dominant["score"])

    # ── 6. Mapeo de emociones al español ──
    school_risk_labels = {"acoso escolar", "ciberacoso", "exclusión social", "violencia"}

    def _map_emotion(e: dict) -> EmotionDetail:
        meta = EMOTION_MAP_ES.get(e["label"], {"es": e["label"], "emoji": "❓", "category": "desconocida"})
        return EmotionDetail(
            label_en=e["label"],
            label_es=meta["es"],
            emoji=meta["emoji"],
            category=meta["category"],
            score=round(e["score"], 4),
        )

    return AnalysisResponse(
        text=text,
        timestamp=datetime.now(timezone.utc).isoformat(),
        context=request.context,
        student_age_range=request.student_age_range,

        dominant_emotion=_map_emotion(dominant),
        intensity=IntensityDetail(**intensity),
        all_emotions=[_map_emotion(e) for e in emotions],

        risk_analysis=[
            RiskDetail(
                label=label,
                score=round(score, 4),
                is_school_related=label in school_risk_labels,
            )
            for label, score in risk_sorted
        ],

        alert_level=level,
        alert_emoji=emoji,
        alert_description=desc,
        route=RouteDetail(name=route_name, requires_follow_up=follow_up),
        recommendations=recs,

        positive_reinforcement=reinforcement,
    )
