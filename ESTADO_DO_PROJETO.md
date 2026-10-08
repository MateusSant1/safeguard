# Safeguard — Estado do Projeto

Documento de referência do time para o projeto da disciplina Tópicos Especiais em Computação (Prof. Felipe dos Anjos). Ele descreve o que já existe, o que falta, quais tecnologias usamos e como o código está organizado. Atualize a seção de estado sempre que um módulo mudar de situação.

**Última atualização:** 08/10/2026. O estado dos módulos é o dos últimos testes registrados com webcam real.

Documentos relacionados: `docs/CONTEXTO_SAFEGUARD.md` (histórico e decisões, para continuar o projeto em outros chats) e `docs/INSTALACAO_RASPBERRY_PI.md` (instalação no Pi).

---

## 1. Visão geral

O Safeguard é um sistema cliente-servidor de vigilância de perímetro. Uma câmera observa uma área, o usuário desenha sobre a imagem a região que quer vigiar (que pode ser só uma parte da imagem ou ela inteira), e o sistema avisa pelo Telegram quando uma **pessoa** entra nessa região. Animais e outros objetos são ignorados.

O servidor roda em um Raspberry Pi 3, que concentra a câmera, o processamento de visão computacional e a API. O cliente é uma página web simples, acessada pelo navegador de qualquer dispositivo na mesma rede, usada para ver a câmera e desenhar o perímetro.

O sistema não usa sensores físicos além da câmera: o gatilho de movimento é feito inteiramente em software, a partir da própria imagem.

---

## 2. Arquitetura

O processamento é dividido em dois estágios para caber no poder de processamento do Raspberry Pi 3. O primeiro estágio é leve e roda o tempo todo; o segundo é pesado e só roda quando o primeiro detecta algo.

```mermaid
flowchart LR
    CAM[Webcam] --> MOV[Estágio 1<br/>Detecção de movimento<br/>MOG2, restrita ao perímetro]
    MOV -- houve movimento --> DET[Estágio 2<br/>Detecção de pessoas<br/>MobileNet-SSD]
    DET -- pessoa detectada --> PER{Caixa da pessoa<br/>dentro do perímetro?<br/>overlap ≥ 15%}
    PER -- sim --> REC[Grava 5 imagens<br/>do evento, 1 s entre elas]
    REC --> TG[Notificação<br/>Telegram]
    CLI[Cliente web] -. desenha e salva o perímetro .-> JSON[(perimeter.json)]
    JSON -.-> MOV
    JSON -.-> PER
```

**Estágio 1 — movimento.** A subtração de fundo (MOG2, do OpenCV) compara cada frame com um modelo da cena parada. A comparação é aplicada apenas dentro de uma máscara com o formato do perímetro, então movimento fora da área vigiada é ignorado desde o início. Regiões muito pequenas são descartadas como ruído.

**Estágio 2 — pessoas.** Quando há movimento, o frame passa por uma rede neural pré-treinada (MobileNet-SSD) que localiza objetos e os classifica. Só as detecções da classe "pessoa" acima de um limiar de confiança seguem adiante.

**Decisão.** Para cada pessoa, o sistema calcula que fração da caixa detectada cai dentro do polígono (modo `overlap`) e considera a pessoa dentro quando essa fração é de pelo menos 15%. O critério original, que testava só o ponto central da base da caixa (os "pés"), falhava quando o modelo enquadrava apenas o tronco; ele continua disponível com `DECISION_MODE=foot`, assim como o centro da caixa (`DECISION_MODE=center`).

**Evento.** Se estiver dentro, o sistema grava 5 imagens, com 1 segundo entre elas (a primeira é o próprio frame da detecção), e as envia pelo Telegram como um álbum. As imagens são gravadas ao longo dos frames seguintes do loop, então o vídeo e a detecção não param durante a gravação. Um intervalo de espera (cooldown) de 60 segundos impede que a mesma invasão gere várias notificações seguidas.

**Servidor e cliente.** O `pipeline.py` roda esse loop em uma thread e é o único que lê a câmera; o `app.py` (Flask + Flask-SocketIO) serve o cliente web, o vídeo ao vivo com as anotações e a API do perímetro e dos eventos, e avisa os navegadores conectados a cada invasão.

**Perímetro.** Os pontos do polígono são salvos em `server/data/perimeter.json` em coordenadas normalizadas, ou seja, como frações de 0.0 a 1.0 da largura e da altura da imagem. Isso permite que o perímetro desenhado em uma resolução (no navegador) funcione corretamente em outra (na inferência). Se o arquivo não existir ou estiver inválido, o sistema vigia a imagem inteira.

