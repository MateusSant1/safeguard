# Safeguard — Contexto completo do projeto

Exportado em 07/10/2026; seções 4 e 6 a 10 atualizadas em 08/10/2026. Este arquivo resume a conversa em que o projeto foi planejado e desenvolvido, de 02/09 a 08/10/2026: o que foi decidido, o que já funciona, o que não funciona, o que já deu errado e como foi resolvido. Serve para qualquer pessoa do grupo continuar o trabalho em outro chat sem precisar reconstruir esse histórico. O Apêndice A é um retrato do código em 07/10; o código atual está no repositório (branch `main`).

## Como usar este arquivo

- **Em um chat novo:** anexe este arquivo e escreva, por exemplo: *"Leia o CONTEXTO_SAFEGUARD.md e me ajude a continuar o projeto a partir do problema 1 da seção 8."* Para mexer no código, anexe também o `safeguard_repositorio.zip`.
- **Em um Projeto do Claude:** adicione este arquivo aos arquivos do projeto e cole o bloco da seção 1 nas instruções do projeto. Assim, todo chat aberto dentro dele já começa com o contexto.
- **No Claude Code:** o arquivo fica em `docs/CONTEXTO_SAFEGUARD.md` no repositório, e o `CLAUDE.md` da raiz já aponta para ele.
- **Mantenha atualizado:** ao terminar uma etapa, peça ao chat para atualizar as seções 7 a 10 e substitua este arquivo para o grupo.

---

## 1. Instruções para o assistente

Cole este bloco nas instruções do projeto ou no início de um chat novo:

```text
Você está ajudando o grupo Safeguard (disciplina Tópicos Especiais em Computação,
Universidade Tiradentes, Prof. Felipe dos Anjos, turma GP0029VNO09A, 2026.2) a
desenvolver um sistema cliente-servidor de vigilância de perímetro com visão
computacional. O contexto completo está no arquivo CONTEXTO_SAFEGUARD.md.

Regras de trabalho:
- Responda em português do Brasil.
- Antes de propor mudanças, leia as seções "Decisões tomadas" e "Armadilhas já
  resolvidas". Não reabra decisões já tomadas (por exemplo: sem sensor de
  presença, OpenCV 4.x, MobileNet-SSD) a menos que o grupo peça.
- O desenvolvimento é feito no Windows (PowerShell) com webcam USB; o servidor
  final é um Raspberry Pi 3. Ao passar um comando, diga em qual dos dois ele roda.
- Python com type hints; nomes de código em inglês; comentários e mensagens em
  português.
- Scripts do pacote server rodam a partir da raiz do projeto, como módulo:
  python -m server.<nome>.
- Nenhum módulo abre a câmera fora de server/camera.py. Segredos só no .env.
- Coordenadas do perímetro são sempre normalizadas (0.0 a 1.0).
- Antes de entregar código, teste o que for possível sem hardware (frames
  sintéticos, câmera e rede simuladas) e diga o que só pode ser confirmado com
  a webcam real.
- Entregue arquivos completos, prontos para substituir, e diga em qual pasta
  cada um vai.
```

---

## 2. O projeto em resumo

| | |
|---|---|
| **Nome** | Safeguard — sistema de vigilância de perímetro |
| **Disciplina** | Tópicos Especiais em Computação (Universidade Tiradentes), Prof. Felipe dos Anjos, turma GP0029VNO09A, semestre 2026.2 |
| **Grupo** | Mateus Henrique de Araújo Santos, Gustavo Rodrigues de Freitas, Luiz Gustavo Santana Santos, Bernardo Gonçalves do Carmo, Matheus Araújo Gois Costa, João Gabriel Costa (Pinto de Mendonça) |
| **Repositório** | https://github.com/MateusSant1/safeguard |
| **Servidor** | Raspberry Pi 3 Model B com Raspberry Pi OS, SSH configurado; webcam USB |
| **Desenvolvimento** | Windows (PowerShell) com webcam USB no índice 0 (640x480) |

**Objetivo.** O usuário desenha sobre a imagem da câmera a região que quer vigiar, que pode ser só uma parte da imagem ou ela inteira. Quando uma **pessoa** entra nessa região, o sistema grava cerca de 5 imagens e avisa o usuário pelo Telegram. Animais e outros objetos são ignorados.

**Divisão cliente-servidor.** O Raspberry Pi concentra a câmera, a visão computacional e a API. O cliente é uma página web simples, aberta no navegador de qualquer dispositivo da rede local, usada para ver a câmera e desenhar o perímetro. A disciplina avalia justamente essa arquitetura distribuída, com o Pi como servidor.

---

## 3. Arquitetura e contratos entre os módulos

### Pipeline em dois estágios

1. **Movimento** (`motion_detector.py`): é leve e roda em todos os frames. Usa subtração de fundo (MOG2, do OpenCV) só dentro de uma máscara com o formato do perímetro.
2. **Pessoas** (`object_detector.py`): é pesado e só roda quando o estágio 1 acusa movimento. Usa a rede MobileNet-SSD pelo `cv2.dnn` e mantém só a classe `person`.
3. **Decisão** (`perimeter.py`): para cada pessoa, testa se o "ponto dos pés" (meio da base da caixa detectada) está dentro do polígono.
4. **Evento** (`event_recorder.py`, depois `notifier.py`): grava ~5 imagens e, no futuro, envia ao Telegram. Um intervalo de espera (cooldown) de 60 s evita notificações repetidas.

O pipeline existe em dois estágios por causa do Raspberry Pi 3: a rede neural processa cerca de 1 imagem por segundo nele, então ela só pode rodar quando há algo se mexendo.

