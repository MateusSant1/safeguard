"""
Teste manual e interativo do motion_detector.py com a webcam real.

Abre a câmera, mostra o vídeo ao vivo numa janela e sinaliza na tela
quando o movimento foi detectado -- útil pra ver o resultado em tempo
real e calibrar o threshold_area (definido logo abaixo) pra sua câmera e
seu ambiente.

Controles (com a janela do vídeo em foco):
    q   - sair
    m   - alterna entre monitorar só o perímetro salvo e o frame inteiro

Uso (a partir da raiz do projeto, com o venv ativado):
    python -m server.test_motion
"""
import cv2

from server.camera import Camera
from server.motion_detector import MotionDetector
from server.perimeter import build_mask, denormalize, load_perimeter

WARM_UP_FRAMES = 30
THRESHOLD_AREA = 500  # ajuste este valor conforme o resultado na prática


def main() -> None:
    with Camera() as cam:
        largura, altura = cam.get_dimensions()
        print(f"Câmera aberta: {largura}x{altura}")

        detector = MotionDetector(threshold_area=THRESHOLD_AREA)

        print(f"Aquecendo o detector com {WARM_UP_FRAMES} frames -- não se mexa na frente da câmera...")
        frames_aquecimento = [cam.read_frame() for _ in range(WARM_UP_FRAMES)]
        detector.warm_up([f for f in frames_aquecimento if f is not None])

        print("Pronto! Mova-se na frente da câmera. 'q' sai, 'm' alterna perímetro/frame inteiro.")

        usar_perimetro = True

        while True:
            frame = cam.read_frame()
            if frame is None:
                continue

            mask = None
            polygon_px = None
            if usar_perimetro:
                pontos_norm = load_perimeter()
                polygon_px = denormalize(pontos_norm, largura, altura)
                mask = build_mask(polygon_px, largura, altura)

            movimento = detector.detect(frame, perimeter_mask=mask)

            exibicao = frame.copy()
            if polygon_px is not None:
                cv2.polylines(
                    exibicao, [polygon_px], isClosed=True, color=(255, 200, 0), thickness=2
                )

            cor = (0, 0, 255) if movimento else (0, 200, 0)
            texto = "MOVIMENTO DETECTADO" if movimento else "sem movimento"
            cv2.putText(exibicao, texto, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, cor, 2)

            modo_texto = "perimetro salvo" if usar_perimetro else "frame inteiro"
            cv2.putText(
                exibicao, f"modo: {modo_texto}  (m para alternar)",
                (10, altura - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1,
            )

            cv2.imshow("Safeguard - teste do motion_detector", exibicao)

            tecla = cv2.waitKey(1) & 0xFF
            if tecla == ord("q"):
                break
            elif tecla == ord("m"):
                usar_perimetro = not usar_perimetro

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
