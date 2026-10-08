"""
Ponto de entrada do servidor. Cria o Flask + SocketIO, registra as rotas
da API e do streaming de vídeo, e inicia o pipeline
(motion detector -> object detector -> perímetro -> evento -> notificação)
numa thread própria (ver pipeline.py).

Rodar como MÓDULO, não como script solto, para os imports do pacote
`server` funcionarem em qualquer máquina do grupo:

    python -m server.app

Rotas:
    GET  /                  -> página do cliente (client/index.html)
    GET  /snapshot          -> um frame JPEG cru, para desenhar o perímetro
    GET  /video_feed        -> stream MJPEG com perímetro e caixas desenhados
    GET  /api/perimetro     -> perímetro salvo (pontos normalizados)
    POST /api/perimetro     -> salva um novo perímetro {"pontos": [[x, y], ...]}
    GET  /api/eventos       -> histórico de eventos (mais recentes primeiro)
    GET  /events/<id>/<arq> -> imagem de um evento
    GET  /api/status        -> estado do pipeline

Evento Socket.IO emitido a cada invasão confirmada: "intrusao".
"""
import logging
import re

from flask import Flask, Response, abort, jsonify, request, send_from_directory
from flask_socketio import SocketIO

from server.config import CLIENT_DIR, EVENTS_DIR, EVENTS_LIST_LIMIT, SERVER_HOST, SERVER_PORT
from server.perimeter import load_perimeter, save_perimeter
from server.pipeline import Pipeline

logger = logging.getLogger(__name__)

MJPEG_BOUNDARY = "frame"
EVENT_DIR_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}$")
IMAGE_PATTERN = re.compile(r"^frame_\d{2}\.jpg$")


def _parse_points(payload) -> list[tuple[float, float]]:
    """Valida o corpo do POST /api/perimetro; levanta ValueError se estiver mal formado."""
    if not isinstance(payload, dict) or "pontos" not in payload:
        raise ValueError('Corpo esperado: {"pontos": [[x, y], ...]}.')
    pontos = payload["pontos"]
    if not isinstance(pontos, list):
        raise ValueError('"pontos" deve ser uma lista.')

    resultado = []
    for ponto in pontos:
        if (
            not isinstance(ponto, (list, tuple))
            or len(ponto) != 2
            or any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in ponto)
        ):
            raise ValueError("Cada ponto deve ser um par numérico [x, y].")
        resultado.append((float(ponto[0]), float(ponto[1])))
    return resultado


def create_app(pipeline: Pipeline) -> tuple[Flask, SocketIO]:
    """
    Monta a aplicação em volta de um pipeline já criado. Não abre câmera nem
    carrega modelo -- isso é do pipeline.start(), chamado em main().
    """
    app = Flask(__name__, static_folder=str(CLIENT_DIR), static_url_path="")
    socketio = SocketIO(app)

    # O pipeline avisa os navegadores conectados a cada invasão.
    pipeline.set_event_callback(lambda evento: socketio.emit("intrusao", evento))

    @app.get("/")
    def index():
        return app.send_static_file("index.html")

    @app.get("/snapshot")
    def snapshot():
        _, jpeg = pipeline.get_jpeg(annotated=False)
        if jpeg is None:
            return jsonify(erro="Ainda não há frame da câmera."), 503
        return Response(jpeg, mimetype="image/jpeg", headers={"Cache-Control": "no-store"})

    @app.get("/video_feed")
    def video_feed():
        def generate():
            ultimo = -1
            while True:
                novo = pipeline.wait_for_frame(ultimo, timeout=2.0)
                if novo == ultimo:
                    if not pipeline.status()["running"]:
                        return
                    continue
                ultimo, jpeg = pipeline.get_jpeg(annotated=True)
                if jpeg is None:
                    continue
                yield (
                    f"--{MJPEG_BOUNDARY}\r\nContent-Type: image/jpeg\r\n"
                    f"Content-Length: {len(jpeg)}\r\n\r\n"
                ).encode() + jpeg + b"\r\n"

        return Response(
            generate(),
            mimetype=f"multipart/x-mixed-replace; boundary={MJPEG_BOUNDARY}",
            headers={"Cache-Control": "no-store"},
        )

    @app.get("/api/perimetro")
    def get_perimetro():
        return jsonify(pontos=[list(p) for p in load_perimeter()])

    @app.post("/api/perimetro")
    def post_perimetro():
        try:
            pontos = _parse_points(request.get_json(silent=True))
            save_perimeter(pontos)
        except ValueError as e:
            return jsonify(erro=str(e)), 400
        pipeline.reload_perimeter()
        return jsonify(pontos=[list(p) for p in pontos])

    @app.get("/api/eventos")
    def get_eventos():
        if not EVENTS_DIR.exists():
            return jsonify(eventos=[])
        pastas = sorted(
            (d for d in EVENTS_DIR.iterdir() if d.is_dir() and EVENT_DIR_PATTERN.match(d.name)),
            key=lambda d: d.name,
            reverse=True,
        )[:EVENTS_LIST_LIMIT]

        eventos = []
        for pasta in pastas:
            imagens = sorted(f.name for f in pasta.glob("frame_*.jpg"))
            data, hora = pasta.name.split("_")
            eventos.append({
                "id": pasta.name,
                "timestamp": f"{data}T{hora.replace('-', ':')}",
                "imagens": [f"/events/{pasta.name}/{nome}" for nome in imagens],
            })
        return jsonify(eventos=eventos)

    @app.get("/events/<event_id>/<filename>")
    def event_image(event_id: str, filename: str):
        # Só aceita os nomes que o EventRecorder gera -- nada de caminhos livres.
        if not EVENT_DIR_PATTERN.match(event_id) or not IMAGE_PATTERN.match(filename):
            abort(404)
        return send_from_directory(EVENTS_DIR / event_id, filename)

    @app.get("/api/status")
    def get_status():
        return jsonify(pipeline.status())

    return app, socketio


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )

    pipeline = Pipeline()
    pipeline.start()  # falhas de câmera/modelo aparecem aqui, antes de subir o servidor
    app, socketio = create_app(pipeline)
    try:
        # use_reloader=False: o reloader subiria um 2º processo e abriria a câmera duas vezes.
        socketio.run(
            app,
            host=SERVER_HOST,
            port=SERVER_PORT,
            use_reloader=False,
            allow_unsafe_werkzeug=True,
        )
    finally:
        pipeline.stop()


if __name__ == "__main__":
    main()
