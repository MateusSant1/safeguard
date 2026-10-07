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
