"""
Orquestra o pipeline operacional numa thread própria:

    camera -> motion_detector -> object_detector -> perimeter -> event_recorder
                                                              -> notifier (thread à parte)

É o ÚNICO dono da câmera: a API (app.py) nunca lê da câmera, só pede o
último frame guardado aqui (snapshot / video_feed). Assim não há duas
leituras disputando o dispositivo.

Os módulos de apoio podem ser injetados no construtor (útil para testar
sem webcam nem modelo); os que não forem passados são criados em start().
"""
import logging
import threading
import time
from datetime import datetime
from typing import Callable

from pathlib import Path
from typing import TYPE_CHECKING

import cv2
import numpy as np

from server.config import (
    ANIMAL_CLASSES,
    CONFIDENCE_THRESHOLD,
    DECISION_MODE,
    JPEG_QUALITY,
    MOTION_THRESHOLD_AREA,
    NOTIFICATION_COOLDOWN_SECONDS,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
    WARM_UP_FRAMES,
)
from server.notifier import send_alert
from server.perimeter import (
    box_overlap_ratio,
    build_mask,
    denormalize,
    load_perimeter,
    person_in_perimeter,
)

if TYPE_CHECKING:
    from server.camera import Camera
    from server.event_recorder import EventRecorder
    from server.motion_detector import MotionDetector
    from server.object_detector import ObjectDetector

logger = logging.getLogger(__name__)

MAX_READ_FAILURES = 50  # leituras seguidas sem frame (~5 s) antes de desistir
COLOR_PERIMETER = (255, 200, 0)
COLOR_INSIDE = (0, 0, 255)
COLOR_OUTSIDE = (0, 200, 0)
COLOR_MOTION = (0, 255, 255)
COLOR_IGNORED = (160, 160, 160)


def _put_text(
    img: np.ndarray, text: str, org: tuple[int, int], color: tuple[int, int, int], scale: float
) -> None:
    """Texto com contorno preto, legível sobre qualquer fundo."""
    if not text:
        return
    cv2.putText(img, text, org, cv2.FONT_HERSHEY_SIMPLEX, scale, (0, 0, 0), 4, cv2.LINE_AA)
    cv2.putText(img, text, org, cv2.FONT_HERSHEY_SIMPLEX, scale, color, 1, cv2.LINE_AA)


