"""
Teste manual e interativo do object_detector.py com a webcam real.

Abre a câmera, roda o MobileNet-SSD em cada frame e desenha uma caixa
verde em volta de cada pessoa detectada (com a confiança da detecção),
além de um ponto na posição usada como "pés" -- é esse ponto que depois
vai ser testado contra o perímetro. Também desenha o perímetro salvo (ou
o frame inteiro, se nenhum tiver sido salvo ainda), pra já visualizar os
dois estágios juntos.

Como o MobileNet-SSD é mais pesado que o motion_detector, é normal a
janela atualizar num ritmo mais lento -- não precisa se assustar se não
ficar tão fluido quanto o teste de movimento.

Controles (com a janela do vídeo em foco):
    q   - sair
    m   - alterna entre monitorar o perímetro salvo e o frame inteiro

Uso (a partir da raiz do projeto, com o venv ativado):
    python -m server.test_object
"""
import cv2

from server.camera import Camera
from server.config import CONFIDENCE_THRESHOLD
from server.object_detector import ObjectDetector
from server.perimeter import build_mask, denormalize, load_perimeter, person_in_perimeter


def main() -> None:
    with Camera() as cam:
        largura, altura = cam.get_dimensions()
        print(f"Câmera aberta: {largura}x{altura}")

        detector = ObjectDetector(confidence_threshold=CONFIDENCE_THRESHOLD)
        print("Modelo carregado. Fique na frente da câmera para testar. 'q' sai, 'm' alterna perímetro/frame inteiro.")

        usar_perimetro = True

        while True:
            frame = cam.read_frame()
            if frame is None:
                continue

            pontos_norm = load_perimeter() if usar_perimetro else None
            polygon_px = denormalize(pontos_norm, largura, altura) if usar_perimetro else None

            pessoas = detector.detect_people(frame)

            exibicao = frame.copy()
            if polygon_px is not None:
                cv2.polylines(
                    exibicao, [polygon_px], isClosed=True, color=(255, 200, 0), thickness=2
                )

            for pessoa in pessoas:
                x1, y1, x2, y2 = pessoa["box"]
                dentro = (
                    person_in_perimeter(pessoa["box"], pessoa["foot_point"], polygon_px)
                    if polygon_px is not None
                    else True
                )
                cor = (0, 0, 255) if dentro else (0, 200, 0)

                cv2.rectangle(exibicao, (x1, y1), (x2, y2), cor, 2)
                cv2.circle(exibicao, pessoa["foot_point"], 6, cor, -1)
                label = f"person {pessoa['confidence']:.2f}"
                cv2.putText(
                    exibicao, label, (x1, max(20, y1 - 8)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, cor, 2,
                )

            status = f"{len(pessoas)} pessoa(s) detectada(s)"
            cv2.putText(exibicao, status, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

            modo_texto = "perimetro salvo" if usar_perimetro else "frame inteiro"
            cv2.putText(
                exibicao, f"modo: {modo_texto}  (m para alternar)",
                (10, altura - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1,
            )

            cv2.imshow("Safeguard - teste do object_detector", exibicao)

            tecla = cv2.waitKey(1) & 0xFF
            if tecla == ord("q"):
                break
            elif tecla == ord("m"):
                usar_perimetro = not usar_perimetro

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