---

## 3. Tecnologias

| Camada | Tecnologia | Situação |
|---|---|---|
| Linguagem | Python 3.11 / 3.12 | Em uso |
| Visão computacional | OpenCV **4.x** (`opencv-python` pelo pip no computador de desenvolvimento; `python3-opencv` pelo apt no Pi) | Em uso |
| Detecção de movimento | `cv2.createBackgroundSubtractorMOG2` | Em uso |
| Detecção de pessoas | MobileNet-SSD (formato Caffe, 21 classes do dataset VOC) via `cv2.dnn` | Em uso |
| Geometria do perímetro | `cv2.pointPolygonTest`, `cv2.fillPoly` | Em uso |
| Cálculo numérico | NumPy | Em uso |
| Configuração | `python-dotenv` (variáveis em `.env`) | Em uso |
| Servidor web / API | Flask + Flask-SocketIO | Em uso |
| Streaming de vídeo | MJPEG via Flask | Em uso |
| Notificação | Bot API do Telegram, chamada com `requests` | Em uso |
| Cliente | HTML, CSS e JavaScript puro, com `<canvas>` para desenhar o perímetro | Em uso |
| Tempo real no cliente | Socket.IO (cliente JavaScript, via CDN; sem internet, o cliente consulta a API periodicamente) | Em uso |
| Hardware do servidor | Raspberry Pi 3 com Raspberry Pi OS | Configurado, ainda sem o código instalado |
| Câmera | Webcam USB | Em uso |
| Versionamento | Git + GitHub (`MateusSant1/safeguard`) | Em uso |

Sobre a versão do OpenCV: o OpenCV 5.0 removeu o suporte a modelos Caffe, que é o formato do MobileNet-SSD que usamos. Por isso o `requirements.txt` fixa a versão abaixo de 5. Instalar o OpenCV sem essa restrição faz o `object_detector.py` falhar com o erro `module 'cv2.dnn' has no attribute 'readNetFromCaffe'`.

---

## 4. Estado atual

| Módulo | Situação | Como foi verificado |
|---|---|---|
| `camera.py` | Funcional | Webcam real (`test_integration.py`) |
| `perimeter.py` | Funcional isoladamente | Webcam real com perímetro de teste desenhado (`test_integration.py`) |
| `motion_detector.py` | Funcional | Webcam real, com e sem máscara do perímetro (`test_motion.py`) |
| `object_detector.py` | Detecta pessoas com limiar 0.26 | Webcam real (`test_object.py`) |
| Perímetro + detecção de pessoas | Funcional no modo `overlap` (limiar 0.15) | Webcam real, perímetro desenhado no navegador; overlap na borda entre 0.26 e 0.37 |
| `event_recorder.py` | Funcional: 5 imagens, 1 s entre elas, sem travar o loop | Webcam real (`python -m server.app`) |
| `pipeline.py` | Funcional | Webcam real |
| `app.py` | Funcional | Webcam real, pelo navegador |
| `notifier.py` | Funcional | Bot real (`test_telegram.py`) |
| `client/` | Funcional: vídeo ao vivo, editor do perímetro, histórico e alerta em tempo real | Navegador no PC de desenvolvimento |
| Animais ignorados | Funcional: aparecem em cinza "ignorado" e não disparam evento | Webcam real, com animal na cena |
| Raspberry Pi 3 | **Ainda não testado** | — |

### Problemas conhecidos

**1. Calibração só de perto.** O limiar de overlap (0.15) foi validado com a pessoa perto da webcam, ocupando boa parte da imagem. Falta testar com a pessoa mais distante, de corpo inteiro, que é a situação real de vigilância. O vídeo ao vivo mostra o `overlap` de cada pessoa para ajudar nessa calibração (`MIN_OVERLAP_RATIO` no `.env`).

**2. IPv6 quebrado no PC de desenvolvimento.** O `requests` tentava o IPv6 do `api.telegram.org` primeiro e terminava em `ReadTimeout`. O `notifier.py` agora usa só IPv4 (`TELEGRAM_FORCE_IPV4=1`, o padrão).

