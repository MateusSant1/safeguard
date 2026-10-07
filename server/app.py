"""
Ponto de entrada do servidor. Cria o Flask + SocketIO, registra as rotas
da API e do streaming de vídeo, e inicia o loop principal do pipeline
(motion detector -> object detector -> perímetro -> evento -> notificação).

Rodar como MÓDULO, não como script solto, para os imports do pacote
`server` funcionarem em qualquer máquina do grupo:

    python -m server.app
"""
from flask import Flask
from flask_socketio import SocketIO

app = Flask(__name__)
socketio = SocketIO(app)


# TODO: rotas da API
#   GET  /snapshot          -> devolve um frame único (JPEG) para calibração
#   GET  /video_feed        -> stream MJPEG contínuo
#   GET  /api/perimetro     -> devolve o perímetro salvo (perimeter.load_perimeter())
#   POST /api/perimetro     -> salva um novo perímetro (perimeter.save_perimeter())
#   GET  /api/eventos       -> lista o histórico de eventos capturados

# TODO: loop principal (numa thread/processo separado da API):
#   1. camera.read_frame()
#   2. motion_detector.detect(frame, perimeter_mask)
#   3. se True: object_detector.detect_people(frame)
#   4. para cada pessoa: perimeter.point_inside_perimeter(foot_point, polygon_px)
#   5. se dentro: event_recorder.capture_event() + notifier.send_alert()
#      + emitir evento via socketio para o frontend
#   6. respeitar o cooldown entre notificações (NOTIFICATION_COOLDOWN_SECONDS)


if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000)
