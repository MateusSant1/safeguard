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

# --- Perímetro ---
PERIMETER_FILE = BASE_DIR / "data" / "perimeter.json"

# --- Eventos (capturas de invasão) ---
EVENTS_DIR = BASE_DIR / "events"
FRAMES_PER_EVENT = 5
NOTIFICATION_COOLDOWN_SECONDS = 60

# --- Telegram ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
