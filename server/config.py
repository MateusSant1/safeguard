"""
Carrega as variáveis do .env e expõe como constantes do projeto.

Nada de lógica aqui além de ler variáveis de ambiente e montar caminhos —
qualquer outro módulo importa deste arquivo em vez de chamar os.getenv()
espalhado pelo código.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

# --- Câmera ---
CAMERA_INDEX = int(os.getenv("CAMERA_INDEX", "0"))

# --- Modelo de detecção (MobileNet-SSD) ---
MODEL_PROTOTXT = BASE_DIR / "models" / "MobileNetSSD_deploy.prototxt"
MODEL_WEIGHTS = BASE_DIR / "models" / "MobileNetSSD_deploy.caffemodel"

VOC_CLASSES = [
    "background", "aeroplane", "bicycle", "bird", "boat", "bottle", "bus",
    "car", "cat", "chair", "cow", "diningtable", "dog", "horse",
    "motorbike", "person", "pottedplant", "sheep", "sofa", "train",
    "tvmonitor",
]
ANIMAL_CLASSES = {"bird", "cat", "cow", "dog", "horse", "sheep"}

# --- Detecção (limiares calibrados com a webcam; ajustáveis pelo .env) ---
# Área mínima (px) de uma região em movimento para acionar o estágio 2.
MOTION_THRESHOLD_AREA = int(os.getenv("MOTION_THRESHOLD_AREA", "500"))
# Confiança mínima para aceitar uma detecção de "person" (0.5 perdia muita gente).
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.26"))
# Frames para o MOG2 aprender o fundo antes de agir sobre o movimento.
WARM_UP_FRAMES = int(os.getenv("WARM_UP_FRAMES", "30"))

# --- Perímetro ---
PERIMETER_FILE = BASE_DIR / "data" / "perimeter.json"

# Como decidir se a pessoa está "dentro" do perímetro:
#   "foot"    -> meio da base da caixa (comportamento original; falha quando a
#                caixa pega só o tronco)
#   "center"  -> centro da caixa
#   "overlap" -> fração da caixa que cai dentro do polígono >= MIN_OVERLAP_RATIO
DECISION_MODE = os.getenv("DECISION_MODE", "overlap")
MIN_OVERLAP_RATIO = float(os.getenv("MIN_OVERLAP_RATIO", "0.15"))

# --- Eventos (capturas de invasão) ---
EVENTS_DIR = BASE_DIR / "events"
FRAMES_PER_EVENT = 5
# Intervalo entre as fotos de um mesmo evento (5 fotos x 1 s = ~4 s de cena).
EVENT_FRAME_INTERVAL_SECONDS = float(os.getenv("EVENT_FRAME_INTERVAL_SECONDS", "1.0"))
# Espera mínima entre dois eventos (e duas notificações).
NOTIFICATION_COOLDOWN_SECONDS = int(os.getenv("NOTIFICATION_COOLDOWN_SECONDS", "60"))

# --- Servidor web ---
SERVER_HOST = os.getenv("SERVER_HOST", "0.0.0.0")
SERVER_PORT = int(os.getenv("SERVER_PORT", "5000"))
CLIENT_DIR = BASE_DIR.parent / "client"
JPEG_QUALITY = int(os.getenv("JPEG_QUALITY", "80"))
EVENTS_LIST_LIMIT = 50

# --- Telegram ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
# Usa só IPv4 para falar com o Telegram (redes com IPv6 quebrado dão ReadTimeout).
TELEGRAM_FORCE_IPV4 = os.getenv("TELEGRAM_FORCE_IPV4", "1").lower() not in ("0", "false", "no")