class Pipeline:
    def __init__(
        self,
        camera: "Camera | None" = None,
        motion_detector: "MotionDetector | None" = None,
        object_detector: "ObjectDetector | None" = None,
        event_recorder: "EventRecorder | None" = None,
        notify: Callable[[list[Path], str], None] | None = send_alert,
        on_event: Callable[[dict], None] | None = None,
        cooldown_seconds: float = NOTIFICATION_COOLDOWN_SECONDS,
    ) -> None:
        self._camera = camera
        self._motion = motion_detector
        self._objects = object_detector
        self._recorder = event_recorder
        self._notify = notify
        self._on_event = on_event
        self._cooldown = cooldown_seconds

        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._perimeter_dirty = threading.Event()
        self._error: str | None = None

        # Geometria do perímetro (só a thread do loop escreve).
        self._size: tuple[int, int] | None = None  # (largura, altura)
        self._polygon_px: np.ndarray | None = None
        self._mask: np.ndarray | None = None

        # Último frame publicado para a API.
        self._cond = threading.Condition()
        self._frame_id = 0
        self._frame_raw: np.ndarray | None = None
        self._frame_annotated: np.ndarray | None = None
        self._jpeg_cache: dict[tuple[bool, int], bytes] = {}

        self._last_event_ts = 0.0
        self._last_event_id: str | None = None

    # ------------------------------------------------------------------
    # Ciclo de vida
    # ------------------------------------------------------------------
    def start(self) -> None:
        """
        Abre a câmera, carrega o modelo, aquece o detector de movimento e
        inicia o loop. Falhas (câmera ausente, modelo faltando) levantam
        aqui, de forma síncrona, em vez de morrerem dentro da thread.
        """
        if self._thread is not None and self._thread.is_alive():
            return

        # Imports tardios: só quem realmente usa o hardware paga o custo.
        if self._camera is None:
            from server.camera import Camera
            self._camera = Camera()
        if self._motion is None:
            from server.motion_detector import MotionDetector
            self._motion = MotionDetector(threshold_area=MOTION_THRESHOLD_AREA)
        if self._objects is None:
            from server.object_detector import ObjectDetector
            self._objects = ObjectDetector(confidence_threshold=CONFIDENCE_THRESHOLD)
        if self._recorder is None:
            from server.event_recorder import EventRecorder
            self._recorder = EventRecorder()

        # Sem bot configurado, roda só local: avisa uma vez em vez de gerar
        # um traceback a cada evento.
        if self._notify is send_alert and not (TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID):
            logger.warning(
                "TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID vazios no .env: "
                "eventos serão salvos, mas não enviados ao Telegram."
            )
            self._notify = None

        self._camera.start()
        try:
            logger.info("Aquecendo o detector de movimento (%d frames)...", WARM_UP_FRAMES)
            frames = [self._camera.read_frame() for _ in range(WARM_UP_FRAMES)]
            frames = [f for f in frames if f is not None]
            if not frames:
                raise RuntimeError("A câmera abriu mas não entregou nenhum frame.")
            self._motion.warm_up(frames)
            self._ensure_geometry(frames[-1])
        except Exception:
            self._camera.stop()
            raise

        self._stop.clear()
        self._error = None
        self._thread = threading.Thread(target=self._run, name="pipeline", daemon=True)
        self._thread.start()
        logger.info("Pipeline iniciado.")

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None
        if self._camera is not None:
            self._camera.stop()
        with self._cond:
            self._cond.notify_all()

    def set_event_callback(self, callback: Callable[[dict], None] | None) -> None:
        """Define quem é avisado (ex.: Socket.IO) a cada invasão confirmada."""
        self._on_event = callback

    def reload_perimeter(self) -> None:
        """Pede para o loop reler o perímetro salvo (chamado após um POST)."""
        self._perimeter_dirty.set()

    # ------------------------------------------------------------------
    # Leitura pela API
    # ------------------------------------------------------------------
    def wait_for_frame(self, last_id: int, timeout: float = 2.0) -> int:
        """Bloqueia até existir um frame mais novo que last_id (ou timeout)."""
        with self._cond:
            self._cond.wait_for(
                lambda: self._frame_id != last_id or self._stop.is_set(), timeout=timeout
            )
            return self._frame_id

    def get_jpeg(self, annotated: bool = False) -> tuple[int, bytes | None]:
        """
        Retorna (id_do_frame, JPEG) do frame mais recente -- cru (para
        calibrar o perímetro no navegador) ou anotado (perímetro, caixas e
        status). O JPEG só é codificado quando alguém pede.
        """
        with self._cond:
            frame_id = self._frame_id
            frame = self._frame_annotated if annotated else self._frame_raw
            cached = self._jpeg_cache.get((annotated, frame_id))
        if frame is None:
            return frame_id, None
        if cached is not None:
            return frame_id, cached

        ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
        if not ok:
            return frame_id, None
        data = buf.tobytes()
        with self._cond:
            self._jpeg_cache = {k: v for k, v in self._jpeg_cache.items() if k[1] == frame_id}
            self._jpeg_cache[(annotated, frame_id)] = data
        return frame_id, data

    def status(self) -> dict:
        restante = max(0.0, self._cooldown - (time.time() - self._last_event_ts))
        return {
            "running": self._thread is not None and self._thread.is_alive(),
            "error": self._error,
            "frame_size": list(self._size) if self._size else None,
            "cooldown_remaining": round(restante, 1),
            "last_event": self._last_event_id,
        }

    # ------------------------------------------------------------------
    # Loop
    # ------------------------------------------------------------------
    def _ensure_geometry(self, frame: np.ndarray) -> None:
        """Recalcula polígono e máscara se o perímetro mudou ou o frame mudou de tamanho."""
        altura, largura = frame.shape[:2]
        if (
            self._perimeter_dirty.is_set()
            or self._size != (largura, altura)
            or self._polygon_px is None
        ):
            self._perimeter_dirty.clear()
            pontos = load_perimeter()
            self._size = (largura, altura)
            self._polygon_px = denormalize(pontos, largura, altura)
            self._mask = build_mask(self._polygon_px, largura, altura)
            logger.info("Perímetro aplicado (%d pontos, frame %dx%d).", len(pontos), largura, altura)

    def _run(self) -> None:
        falhas = 0
        try:
            while not self._stop.is_set():
                frame = self._camera.read_frame()
                if frame is None:
                    falhas += 1
                    if falhas >= MAX_READ_FAILURES:
                        raise RuntimeError("A câmera parou de entregar frames.")
                    time.sleep(0.1)
                    continue
                falhas = 0
                self._process(frame)
        except Exception as e:
            self._error = str(e)
            logger.exception("Pipeline interrompido por erro.")
        finally:
            logger.info("Loop do pipeline encerrado.")

    def _process(self, frame: np.ndarray) -> None:
        self._ensure_geometry(frame)

        movimento = self._motion.detect(frame, self._mask)

        pessoas: list[dict] = []
        animais: list[dict] = []
        if movimento:
            # Estágio 2 (caro): só roda quando o estágio 1 acusou movimento.
            # Animais também são pedidos, mas só para aparecerem no vídeo
            # como "ignorados" -- nunca disparam evento.
            deteccoes = self._objects.detect(frame, {"person"} | ANIMAL_CLASSES)
            pessoas = [d for d in deteccoes if d["label"] == "person"]
            animais = [d for d in deteccoes if d["label"] != "person"]
            for p in pessoas:
                p["inside"] = person_in_perimeter(p["box"], p["foot_point"], self._polygon_px)
                # Só para exibir no vídeo (calibrar MIN_OVERLAP_RATIO).
                p["overlap"] = box_overlap_ratio(p["box"], self._polygon_px)

        invasao = any(p["inside"] for p in pessoas)
        agora = time.time()
        em_cooldown = (agora - self._last_event_ts) < self._cooldown

        self._publish(
            frame, self._annotate(frame, movimento, pessoas, animais, em_cooldown, agora)
        )

        if invasao and not em_cooldown:
            self._handle_intrusion(frame, len(pessoas), agora)

    def _handle_intrusion(self, frame: np.ndarray, num_pessoas: int, agora: float) -> None:
        # O cooldown começa antes da captura: se ela falhar, não tentamos
        # de novo a cada frame.
        self._last_event_ts = agora
        logger.info("INVASÃO detectada (%d pessoa(s) no frame) -- capturando evento.", num_pessoas)

        try:
            caminhos = self._recorder.capture_event(self._camera, first_frame=frame)
        except Exception:
            logger.exception("Falha ao capturar o evento.")
            return
        if not caminhos:
            logger.warning("capture_event não salvou nenhuma imagem.")
            return

        event_id = caminhos[0].parent.name
        self._last_event_id = event_id
        legenda = f"Invasão detectada! {datetime.now():%d/%m/%Y %H:%M:%S}"
        logger.info("%d imagem(ns) salvas em %s.", len(caminhos), caminhos[0].parent)

        # Rede lenta não pode travar a leitura da câmera: envia em outra thread.
        if self._notify is not None:
            threading.Thread(
                target=self._notify_safe, args=(caminhos, legenda), name="notify", daemon=True
            ).start()

        if self._on_event is not None:
            try:
                self._on_event({
                    "id": event_id,
                    "mensagem": legenda,
                    "imagens": [f"/events/{event_id}/{c.name}" for c in caminhos],
                })
            except Exception:
                logger.exception("Falha ao avisar os clientes do evento.")

    def _notify_safe(self, caminhos: list[Path], legenda: str) -> None:
        try:
            self._notify(caminhos, legenda)
        except Exception:
            logger.exception("Falha ao enviar a notificação.")

    # ------------------------------------------------------------------
    # Desenho e publicação
    # ------------------------------------------------------------------
    def _annotate(
        self,
        frame: np.ndarray,
        movimento: bool,
        pessoas: list[dict],
        animais: list[dict],
        em_cooldown: bool,
        agora: float,
    ) -> np.ndarray:
        img = frame.copy()

        # Pinta de amarelo os pixels que o MOG2 considerou movimento (já
        # restritos ao perímetro) -- mostra o que realmente aciona o estágio 2.
        mask = getattr(self._motion, "last_mask", None)
        if mask is not None and mask.shape[:2] == img.shape[:2]:
            overlay = img.copy()
            overlay[mask > 0] = COLOR_MOTION
            cv2.addWeighted(overlay, 0.4, img, 0.6, 0, dst=img)

        cv2.polylines(img, [self._polygon_px], isClosed=True, color=COLOR_PERIMETER, thickness=2)

        for a in animais:
            x1, y1, x2, y2 = a["box"]
            cv2.rectangle(img, (x1, y1), (x2, y2), COLOR_IGNORED, 2)
            _put_text(img, f"{a['label']} {a['confidence']:.2f} (ignorado)",
                      (x1, max(y1 - 8, 15)), COLOR_IGNORED, 0.5)

        for p in pessoas:
            x1, y1, x2, y2 = p["box"]
            cor = COLOR_INSIDE if p["inside"] else COLOR_OUTSIDE
            cv2.rectangle(img, (x1, y1), (x2, y2), cor, 2)
            # Marca o ponto que o modo de decisão atual realmente testa.
            if DECISION_MODE == "foot":
                cv2.circle(img, p["foot_point"], 6, cor, -1)
            elif DECISION_MODE == "center":
                cv2.circle(img, ((x1 + x2) // 2, (y1 + y2) // 2), 6, cor, -1)
            texto = f"person {p['confidence']:.2f} overlap={p['overlap']:.2f}"
            _put_text(img, texto, (x1, max(y1 - 8, 15)), cor, 0.5)

        # Linha 1: estágio 1 (movimento). Linha 2: estágio 2 + decisão.
        # (Fonte Hershey não tem acentos -- textos em ASCII.)
        area = getattr(self._motion, "last_area", 0.0)
        minimo = getattr(self._motion, "threshold_area", 0)
        linha1 = f"[{DECISION_MODE}] " + ("MOVIMENTO" if movimento else "sem movimento")
        linha1 += f"  area={area:.0f}px (min {minimo})"
        if any(p["inside"] for p in pessoas):
            linha2 = "PESSOA DENTRO DO PERIMETRO"
        elif pessoas:
            linha2 = "pessoa fora do perimetro"
        elif movimento:
            linha2 = "movimento sem pessoa"
        else:
            linha2 = ""
        if em_cooldown:
            restante = self._cooldown - (agora - self._last_event_ts)
            linha2 += f"  (cooldown: {restante:.0f}s)"
        _put_text(img, linha1, (10, 25), (255, 255, 255), 0.6)
        _put_text(img, linha2.strip(), (10, 50), (255, 255, 255), 0.6)
        return img

    def _publish(self, raw: np.ndarray, annotated: np.ndarray) -> None:
        with self._cond:
            self._frame_raw = raw
            self._frame_annotated = annotated
            self._frame_id += 1
            self._cond.notify_all()