### Contratos (o que cada módulo recebe e devolve)

| Módulo | Interface |
|---|---|
| `config.py` | Lê o `.env` e expõe constantes: `CAMERA_INDEX`, `MODEL_PROTOTXT`, `MODEL_WEIGHTS`, `VOC_CLASSES` (21 classes do PASCAL VOC), `ANIMAL_CLASSES`, `PERIMETER_FILE`, `EVENTS_DIR`, `FRAMES_PER_EVENT = 5`, `NOTIFICATION_COOLDOWN_SECONDS = 60`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` |
| `camera.py` | `Camera(index)` com `start()`, `read_frame() -> ndarray BGR \| None`, `get_dimensions() -> (largura, altura)`, `stop()`; funciona como `with Camera() as cam:` |
| `perimeter.py` | `save_perimeter(pontos)`, `load_perimeter()`, `denormalize(pontos, largura, altura) -> ndarray int32`, `point_inside_perimeter(ponto, polygon_px) -> bool`, `build_mask(polygon_px, largura, altura) -> ndarray uint8`, `FULL_FRAME_PERIMETER` |
| `motion_detector.py` | `MotionDetector(threshold_area=500)`, `warm_up(frames)` (uns 30 frames da cena parada), `detect(frame, perimeter_mask=None) -> bool` |
| `object_detector.py` | `ObjectDetector(confidence_threshold=0.5)` (usamos **0.26**); `detect_people(frame)` devolve uma lista de `{"box": (x1, y1, x2, y2), "confidence": float, "foot_point": ((x1 + x2) // 2, y2)}` |
| `event_recorder.py` | `EventRecorder(frames_per_event=5, interval_seconds=0.4)`; `capture_event(camera)` salva em `server/events/AAAA-MM-DD_HH-MM-SS/frame_00.jpg` e devolve a lista de caminhos |
| `notifier.py` | (planejado) `send_alert(caminhos, legenda)`, chamando a Bot API do Telegram com `requests` |
| `app.py` | (planejado) Flask + Flask-SocketIO na porta 5000: `GET /snapshot`, `GET /video_feed` (MJPEG), `GET/POST /api/perimetro`, `GET /api/eventos`, `GET /api/status`, evento WebSocket `alerta_invasao`; o loop do pipeline roda numa thread separada |

**Formato do perímetro** (`server/data/perimeter.json`):

```json
{"pontos": [[0.25, 0.25], [0.75, 0.25], [0.75, 0.75], [0.25, 0.75]]}
```

Os pontos são frações (0.0 a 1.0) da largura e da altura da imagem, para que o perímetro desenhado no navegador funcione em qualquer resolução usada no processamento. Se o arquivo não existir, estiver vazio ou for inválido, o sistema vigia a imagem inteira. A leitura usa `utf-8-sig` para aceitar arquivos salvos com BOM pelo Windows.

---

## 4. Tecnologias

| Camada | Tecnologia | Situação |
|---|---|---|
| Linguagem | Python | Em uso |
| Visão computacional | OpenCV **4.x** (`opencv-python` no Windows; `python3-opencv` do apt no Pi) | Em uso |
| Movimento | `cv2.createBackgroundSubtractorMOG2` | Em uso |
| Pessoas | MobileNet-SSD (formato Caffe, dataset PASCAL VOC) via `cv2.dnn` | Em uso |
| Perímetro | `cv2.pointPolygonTest`, `cv2.fillPoly` | Em uso |
| Números | NumPy | Em uso |
| Configuração | `python-dotenv` | Em uso |
| Servidor web | Flask + Flask-SocketIO, vídeo em MJPEG | Em uso |
| Notificação | Bot API do Telegram com `requests` | Em uso |
| Cliente | HTML, CSS e JavaScript puro, `<canvas>` para o perímetro, Socket.IO no navegador | Em uso |

---

## 5. Decisões tomadas

| Decisão | Motivo |
|---|---|
| **Sem sensor de presença (PIR).** O gatilho de movimento é feito por software, na própria imagem. | O grupo não tem o sensor, e a câmera já resolve. A ideia está descartada de vez; ela foi removida também do relatório. |
| Pipeline em dois estágios (movimento → pessoas) | A rede neural é lenta demais no Pi 3 para rodar em todos os frames. |
| Raspberry Pi 3 | É o hardware disponível. O Pi 4 e o Pi 2 chegaram a ser considerados. |
| MobileNet-SSD pelo `cv2.dnn`, e não YOLO | Não exige PyTorch, é leve no Pi e já separa pessoa de animal. Depois de calibrar o limiar, o grupo decidiu seguir com ele. YOLO exportado para ONNX ficou como melhoria futura. |
| OpenCV fixado em 4.x | O OpenCV 5.0 removeu o suporte a modelos Caffe. |
| Limiar de confiança 0.26 | Com 0.5 o modelo perdia muitas detecções; 0.26 funcionou bem nos testes. O grupo pretende testar outros valores. |
| Perímetro em coordenadas normalizadas | A resolução de desenho no navegador pode ser diferente da resolução de processamento. |
| Interface web simples (Flask + canvas em JavaScript puro) | Basta mostrar a câmera e desenhar o perímetro; o Konva.js fica como opção se o desenho ficar trabalhoso. |
| Telegram com `requests` direto, sem biblioteca de bot | O sistema só envia mensagens. O `pyTelegramBotAPI` só entra se quiserem comandos pelo Telegram. |
| Telegram por último | O grupo decidiu fechar primeiro a lógica operacional. |
| Sem pasta `tests/` | Testes automatizados ficaram fora do escopo. Os testes manuais com câmera ficam em `server/test_*.py`. |
| 5 imagens por evento, cooldown de 60 s | Evita várias notificações para a mesma invasão. |

---

## 6. Histórico da conversa

- **02/09** — Ideia inicial: Pi como servidor, câmera, sensor PIR, perímetro na imagem, alerta no Telegram, distinguir pessoa de animal. Arquitetura proposta e relatório da disciplina preenchido nas seções 3 a 8.1, com diagrama.
- **10/09** — Sensor PIR descartado; movimento passa a ser detectado por software. Criados um `CLAUDE.md` e um tutorial de uso do Claude Code pelo grupo.
- **16/09** — Escopo revisado e pesquisa de bibliotecas. O Pi 2 foi avaliado e o Pi 3 foi definido. Ambiente preparado no Windows; estrutura de pastas definida (sem `tests/`) e repositório criado. Implementados e testados com a webcam real: `camera`, `perimeter`, `motion_detector` e `object_detector`. Nesse caminho apareceram e foram resolvidos: ativação da `.venv` no PowerShell, imports do pacote `server`, `config.py` não enviado, BOM no `perimeter.json`, OpenCV 5 sem Caffe, download do modelo com 404, prototxt incompatível com os pesos, limiar 0.26. Implementados `event_recorder` e `test_pipeline`.
- **Até 23/09** — Os testes mostraram que perímetro e detecção de pessoas não funcionam juntos e que o `event_recorder` não chega a gravar no pipeline real.
- **23/09** — Apresentação de andamento preenchida com o status real e os desafios. Pacote de referência com o código entregue.
- **30/09** — Criado o `ESTADO_DO_PROJETO.md` para o grupo.
- **05/10** — Relatório preenchido da seção 8.2 à 13; sensor de presença removido de todo o relatório; referências reduzidas às documentações das bibliotecas.
- **07/10** — Este arquivo. Descoberto que os arquivos de código no GitHub estavam vazios. Criados os scripts de instalação no Raspberry Pi, e todo o código foi enviado para a branch `pipeline-raspberry`.
- **08/10** — Implementados `pipeline.py`, `app.py`, `notifier.py` e o cliente web, e validados com a webcam real e o bot real. Limiares movidos para o `config.py`. Problemas 1 e 2 resolvidos: a decisão passou a usar a sobreposição caixa × polígono (`overlap` ≥ 0.15), e o `event_recorder` grava normalmente quando a condição de disparo é atendida. As fotos do evento passaram a ter 1 s de intervalo, gravadas sem travar o loop. O Telegram dava `ReadTimeout` por causa do IPv6 quebrado na rede do PC; o `notifier` passou a forçar IPv4.

---

## 7. Estado atual

| Módulo | Situação | Como foi verificado |
|---|---|---|
| `camera.py` | Funcional | Webcam real |
| `perimeter.py` | Funcional isoladamente | Webcam real, perímetro de teste desenhado (`test_integration`) |
| `motion_detector.py` | Funcional, inclusive restrito ao perímetro | Webcam real (`test_motion`); perto da borda do perímetro é preciso um movimento maior para disparar, o que é esperado |
| `object_detector.py` | Detecta pessoas com limiar 0.26 | Webcam real (`test_object`) |
| Perímetro + detecção de pessoas | Funcional no modo `overlap` (0.15) | Webcam real, perímetro desenhado no navegador; overlap na borda entre 0.26 e 0.37 |
| `event_recorder.py` | Funcional: 5 imagens, 1 s entre elas, sem travar o loop | Webcam real |
| `pipeline.py`, `app.py` | Funcionais | Webcam real, pelo navegador (`python -m server.app`) |
| `notifier.py` | Funcional | Bot real (`python -m server.test_telegram`) |
| `client/` | Funcional: vídeo ao vivo, editor do perímetro, histórico, alerta em tempo real | Navegador no PC de desenvolvimento |

**Repositório no GitHub:** até 07/10/2026 a `main` tinha 7 commits com todos os arquivos de `server/` e `client/` **vazios (0 bytes)**, inclusive um `server/data/perimeter.json` vazio. Em 07/10 todo o código desta conversa foi enviado para a branch **`pipeline-raspberry`**. Em 08/10 a branch foi mesclada na `main` (PR #1); clone com `git clone https://github.com/MateusSant1/safeguard.git`.

**Ambiente Windows (máquina do Mateus):** `.venv` com OpenCV 4.x (reinstalado abaixo da versão 5), modelo baixado em `server/models/`, webcam no índice 0 (640x480) e um perímetro de teste salvo.

**Raspberry Pi 3:** sistema e SSH configurados; o código ainda não foi instalado. Os scripts para isso estão prontos (`scripts/setup_raspberry_pi.sh`).

**Documentos da disciplina:** o relatório está na versão 4, com as seções 1 a 13 preenchidas. A apresentação de andamento é de 23/09.

---

## 8. Problemas em aberto

### Resolvidos em 08/10

- **Problema 1 — decisão do perímetro.** Nos testes, com a pessoa perto da webcam, as pernas nem aparecem na imagem: a caixa pega só o tronco e o `foot_point` não representa a posição da pessoa. Adotada a correção (a): a pessoa está dentro quando pelo menos 15% da caixa cai dentro do polígono (`DECISION_MODE=overlap`, `MIN_OVERLAP_RATIO=0.15`). Os modos `foot` e `center` continuam disponíveis pelo `.env`. Atenção ao testar: se a pessoa cruzar a linha do perímetro, a caixa sempre terá overlap suficiente.
- **Problema 2 — `event_recorder`.** O gravador não tinha defeito; ele não era acionado por causa do problema 1.
- **Animais.** Testado com um animal real na cena: aparece em cinza "ignorado" e não dispara evento.

### Pendentes

- **Calibração de longe.** O limiar 0.15 foi validado com a pessoa perto da webcam; falta testar com a pessoa distante, de corpo inteiro.
- **Desempenho no Pi 3.** Ainda não medido.

### Limitações conhecidas (aceitas)

O MobileNet-SSD é de 2017 e foi treinado num conjunto de dados pequeno. Ele perde a detecção em movimentos bruscos (por causa do desfoque), depende de a pessoa estar de frente e bem enquadrada, e não rastreia entre frames: cada imagem é analisada do zero. Isso é aceitável no escopo da disciplina.

---

## 9. Armadilhas já resolvidas

Se algum destes erros aparecer de novo, a causa e a solução já são conhecidas:

| Sintoma | Causa | Solução |
|---|---|---|
| `.venv\Scripts\activate : Não foi possível carregar o módulo` | Sintaxe do PowerShell | `.\.venv\Scripts\Activate.ps1`; se bloquear, `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |
| `ModuleNotFoundError: No module named 'cv2'` | `.venv` não ativada ou bibliotecas não instaladas nela | Ativar a `.venv` e `pip install -r requirements.txt` |
| `No module named 'server'` | Script rodado como arquivo | Rodar da raiz com `python -m server.<script>` |
| `cannot import name 'CAMERA_INDEX' from 'server.config'` | `config.py` era só o esqueleto | Usar o `config.py` completo |
| "Arquivo de perímetro inválido (Expecting value...)" | `perimeter.json` vazio (veio vazio do GitHub) | Apagar o arquivo; sem ele, o sistema vigia a imagem inteira |
| "Arquivo de perímetro inválido (Unexpected UTF-8 BOM)" | `Out-File` do PowerShell grava com BOM | `perimeter.py` lê com `utf-8-sig`; para gravar sem BOM: `[System.IO.File]::WriteAllText(...)` |
| 404 ao baixar o `.caffemodel` | O repositório chuanqi305 não tem mais o arquivo | Baixar do PINTO0309/MobileNet-SSD-RealSense |
| `module 'cv2.dnn' has no attribute 'readNetFromCaffe'` | `pip` instalou o OpenCV 5.0, que removeu o suporte a Caffe | Windows: `pip install "opencv-python<5"`; Pi: OpenCV do apt |
| `blobs.size() >= 2` no `net.forward()` | Prototxt e caffemodel de fontes diferentes | Baixar os dois da mesma fonte (PINTO0309) |
| Poucas detecções, só com o rosto visível | Limiar 0.5 alto demais para esse modelo | Limiar 0.26 |
| Perímetro "não discerne": pessoa sempre dentro | Pessoa perto da câmera cruzando a linha do perímetro; a caixa sempre tem overlap ≥ 0.15 | Testar com a pessoa inteira de um lado da linha; conferir o `overlap` mostrado no vídeo |
| `MOVIMENTO` aparece mesmo com a pessoa fora do perímetro | É só o estágio 1 (MOG2): corpo, sombra e ajuste automático de brilho da webcam | Esperado; evento exige uma caixa `person` dentro |
| `ERRO: Falha de rede ao chamar o Telegram (ReadTimeout)` | IPv6 configurado na rede, mas sem saída; o `requests` tentava o IPv6 primeiro | `notifier.py` força IPv4 (`TELEGRAM_FORCE_IPV4=1`, padrão) |

---

## 10. Próximos passos

| # | Tarefa |
|---|---|
| 1 | Instalar no Pi com `scripts/setup_raspberry_pi.sh` e rodar `python -m server.app` lá, medindo o desempenho |
| 2 | Testar a calibração do overlap com a pessoa distante |
| 3 | Teste completo no Pi; prints e vídeo para o relatório (seções 9 e 13) |

---

## 11. Arquivos produzidos durante a conversa

Quem tiver estes arquivos deve compartilhá-los no grupo:

| Arquivo | Conteúdo |
|---|---|
| `safeguard_repositorio.zip` | Código atual + documentação + scripts (mesmo conteúdo da branch `pipeline-raspberry`) |
| `CONTEXTO_SAFEGUARD.md` | Este arquivo |
| `INSTALACAO_RASPBERRY_PI.md` e `setup_raspberry_pi.sh` | Instalação no Pi, manual e automática |
| `ESTADO_DO_PROJETO.md` | Estado do projeto, tecnologias e estrutura, para o grupo |
| `Safeguard_Relatorio_Projeto_v4.docx` | Relatório da disciplina (versão mais recente) |
| `TÓPICOS_ESPECIAIS_EM_COMPUTAÇÃO_atualizado.pptx` | Apresentação de andamento de 23/09 |

---

## 12. Comandos de referência

### Windows (desenvolvimento), na raiz do projeto

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python scripts/verificar_ambiente.py

python server/list_cameras.py          # índice da webcam
python -m server.test_integration      # câmera + perímetro (gera test_perimetro.jpg)
python -m server.test_motion           # movimento ao vivo ('m' alterna perímetro/imagem inteira, 'q' sai)
python -m server.test_object           # pessoas ao vivo
python -m server.test_pipeline         # pipeline completo, sem Telegram
```

Modelo, se faltar em `server/models/`:

```powershell
$base = "https://github.com/PINTO0309/MobileNet-SSD-RealSense/raw/refs/heads/master/caffemodel/MobileNetSSD"
Invoke-WebRequest -Uri "$base/MobileNetSSD_deploy.prototxt"   -OutFile "server\models\MobileNetSSD_deploy.prototxt"
Invoke-WebRequest -Uri "$base/MobileNetSSD_deploy.caffemodel" -OutFile "server\models\MobileNetSSD_deploy.caffemodel"
```

Perímetro de teste, sem BOM:

```powershell
[System.IO.File]::WriteAllText("server\data\perimeter.json", '{"pontos": [[0.25, 0.25], [0.75, 0.25], [0.75, 0.75], [0.25, 0.75]]}')
```

### Raspberry Pi

Ver `INSTALACAO_RASPBERRY_PI.md`. Em resumo:

```bash
git clone https://github.com/MateusSant1/safeguard.git
cd safeguard
bash scripts/setup_raspberry_pi.sh
```

---

## Apêndice A — Código em 07/10/2026

> **Desatualizado:** este apêndice é o retrato de 07/10, antes do `pipeline.py`, do `app.py`, do `notifier.py` e do cliente serem implementados. O código atual está no repositório (branch `main`); consulte-o lá.

Versão de cada arquivo em 07/10, igual à do `safeguard_repositorio.zip`. Ela inclui as duas correções feitas no computador do Mateus: leitura com `utf-8-sig` no `perimeter.py` e limiar 0.26 nos testes. Se a cópia local de alguém tiver mudanças posteriores, a cópia local vale.

O `server/__init__.py` existe e é vazio (marca `server/` como pacote).

### `server/config.py` — Configuração central

```python
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
```

### `server/camera.py` — Câmera

```python
"""
Responsabilidade única: abrir a webcam e entregar frames.

Nenhum outro módulo deve chamar cv2.VideoCapture diretamente — tudo passa
por aqui, para que trocar de câmera (webcam USB -> câmera do Pi, por
exemplo) signifique mexer em um arquivo só.
"""
import logging

import cv2
import numpy as np

from server.config import CAMERA_INDEX

logger = logging.getLogger(__name__)


class Camera:
    def __init__(self, index: int = CAMERA_INDEX):
        self._index = index
        self._cap: cv2.VideoCapture | None = None

    def start(self) -> None:
        """Abre a captura de vídeo. Levanta RuntimeError se falhar."""
        self._cap = cv2.VideoCapture(self._index)
        if not self._cap.isOpened():
            self._cap = None
            raise RuntimeError(
                f"Não foi possível abrir a câmera de índice {self._index}. "
                "Verifique se ela está conectada (ls /dev/video* no Linux) "
                "e se CAMERA_INDEX está correto."
            )
        logger.info("Câmera %s aberta com sucesso.", self._index)

    def read_frame(self) -> np.ndarray | None:
        """Retorna o frame mais recente (numpy array BGR) ou None se falhar."""
        if self._cap is None:
            raise RuntimeError("A câmera não foi iniciada. Chame start() primeiro.")

        ok, frame = self._cap.read()
        if not ok:
            logger.warning("Falha ao ler frame da câmera %s.", self._index)
            return None
        return frame

    def get_dimensions(self) -> tuple[int, int]:
        """Retorna (largura, altura) reportadas pela câmera."""
        if self._cap is None:
            raise RuntimeError("A câmera não foi iniciada. Chame start() primeiro.")

        width = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        return width, height

    def stop(self) -> None:
        """Libera a câmera. Seguro chamar mesmo se ela nunca foi aberta."""
        if self._cap is not None:
            self._cap.release()
            self._cap = None
            logger.info("Câmera %s liberada.", self._index)

    # Permite usar "with Camera() as cam:" para garantir que stop() é
    # chamado mesmo se der exceção no meio do uso.
    def __enter__(self) -> "Camera":
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.stop()
```

### `server/perimeter.py` — Perímetro

```python
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

from server.config import PERIMETER_FILE

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
```

### `server/motion_detector.py` — Estágio 1: movimento

```python
"""
Estágio 1 do pipeline: gatilho de movimento barato.

Roda continuamente sobre os frames da câmera (idealmente em baixa
resolução) e só avisa "tem movimento" quando a área de pixels alterados,
DENTRO da máscara do perímetro, ultrapassa um limiar. Não sabe nada sobre
pessoas/animais -- isso é trabalho do object_detector.py no estágio
seguinte, que só deve ser chamado quando detect() retornar True.

Detalhe importante de operação: o subtrator de fundo (MOG2) precisa de
alguns frames para "aprender" como é o fundo parado da cena. Nos
primeiros frames depois de start()/reset(), é normal e esperado que
detect() acuse movimento mesmo sem ninguém na cena -- use warm_up() para
consumir esses frames iniciais antes de começar a agir sobre o resultado.
"""
import cv2
import numpy as np


class MotionDetector:
    def __init__(
        self,
        threshold_area: int = 500,
        history: int = 500,
        var_threshold: float = 16.0,
    ):
        """
        threshold_area: área mínima (em pixels) de uma região alterada
            para contar como "movimento real" -- filtra ruído da câmera
            (pequenas variações de luz, compressão, etc.) que a subtração
            de fundo sozinha não elimina.
        history / var_threshold: repassados direto para o
            cv2.createBackgroundSubtractorMOG2 -- history é quantos frames
            ele usa pra formar o modelo de fundo; var_threshold controla a
            sensibilidade (menor = mais sensível a pequenas mudanças).
        """
        self._subtractor = cv2.createBackgroundSubtractorMOG2(
            history=history, varThreshold=var_threshold, detectShadows=False
        )
        self._threshold_area = threshold_area
        # Kernel usado para limpar ruído da máscara de movimento antes de
        # procurar contornos (remove pontinhos isolados de 1-2 pixels).
        self._clean_kernel = np.ones((3, 3), np.uint8)

    def warm_up(self, frames) -> None:
        """
        Alimenta o subtrator com frames iniciais sem verificar movimento,
        para ele aprender o fundo da cena antes de qualquer detecção real
        valer a pena. Chame isso com uns 20-30 frames ao iniciar o
        servidor (ou depois de qualquer mudança grande na cena).
        """
        for frame in frames:
            self._subtractor.apply(frame)

    def detect(self, frame: np.ndarray, perimeter_mask: np.ndarray | None = None) -> bool:
        """
        Retorna True se uma região de movimento com área >= threshold_area
        foi encontrada dentro da máscara do perímetro (ou no frame inteiro,
        se perimeter_mask for None).
        """
        fg_mask = self._subtractor.apply(frame)

        if perimeter_mask is not None:
            fg_mask = cv2.bitwise_and(fg_mask, perimeter_mask)

        # Remove ruído isolado antes de medir área -- sem isso, poeira de
        # compressão de vídeo já basta pra disparar falso positivo.
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, self._clean_kernel)

        contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        maior_area = max((cv2.contourArea(c) for c in contours), default=0)

        return maior_area >= self._threshold_area
```

### `server/object_detector.py` — Estágio 2: pessoas

```python
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
```

### `server/event_recorder.py` — Gravação de eventos

```python
"""
Quando uma invasão é confirmada (pessoa dentro do perímetro), captura uma
sequência de frames e salva em disco -- essas imagens são o que vai
anexado na notificação do Telegram (implementada depois, em notifier.py).
"""
import time
from datetime import datetime
from pathlib import Path

import cv2

from server.config import EVENTS_DIR, FRAMES_PER_EVENT


class EventRecorder:
    def __init__(self, frames_per_event: int = FRAMES_PER_EVENT, interval_seconds: float = 0.4):
        """
        interval_seconds: pausa entre cada frame capturado dentro de um
        mesmo evento -- existe pra que as ~5 imagens mostrem a cena
        evoluindo ao longo de ~2 segundos, em vez de serem 5 cópias quase
        idênticas do mesmo instante.
        """
        self._frames_per_event = frames_per_event
        self._interval_seconds = interval_seconds

    def capture_event(self, camera) -> list[Path]:
        """
        Captura frames_per_event frames em sequência e salva em
        EVENTS_DIR/<timestamp>/frame_00.jpg, frame_01.jpg, ...

        Recebe o objeto `camera` (já aberto) em vez de abrir uma câmera
        própria -- assim usa o mesmo frame stream que o resto do
        pipeline, sem disputar o dispositivo com outra captura.

        Retorna a lista de caminhos das imagens salvas (pode vir mais
        curta que frames_per_event se algum frame falhar na leitura).
        """
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        event_dir = EVENTS_DIR / timestamp
        event_dir.mkdir(parents=True, exist_ok=True)

        caminhos: list[Path] = []
        for i in range(self._frames_per_event):
            frame = camera.read_frame()
            if frame is not None:
                caminho = event_dir / f"frame_{i:02d}.jpg"
                cv2.imwrite(str(caminho), frame)
                caminhos.append(caminho)

            is_last = i == self._frames_per_event - 1
            if not is_last:
                time.sleep(self._interval_seconds)

        return caminhos
```

### `server/test_pipeline.py` — Teste manual do pipeline completo

```python
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
from server.config import NOTIFICATION_COOLDOWN_SECONDS
from server.event_recorder import EventRecorder
from server.motion_detector import MotionDetector
from server.object_detector import ObjectDetector
from server.perimeter import build_mask, denormalize, load_perimeter, point_inside_perimeter

WARM_UP_FRAMES = 30
MOTION_THRESHOLD_AREA = 500
CONFIDENCE_THRESHOLD = 0.26  # calibrado nos testes anteriores -- ajuste se precisar


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
                    dentro = point_inside_perimeter(pessoa["foot_point"], polygon_px)
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
```

### `server/test_object.py` — Teste manual da detecção de pessoas

```python
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
from server.object_detector import ObjectDetector
from server.perimeter import build_mask, denormalize, load_perimeter, point_inside_perimeter

CONFIDENCE_THRESHOLD = 0.26


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
                    point_inside_perimeter(pessoa["foot_point"], polygon_px)
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
```

### `server/test_motion.py` — Teste manual do movimento

```python
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
```

### `server/test_integration.py` — Teste manual câmera + perímetro

```python
"""
Teste de integração manual: usa a classe Camera (camera.py) junto com as
funções de perimeter.py, captura um frame REAL da sua webcam, desenha um
perímetro de exemplo por cima e salva a imagem para conferência visual.

Isso confirma, tudo de uma vez, que:
  - a classe Camera abre a sua webcam de verdade e entrega frames;
  - a conversão de coordenadas normalizadas -> pixels (denormalize) bate
    certinho com as dimensões reais do frame da sua câmera;
  - point_inside_perimeter reconhece corretamente um ponto de teste
    dentro e outro fora do perímetro desenhado.

Uso:
    python server/test_integration.py
"""
import cv2

from server.camera import Camera
from server.perimeter import denormalize, point_inside_perimeter

# Perímetro de exemplo: um retângulo cobrindo a região central do frame.
# Em produção, isso viria do server/data/perimeter.json (desenhado pelo
# usuário no navegador) via perimeter.load_perimeter().
PERIMETRO_EXEMPLO = [(0.25, 0.25), (0.75, 0.25), (0.75, 0.75), (0.25, 0.75)]


def main() -> None:
    with Camera() as cam:
        largura, altura = cam.get_dimensions()
        print(f"Câmera aberta: {largura}x{altura}")

        frame = cam.read_frame()
        if frame is None:
            print("ERRO: não foi possível capturar um frame.")
            return

    polygon_px = denormalize(PERIMETRO_EXEMPLO, largura, altura)

    # Desenha o perímetro por cima do frame, em verde.
    frame_com_perimetro = frame.copy()
    cv2.polylines(
        frame_com_perimetro, [polygon_px], isClosed=True, color=(0, 255, 0), thickness=3
    )

    # Testa dois pontos: o centro do frame (deve estar DENTRO do
    # retângulo de exemplo) e o canto superior esquerdo (deve estar FORA).
    centro = (largura // 2, altura // 2)
    canto = (5, 5)

    dentro_centro = point_inside_perimeter(centro, polygon_px)
    dentro_canto = point_inside_perimeter(canto, polygon_px)

    cor_centro = (0, 255, 0) if dentro_centro else (0, 0, 255)
    cor_canto = (0, 255, 0) if dentro_canto else (0, 0, 255)
    cv2.circle(frame_com_perimetro, centro, 8, cor_centro, -1)
    cv2.circle(frame_com_perimetro, canto, 8, cor_canto, -1)

    saida = "test_perimetro.jpg"
    cv2.imwrite(saida, frame_com_perimetro)

    print(f"Centro do frame {centro} está dentro do perímetro? {dentro_centro} (esperado: True)")
    print(f"Canto do frame {canto} está dentro do perímetro? {dentro_canto} (esperado: False)")
    print(f"Imagem salva em '{saida}' -- abra e confira visualmente o retângulo verde.")


if __name__ == "__main__":
    main()
```

### `server/list_cameras.py` — Diagnóstico: índices de câmera

```python
"""
Lista quais índices de câmera funcionam no seu computador. No Windows é
comum ter mais de um dispositivo de vídeo registrado (câmeras virtuais de
Zoom, Teams, OBS etc.), então nem sempre o índice 0 é a sua webcam física.

Uso:
    python server/list_cameras.py
"""
import cv2

MAX_INDEX_TO_TRY = 5


def main() -> None:
    encontrados = []

    for index in range(MAX_INDEX_TO_TRY + 1):
        cap = cv2.VideoCapture(index)
        if not cap.isOpened():
            cap.release()
            continue

        ok, frame = cap.read()
        if ok and frame is not None:
            height, width = frame.shape[:2]
            filename = f"camera_{index}.jpg"
            cv2.imwrite(filename, frame)
            print(f"[OK] Índice {index}: {width}x{height} -- frame salvo em '{filename}'")
            encontrados.append(index)
        else:
            print(f"[--] Índice {index}: abriu, mas não retornou frame")

        cap.release()

    print()
    if not encontrados:
        print(
            "Nenhuma câmera respondeu. Verifique se ela está conectada e "
            "se nenhum outro programa (Zoom, Teams, OBS...) está usando-a."
        )
    else:
        print(f"Índices que funcionaram: {encontrados}")
        print(
            "Abra os arquivos camera_<indice>.jpg gerados nesta pasta para "
            "ver qual imagem é a da sua webcam de verdade."
        )


if __name__ == "__main__":
    main()
```

### `server/test_camera.py` — Diagnóstico: câmera abre

```python
"""
Script de sanidade do ambiente: confirma que o OpenCV consegue abrir a
câmera e capturar frames antes de qualquer lógica de visão computacional
entrar em cena. Rode isto primeiro, tanto no notebook quanto no Pi.

Uso:
    python server/test_camera.py
"""
import os
import sys
import time

import cv2

CAMERA_INDEX = int(os.getenv("CAMERA_INDEX", "0"))


def main() -> None:
    print(f"Tentando abrir a câmera de índice {CAMERA_INDEX}...")
    cap = cv2.VideoCapture(CAMERA_INDEX)

    if not cap.isOpened():
        print("ERRO: não foi possível abrir a câmera. Verifique:")
        print("  - Se a webcam está conectada (ls /dev/video* no Linux)")
        print("  - Se CAMERA_INDEX está correto (tente 0, 1, 2...)")
        sys.exit(1)

    ok, frame = cap.read()
    if not ok:
        print("ERRO: a câmera abriu, mas não retornou nenhum frame.")
        sys.exit(1)

    height, width = frame.shape[:2]
    print(f"OK! Frame capturado com sucesso: {width}x{height} pixels.")

    out_path = "test_frame.jpg"
    cv2.imwrite(out_path, frame)
    print(f"Frame salvo em '{out_path}' para conferência visual.")

    cap.release()


if __name__ == "__main__":
    main()
```

### `server/app.py` — Servidor Flask (esqueleto)

```python
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
```

### `server/notifier.py` — Telegram (esqueleto)

```python
"""
Envia a notificação de invasão para o Telegram, usando a Bot API
diretamente via `requests` (sem wrapper -- este bot só envia, não recebe
comandos).
"""
from pathlib import Path

import requests

from server.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID


def send_alert(image_paths: list[Path], caption: str = "Invasão detectada!") -> None:
    """
    Envia a mensagem + imagens do evento para o chat configurado.
    Levanta exceção se TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID não estiverem
    configurados -- não falhar silenciosamente aqui, é melhor aparecer
    no log do servidor.
    """
    # TODO:
    #   url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    #   para cada imagem (ou usar sendMediaGroup para mandar as ~5 juntas),
    #   requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "caption": caption},
    #                 files={"photo": open(caminho, "rb")})
    raise NotImplementedError
```

### `client/index.html` — Cliente: página (esqueleto)

```html
<!doctype html>
<html lang="pt-br">
<head>
  <meta charset="utf-8" />
  <title>Safeguard - Vigilância de Perímetro</title>
  <link rel="stylesheet" href="style.css" />
</head>
<body>
  <h1>Safeguard</h1>

  <section id="perimetro-section">
    <h2>Configurar perímetro</h2>
    <!--
      TODO: <img id="snapshot" src="/snapshot"> como fundo,
      <canvas id="perimetro-canvas"> por cima, do MESMO tamanho da imagem,
      para o usuário clicar os vértices do polígono.
    -->
    <canvas id="perimetro-canvas"></canvas>
    <button id="salvar-perimetro">Salvar perímetro</button>
    <button id="perimetro-total">Monitorar imagem inteira</button>
  </section>

  <section id="stream-section">
    <h2>Câmera ao vivo</h2>
    <!-- TODO: <img src="/video_feed"> para o stream MJPEG -->
  </section>

  <section id="eventos-section">
    <h2>Histórico de eventos</h2>
    <ul id="lista-eventos"><!-- TODO: preenchido via events.js --></ul>
  </section>

  <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.2/socket.io.min.js"></script>
  <script src="perimeter.js"></script>
  <script src="events.js"></script>
</body>
</html>
```

### `client/perimeter.js` — Cliente: desenho do perímetro (esqueleto)

```javascript
/**
 * Desenho e edição do polígono do perímetro sobre um <canvas>.
 *
 * Fluxo:
 *   1. Carrega a imagem de referência (/snapshot) e ajusta o canvas
 *      para o mesmo tamanho dela.
 *   2. Cada clique no canvas adiciona um vértice (x, y em pixels do
 *      canvas) à lista de pontos e redesenha o polígono.
 *   3. Ao clicar "Salvar perímetro", NORMALIZA os pontos (divide x pela
 *      largura do canvas, y pela altura) antes de enviar via
 *      POST /api/perimetro -- ver perimeter.py no servidor para o porquê.
 */

// TODO: const canvas = document.getElementById("perimetro-canvas");
// TODO: let pontos = [];
// TODO: canvas.addEventListener("click", (evento) => { ... adiciona ponto, redesenha ... });
// TODO: document.getElementById("salvar-perimetro").addEventListener("click", async () => {
//         const normalizados = pontos.map(([x, y]) => [x / canvas.width, y / canvas.height]);
//         await fetch("/api/perimetro", { method: "POST", ... });
//       });
```

### `client/events.js` — Cliente: histórico (esqueleto)

```javascript
/**
 * Recebe e exibe o histórico de eventos de invasão em tempo real,
 * via WebSocket (Socket.IO), além de carregar o histórico já existente
 * ao abrir a página (GET /api/eventos).
 */

// TODO: const socket = io();
// TODO: socket.on("alerta_invasao", (evento) => { ... adiciona na lista ... });
// TODO: fetch("/api/eventos").then(...) ao carregar a página
```

### `client/style.css` — Cliente: estilo (esqueleto)

```css
/* TODO: estilizar. Manter simples -- este é um painel interno, não uma
   vitrine. Prioridade: o canvas do perímetro ficar exatamente alinhado
   com a imagem por baixo dele. */

body {
  font-family: system-ui, sans-serif;
  margin: 2rem;
}
```

### `requirements.txt` — Dependências do computador de desenvolvimento

```text
# Dependências do COMPUTADOR DE DESENVOLVIMENTO (Windows/Linux/macOS).
# No Raspberry Pi use requirements-pi.txt (o OpenCV e o NumPy vêm do apt).
#
#   pip install -r requirements.txt

# Servidor web e notificações
flask>=3.0,<4
flask-socketio>=5.3,<6
python-dotenv>=1.0
requests>=2.31

# Visão computacional
# O OpenCV 5.0 removeu o suporte a modelos Caffe (cv2.dnn.readNetFromCaffe),
# que é o formato do MobileNet-SSD usado em object_detector.py. Por isso a
# versão fica abaixo de 5. Usamos opencv-python (com janela), porque os
# scripts de teste mostram o vídeo com cv2.imshow.
opencv-python>=4.9,<5
numpy>=1.26
```

### `requirements-pi.txt` — Dependências pip do Raspberry Pi

```text
# Dependências Python do RASPBERRY PI, instaladas com pip dentro do .venv.
#
# O OpenCV e o NumPy NÃO entram aqui: no Pi eles vêm do apt
# (python3-opencv e python3-numpy), já compilados para ARM e na versão 4.x.
# O .venv é criado com --system-site-packages para enxergar esses pacotes.
# Não instale opencv-python, opencv-python-headless nem numpy pelo pip no Pi.
#
#   pip install -r requirements-pi.txt

flask>=3.0,<4
flask-socketio>=5.3,<6
python-dotenv>=1.0
requests>=2.31
```

### `.env.example` — Modelo do .env

```bash
# Copie este arquivo para ".env" e preencha com os valores reais.
# NUNCA commite o arquivo ".env" (ele já está no .gitignore).

TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

# Índice da webcam (0 = primeira câmera do sistema)
CAMERA_INDEX=0
```
