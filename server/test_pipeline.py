"""
Teste manual e interativo do pipeline OPERACIONAL completo:

    motion_detector (Estágio 1, barato)
        -> só se detectar movimento ->
    object_detector (Estágio 2, caro)
        -> para cada pessoa detectada ->
    perimeter.point_inside_perimeter (decisão)
        -> se dentro ->
    event_recorder.capture_event (~5 imagens do evento)

A notificação por Telegram AINDA NÃO entra aqui -- no lugar dela, só
aparece um print no console. Isso deixa toda a lógica operacional
validável com a webcam antes de depender do bot do Telegram estar
configurado.

Um cooldown (NOTIFICATION_COOLDOWN_SECONDS, definido em config.py) evita
disparar um evento novo a cada frame enquanto a pessoa continua parada
dentro do perímetro.

Controles (com a janela do vídeo em foco):
    q   - sair

Uso (a partir da raiz do projeto, com o venv ativado):
    python -m server.test_pipeline
"""
import time

import cv2

from server.camera import Camera
from server.config import (
    CONFIDENCE_THRESHOLD,
    MOTION_THRESHOLD_AREA,
    NOTIFICATION_COOLDOWN_SECONDS,
    WARM_UP_FRAMES,
)
from server.event_recorder import EventRecorder
from server.motion_detector import MotionDetector
from server.object_detector import ObjectDetector
from server.perimeter import build_mask, denormalize, load_perimeter, person_in_perimeter


def main() -> None:
    with Camera() as cam:
        largura, altura = cam.get_dimensions()
        print(f"Câmera aberta: {largura}x{altura}")

        pontos_norm = load_perimeter()
        polygon_px = denormalize(pontos_norm, largura, altura)
        perimeter_mask = build_mask(polygon_px, largura, altura)

        motion_detector = MotionDetector(threshold_area=MOTION_THRESHOLD_AREA)
        object_detector = ObjectDetector(confidence_threshold=CONFIDENCE_THRESHOLD)
        event_recorder = EventRecorder()

        print(f"Aquecendo o motion detector com {WARM_UP_FRAMES} frames -- não se mexa...")
        frames_aquecimento = [cam.read_frame() for _ in range(WARM_UP_FRAMES)]
        motion_detector.warm_up([f for f in frames_aquecimento if f is not None])

        print("Pronto! Ande dentro/fora do perímetro para testar o pipeline completo. 'q' sai.")

        ultimo_evento = 0.0

        while True:
            frame = cam.read_frame()
            if frame is None:
                continue

            exibicao = frame.copy()
            cv2.polylines(exibicao, [polygon_px], isClosed=True, color=(255, 200, 0), thickness=2)

            movimento = motion_detector.detect(frame, perimeter_mask=perimeter_mask)

            invasao_confirmada = False
            if movimento:
                # Estágio 2 só roda quando o Estágio 1 já indicou movimento.
                pessoas = object_detector.detect_people(frame)
                for pessoa in pessoas:
                    x1, y1, x2, y2 = pessoa["box"]
                    dentro = person_in_perimeter(pessoa["box"], pessoa["foot_point"], polygon_px)
                    cor = (0, 0, 255) if dentro else (0, 200, 0)

                    cv2.rectangle(exibicao, (x1, y1), (x2, y2), cor, 2)
                    cv2.circle(exibicao, pessoa["foot_point"], 6, cor, -1)

                    if dentro:
                        invasao_confirmada = True

            agora = time.time()
            em_cooldown = (agora - ultimo_evento) < NOTIFICATION_COOLDOWN_SECONDS

            if invasao_confirmada and not em_cooldown:
                print(f"[{time.strftime('%H:%M:%S')}] INVASÃO DETECTADA -- capturando evento...")
                caminhos = event_recorder.capture_event(cam)
                pasta = caminhos[0].parent if caminhos else "???"
                print(f"  -> {len(caminhos)} imagens salvas em {pasta}")
                print("  -> (aqui entraria o envio para o Telegram, via notifier.py)")
                ultimo_evento = agora

            status = "MOVIMENTO" if movimento else "sem movimento"
            if em_cooldown:
                restante = NOTIFICATION_COOLDOWN_SECONDS - (agora - ultimo_evento)
                status += f"  (cooldown: {restante:.0f}s)"
            cv2.putText(exibicao, status, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

            cv2.imshow("Safeguard - pipeline completo", exibicao)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