**3. Limitações do modelo.** O MobileNet-SSD é de 2017 e foi treinado em um conjunto de dados pequeno. Ele perde a detecção em movimentos bruscos (por causa do desfoque) e depende bastante de a pessoa estar de frente e bem enquadrada. O detector também não faz rastreamento: cada frame é analisado do zero. Isso é aceitável para o escopo do projeto, e a troca por um modelo mais moderno (YOLO exportado para ONNX) fica registrada como possível melhoria.

---

## 5. Estrutura de pastas

```
safeguard/
├── CLAUDE.md               # contexto do projeto para o Claude Code
├── ESTADO_DO_PROJETO.md    # este documento
├── README.md
├── requirements.txt        # dependências do computador de desenvolvimento (OpenCV < 5)
├── requirements-pi.txt     # dependências pip do Raspberry Pi (OpenCV/NumPy vêm do apt)
├── .env.example            # modelo das variáveis de ambiente
├── .gitignore
├── .gitattributes
│
├── docs/
│   ├── CONTEXTO_SAFEGUARD.md       # contexto completo para novos chats
│   └── INSTALACAO_RASPBERRY_PI.md  # instalação no Pi, passo a passo
├── scripts/
│   ├── setup_raspberry_pi.sh       # instala tudo no Pi
│   └── verificar_ambiente.py       # confere OpenCV, modelo e bibliotecas
│
├── server/                 # roda no Raspberry Pi
│   ├── __init__.py
│   ├── config.py           # lê o .env e centraliza caminhos e constantes
│   ├── camera.py           # único ponto de acesso à webcam
│   ├── perimeter.py        # salva, carrega e testa o polígono do perímetro
│   ├── motion_detector.py  # estágio 1: movimento (MOG2)
│   ├── object_detector.py  # estágio 2: pessoas (MobileNet-SSD)
│   ├── event_recorder.py   # grava as ~5 imagens de um evento
│   ├── notifier.py         # envio ao Telegram
│   ├── app.py              # servidor Flask e rotas da API
│   ├── pipeline.py         # loop principal em thread (movimento → pessoas → evento)
│   │
│   ├── list_cameras.py     # diagnóstico: descobre o índice da webcam
│   ├── test_camera.py      # diagnóstico: confirma que a câmera abre
│   ├── test_integration.py # teste manual: câmera + perímetro
│   ├── test_motion.py      # teste manual ao vivo: movimento
│   ├── test_object.py      # teste manual ao vivo: detecção de pessoas
│   ├── test_pipeline.py    # teste manual ao vivo: pipeline completo sem Telegram
│   ├── test_telegram.py    # teste do Telegram sem câmera; descobre o chat_id
│   │
│   ├── models/             # MobileNetSSD_deploy.prototxt e .caffemodel (~22 MB)
│   ├── data/               # perimeter.json
│   └── events/             # imagens das invasões (ignorado pelo Git)
│
└── client/                 # interface web, servida pelo app.py em http://<servidor>:5000
    ├── index.html          # vídeo ao vivo + editor do perímetro + histórico
    ├── style.css
    ├── perimeter.js        # desenho do polígono e envio dos pontos normalizados
    └── events.js           # estado do pipeline, histórico e alerta em tempo real
```

Nenhum módulo além de `camera.py` deve abrir a câmera diretamente, para que trocar a webcam pela câmera do Raspberry Pi exija mudança em um arquivo só.

