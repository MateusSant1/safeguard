"""
Estágio 2 do pipeline: detecção e classificação (caro).

Só deve ser chamado quando o MotionDetector já indicou movimento -- nunca
rodar isto em todo frame continuamente, especialmente no Raspberry Pi 3.
"""
import cv2
import numpy as np

from server.config import MODEL_PROTOTXT, MODEL_WEIGHTS, VOC_CLASSES

# Parâmetros esperados pelo MobileNet-SSD treinado no VOC0712 (valores
# padrão desse modelo específico, não são "mágicos" -- vêm da forma como
# ele foi treinado).
INPUT_SIZE = (300, 300)
SCALE_FACTOR = 0.007843  # 1 / 127.5
MEAN = 127.5


class ObjectDetector:
    def __init__(self, confidence_threshold: float = 0.5):
        self._net = cv2.dnn.readNetFromCaffe(str(MODEL_PROTOTXT), str(MODEL_WEIGHTS))
        self._confidence_threshold = confidence_threshold

    def detect_people(self, frame: np.ndarray) -> list[dict]:
        """
        Roda a rede sobre o frame e retorna uma lista de detecções da
        classe "person", cada uma como:
            {"box": (x1, y1, x2, y2), "confidence": float, "foot_point": (x, y)}

        Detecções de qualquer outra classe (incluindo animais) são
        descartadas aqui mesmo e nunca chegam a virar um resultado -- é
        assim que o sistema "sabe" ignorar bichos: o chamador só vê
        pessoas, nunca precisa filtrar nada de novo.
        """
        frame_height, frame_width = frame.shape[:2]

        blob = cv2.dnn.blobFromImage(
            frame, SCALE_FACTOR, INPUT_SIZE, MEAN, swapRB=False, crop=False
        )
        self._net.setInput(blob)
        raw_detections = self._net.forward()

        pessoas = []
        # raw_detections tem shape (1, 1, N, 7); cada linha é:
        #   [batch_id, class_id, confidence, x1, y1, x2, y2]
        # com x/y normalizados entre 0.0 e 1.0 (fração do frame de entrada).
        num_detections = raw_detections.shape[2]
        for i in range(num_detections):
            confidence = float(raw_detections[0, 0, i, 2])
            if confidence < self._confidence_threshold:
                continue

            class_id = int(raw_detections[0, 0, i, 1])
            if class_id < 0 or class_id >= len(VOC_CLASSES):
                continue

            if VOC_CLASSES[class_id] != "person":
                continue

            x1 = int(raw_detections[0, 0, i, 3] * frame_width)
            y1 = int(raw_detections[0, 0, i, 4] * frame_height)
            x2 = int(raw_detections[0, 0, i, 5] * frame_width)
            y2 = int(raw_detections[0, 0, i, 6] * frame_height)

            # Detecções perto da borda podem sair levemente fora dos
            # limites do frame por arredondamento -- protege contra isso.
            x1, x2 = max(0, x1), min(frame_width - 1, x2)
            y1, y2 = max(0, y1), min(frame_height - 1, y2)

            # Ponto dos "pés": meio da largura, base da caixa. É esse
            # ponto que perimeter.point_inside_perimeter testa, não o
            # centro geométrico da caixa -- fica mais fiel a onde a
            # pessoa está pisando na cena.
            foot_point = ((x1 + x2) // 2, y2)

            pessoas.append({
                "box": (x1, y1, x2, y2),
                "confidence": confidence,
                "foot_point": foot_point,
            })

        return pessoas
