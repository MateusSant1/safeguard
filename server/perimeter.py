"""
Define, persiste e testa o polígono do perímetro de vigilância.

Pontos são guardados NORMALIZADOS (fração de 0.0 a 1.0 da largura/altura
do frame de referência usado no momento do desenho). Isso é essencial
porque a resolução em que o usuário desenha o perímetro no navegador
(ex.: 640x480, resolução do /snapshot) pode ser diferente da resolução
usada na inferência (ex.: 320x240, para rodar mais rápido no Pi). Guardando
frações em vez de pixels, o mesmo perímetro salvo funciona corretamente em
qualquer resolução de frame que o pipeline decidir usar depois.
"""
import json
import logging

import cv2
import numpy as np

from server.config import DECISION_MODE, MIN_OVERLAP_RATIO, PERIMETER_FILE

logger = logging.getLogger(__name__)

# Perímetro "total": os 4 cantos do frame, em coordenadas normalizadas.
# Usado como padrão quando o usuário ainda não desenhou nada.
FULL_FRAME_PERIMETER: list[tuple[float, float]] = [
    (0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0),
]


def save_perimeter(normalized_points: list[tuple[float, float]]) -> None:
    """
    Salva o polígono (pontos normalizados 0.0-1.0) em disco.

    Levanta ValueError se os pontos não formarem um polígono válido ou se
    algum ponto estiver fora do intervalo [0.0, 1.0] — isso indicaria um
    bug no frontend (enviando pixels em vez de frações).
    """
    if len(normalized_points) < 3:
        raise ValueError("Um perímetro precisa de pelo menos 3 pontos.")

    for x, y in normalized_points:
        if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
            raise ValueError(
                f"Ponto ({x}, {y}) fora do intervalo esperado [0.0, 1.0]. "
                "Os pontos devem ser normalizados antes de chamar save_perimeter."
            )

    PERIMETER_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(PERIMETER_FILE, "w", encoding="utf-8") as f:
        json.dump({"pontos": normalized_points}, f)

    logger.info("Perímetro salvo com %d pontos em %s.", len(normalized_points), PERIMETER_FILE)


def load_perimeter() -> list[tuple[float, float]]:
    """
    Carrega o polígono salvo. Se não existir nenhum ainda (ou se o arquivo
    estiver corrompido/inválido), retorna o perímetro "total": os 4 cantos
    do frame — ou seja, por padrão o sistema monitora a imagem inteira até
    o usuário desenhar um perímetro parcial.
    """
    if not PERIMETER_FILE.exists():
        logger.info("Nenhum perímetro salvo ainda; usando o frame inteiro.")
        return list(FULL_FRAME_PERIMETER)

    try:
        with open(PERIMETER_FILE, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
        pontos = data["pontos"]
        if len(pontos) < 3:
            raise ValueError("menos de 3 pontos salvos")
        return [(float(x), float(y)) for x, y in pontos]
    except (json.JSONDecodeError, KeyError, ValueError, TypeError) as e:
        logger.warning(
            "Arquivo de perímetro inválido (%s); usando o frame inteiro.", e
        )
        return list(FULL_FRAME_PERIMETER)


def denormalize(
    normalized_points: list[tuple[float, float]], frame_width: int, frame_height: int
) -> np.ndarray:
    """
    Converte pontos normalizados (0.0-1.0) para pixels de um frame WxH
    específico. Retorna um array int32 no formato que cv2.pointPolygonTest
    e cv2.fillPoly esperam.
    """
    pixels = [
        (int(round(x * frame_width)), int(round(y * frame_height)))
        for x, y in normalized_points
    ]
    return np.array(pixels, dtype=np.int32)


def point_inside_perimeter(point: tuple[float, float], polygon_px: np.ndarray) -> bool:
    """
    Testa se um ponto (em pixels) está dentro do polígono (em pixels, já
    denormalizado). Pontos exatamente sobre a borda contam como "dentro".
    """
    contour = polygon_px.reshape((-1, 1, 2)).astype(np.float32)
    result = cv2.pointPolygonTest(contour, (float(point[0]), float(point[1])), False)
    return result >= 0


def build_mask(polygon_px: np.ndarray, frame_width: int, frame_height: int) -> np.ndarray:
    """
    Gera uma máscara binária (frame_height x frame_width, uint8) com 255
    dentro do polígono e 0 fora. Usada para restringir a detecção de
    movimento (estágio 1) apenas à área do perímetro.
    """
    mask = np.zeros((frame_height, frame_width), dtype=np.uint8)
    cv2.fillPoly(mask, [polygon_px], color=255)
    return mask


def box_overlap_ratio(box: tuple[int, int, int, int], polygon_px: np.ndarray) -> float:
    """
    Fração (0.0-1.0) da área da caixa (x1, y1, x2, y2) que cai dentro do
    polígono. Desenha o polígono num canvas do tamanho da caixa e conta os
    pixels preenchidos -- barato, porque a caixa é pequena.
    """
    x1, y1, x2, y2 = box
    w, h = x2 - x1, y2 - y1
    if w <= 0 or h <= 0:
        return 0.0
    canvas = np.zeros((h, w), dtype=np.uint8)
    shifted = (polygon_px - np.array([x1, y1], dtype=np.int32)).astype(np.int32)
    cv2.fillPoly(canvas, [shifted], color=1)
    return float(cv2.countNonZero(canvas)) / float(w * h)


def person_in_perimeter(
    box: tuple[int, int, int, int],
    foot_point: tuple[int, int],
    polygon_px: np.ndarray,
    mode: str = DECISION_MODE,
    min_overlap_ratio: float = MIN_OVERLAP_RATIO,
) -> bool:
    """
    Decide se uma pessoa detectada está dentro do perímetro.

    O modelo às vezes enquadra só a parte de cima do corpo; nesse caso o
    foot_point (base da caixa) fica na altura do peito e não representa onde
    a pessoa está. Por isso há três critérios, escolhidos em config.DECISION_MODE
    (ver config.py): "foot", "center" e "overlap".
    """
    if mode == "foot":
        return point_inside_perimeter(foot_point, polygon_px)
    if mode == "center":
        x1, y1, x2, y2 = box
        return point_inside_perimeter(((x1 + x2) / 2, (y1 + y2) / 2), polygon_px)
    if mode == "overlap":
        return box_overlap_ratio(box, polygon_px) >= min_overlap_ratio
    raise ValueError(f"DECISION_MODE inválido: {mode!r} (use foot, center ou overlap).")