Até 07/10/2026, todos os arquivos de código da `main` no GitHub estavam **vazios (0 bytes)**, inclusive um `server/data/perimeter.json` vazio, que é o que gerava o aviso "Arquivo de perímetro inválido". Em 07/10 o código foi enviado para a branch `pipeline-raspberry`, mesclada na **`main`** em 08/10 (PR #1). Clone com `git clone https://github.com/MateusSant1/safeguard.git`.

---

## 6. Como rodar

### Preparação (Windows)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python scripts/verificar_ambiente.py
```

Se o PowerShell bloquear a ativação do ambiente virtual, rode uma vez `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

### Modelo de detecção

Os dois arquivos precisam vir da **mesma fonte**. Arquivos de repositórios diferentes são incompatíveis entre si e causam o erro `blobs.size() >= 2`.

```powershell
$base = "https://github.com/PINTO0309/MobileNet-SSD-RealSense/raw/refs/heads/master/caffemodel/MobileNetSSD"
Invoke-WebRequest -Uri "$base/MobileNetSSD_deploy.prototxt"   -OutFile "server\models\MobileNetSSD_deploy.prototxt"
Invoke-WebRequest -Uri "$base/MobileNetSSD_deploy.caffemodel" -OutFile "server\models\MobileNetSSD_deploy.caffemodel"
```

O `.caffemodel` deve ter cerca de 22 MB.

### Sistema completo

```powershell
python -m server.app
```

Abra **http://localhost:5000** (ou `http://<IP do computador>:5000` em outro dispositivo da mesma rede). Fique fora do enquadramento ao iniciar: nos primeiros 30 frames o detector de movimento aprende o fundo da cena.

- **Monitoramento ao vivo:** amarelo = movimento dentro do perímetro; caixa vermelha = pessoa dentro; verde = pessoa fora; cinza = animal (ignorado). Cada pessoa mostra a confiança e o `overlap`.
- **Perímetro:** clique para adicionar vértices, arraste para mover, botão direito remove; "Salvar perímetro" aplica na hora, sem reiniciar.
- **Histórico:** eventos com miniaturas; um aviso vermelho aparece a cada invasão.

Sem `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID` no `.env`, os eventos são só salvos (um aviso aparece no log ao iniciar).

### Telegram

```powershell
python -m server.test_telegram
```

Sem token, explica como criar o bot no @BotFather; com token e sem chat_id, lista os chats que falaram com o bot (para copiar o `TELEGRAM_CHAT_ID`); com os dois, envia as imagens do evento mais recente.

### Testes manuais

Todos os scripts são executados **da raiz do projeto** e **como módulo** (com `-m` e ponto no lugar da barra). Rodar como arquivo (`python server/test_motion.py`) quebra os imports do pacote `server`.

```powershell
python server/list_cameras.py          # descobrir o índice da webcam
python -m server.test_integration      # câmera + perímetro, gera test_perimetro.jpg
python -m server.test_motion           # movimento ao vivo ('m' alterna modo, 'q' sai)
python -m server.test_object           # pessoas ao vivo
python -m server.test_pipeline         # pipeline completo, sem Telegram
```

Para criar um perímetro de teste sem a interface web, gere o JSON pelo .NET, que não grava o BOM que o `Out-File` do PowerShell adiciona:

```powershell
[System.IO.File]::WriteAllText("server\data\perimeter.json", '{"pontos": [[0.25, 0.25], [0.75, 0.25], [0.75, 0.75], [0.25, 0.75]]}')
```

---

## 7. Configuração

As variáveis de ambiente ficam no arquivo `.env` (copiado de `.env.example` e nunca enviado ao Git):

| Variável | Uso |
|---|---|
| `CAMERA_INDEX` | Índice da webcam (padrão 0) |
| `TELEGRAM_BOT_TOKEN` | Token do bot, gerado pelo @BotFather |
| `TELEGRAM_CHAT_ID` | Chat que recebe as notificações |

Os parâmetros ajustáveis do pipeline ficam todos no `config.py`, com valor padrão que pode ser trocado pelo `.env` (ver `.env.example`):

| Variável | Padrão | Uso |
|---|---|---|
| `CONFIDENCE_THRESHOLD` | 0.26 | Confiança mínima para aceitar uma pessoa |
| `MOTION_THRESHOLD_AREA` | 500 px | Área mínima de movimento para acionar o estágio 2 |
| `WARM_UP_FRAMES` | 30 | Frames para o MOG2 aprender o fundo ao iniciar |
| `DECISION_MODE` | `overlap` | Critério dentro/fora: `overlap`, `foot` ou `center` |
| `MIN_OVERLAP_RATIO` | 0.15 | Fração mínima da caixa dentro do polígono (modo `overlap`) |
| `EVENT_FRAME_INTERVAL_SECONDS` | 1.0 | Intervalo entre as 5 imagens de um evento |
| `NOTIFICATION_COOLDOWN_SECONDS` | 60 | Espera mínima entre dois eventos |
| `TELEGRAM_FORCE_IPV4` | 1 | Usa só IPv4 para falar com o Telegram |
| `SERVER_HOST` / `SERVER_PORT` | 0.0.0.0 / 5000 | Endereço do servidor web |

---

## 8. Próximos passos

| Ordem | Tarefa |
|---|---|
| 1 | Instalar e testar no Raspberry Pi 3 com `scripts/setup_raspberry_pi.sh` (ver `docs/INSTALACAO_RASPBERRY_PI.md`), medindo o desempenho do loop |
| 2 | Testar a calibração com a pessoa distante, de corpo inteiro (problema 1) |
