import { mkdir, rm } from "node:fs/promises";
import { spawn } from "node:child_process";
import path from "node:path";
import { chromium } from "playwright-core";
import ffmpegPath from "ffmpeg-static";

const chromePath = process.env.CHROME_PATH || "/usr/bin/google-chrome";
const outDir = path.resolve("apps/web/public/trabalho/videos");
const frameRoot = path.resolve(".trabalho-video-frames");

const videos = [
  {
    name: "professor-preferencias",
    title: "Portal do professor",
    subtitle: "Janelas, fila de cadeiras e restrições em linguagem natural",
    steps: [
      "Selecionar o professor convidado",
      "Adicionar N disponibilidades por dia",
      "Definir cadeiras desejadas em fila",
      "Registrar restrições complexas",
      "Enviar para a otimização"
    ]
  },
  {
    name: "aluno-escolhas",
    title: "Portal do aluno",
    subtitle: "Histórico simulado, sugestões e fila X, senão Y, senão Z",
    steps: [
      "Criar aluno de teste pelo QR Code",
      "Gerar histórico acadêmico aleatório",
      "Comparar sugestões com dependências",
      "Ordenar a fila de preferência",
      "Enviar demanda para a rodada administrativa"
    ]
  }
];

await mkdir(outDir, { recursive: true });
await rm(frameRoot, { recursive: true, force: true });
await mkdir(frameRoot, { recursive: true });

const browser = await chromium.launch({ executablePath: chromePath, headless: true });
try {
  for (const video of videos) {
    await renderVideo(browser, video);
  }
} finally {
  await browser.close();
}

async function renderVideo(browser, video) {
  const framesDir = path.join(frameRoot, video.name);
  await mkdir(framesDir, { recursive: true });
  const page = await browser.newPage({ viewport: { width: 1280, height: 720 }, deviceScaleFactor: 1 });
  const totalFrames = 150;
  for (let frame = 0; frame < totalFrames; frame += 1) {
    const progress = frame / (totalFrames - 1);
    await page.setContent(html(video, progress), { waitUntil: "load" });
    await page.screenshot({ path: path.join(framesDir, `frame-${String(frame).padStart(4, "0")}.png`) });
  }
  await page.close();
  await encode(framesDir, path.join(outDir, `${video.name}.mp4`));
}

function html(video, progress) {
  const active = Math.min(video.steps.length - 1, Math.floor(progress * video.steps.length));
  const cursorX = 230 + Math.sin(progress * Math.PI * 2) * 160 + active * 86;
  const cursorY = 530 - active * 66 + Math.cos(progress * Math.PI * 4) * 12;
  return `<!doctype html>
  <html lang="pt-BR">
    <head>
      <meta charset="utf-8" />
      <style>
        * { box-sizing: border-box; }
        body {
          margin: 0;
          font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
          background: #f6f8fb;
          color: #17202a;
        }
        .stage {
          width: 1280px;
          height: 720px;
          padding: 44px;
          background:
            linear-gradient(135deg, rgba(27,107,147,0.11), transparent 32%),
            linear-gradient(315deg, rgba(63,125,88,0.13), transparent 38%),
            #f6f8fb;
          overflow: hidden;
          position: relative;
        }
        .shell {
          display: grid;
          grid-template-columns: 410px 1fr;
          gap: 28px;
          height: 100%;
        }
        .panel {
          border: 1px solid #d8dee7;
          background: rgba(255,255,255,0.94);
          border-radius: 10px;
          box-shadow: 0 1px 2px rgba(23,32,42,0.08);
          padding: 28px;
        }
        .eyebrow { color: #1b6b93; font-size: 13px; font-weight: 800; text-transform: uppercase; }
        h1 { font-size: 42px; line-height: 1.02; margin: 10px 0 14px; letter-spacing: 0; }
        p { color: #536274; font-size: 18px; line-height: 1.45; margin: 0; }
        .preview { display: grid; gap: 16px; align-content: start; }
        .toolbar { display: flex; gap: 10px; border-bottom: 1px solid #d8dee7; padding-bottom: 16px; }
        .dot { width: 13px; height: 13px; border-radius: 50%; background: #d8dee7; }
        .dot:nth-child(1) { background: #a33a4a; }
        .dot:nth-child(2) { background: #b26a00; }
        .dot:nth-child(3) { background: #3f7d58; }
        .form { display: grid; gap: 14px; margin-top: 4px; }
        label { display: grid; gap: 7px; font-size: 13px; font-weight: 750; }
        .input { height: 42px; border: 1px solid #d8dee7; border-radius: 7px; background: #fff; padding: 0 14px; color: #536274; display: flex; align-items: center; }
        .queue { display: grid; gap: 10px; }
        .queue-item {
          display: flex;
          align-items: center;
          justify-content: space-between;
          border: 1px solid ${active > 1 ? "#1b6b93" : "#d8dee7"};
          border-radius: 8px;
          background: ${active > 1 ? "rgba(27,107,147,0.09)" : "#f8fafc"};
          padding: 12px 14px;
          font-size: 14px;
        }
        .steps { display: grid; gap: 12px; margin-top: 30px; }
        .step {
          border: 1px solid #d8dee7;
          border-radius: 8px;
          padding: 14px 16px;
          background: #fff;
          color: #536274;
          font-size: 15px;
          transform: translateX(0);
        }
        .step.active {
          border-color: #1b6b93;
          color: #17202a;
          box-shadow: 0 8px 28px rgba(27,107,147,0.13);
        }
        .button {
          height: 44px;
          border-radius: 8px;
          background: #1b6b93;
          color: white;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          font-weight: 800;
          margin-top: 6px;
        }
        .cursor {
          position: absolute;
          left: ${cursorX}px;
          top: ${cursorY}px;
          width: 24px;
          height: 24px;
          border-radius: 50%;
          border: 3px solid #17202a;
          background: rgba(255,255,255,0.85);
          box-shadow: 0 0 0 12px rgba(27,107,147,0.12);
        }
      </style>
    </head>
    <body>
      <main class="stage">
        <section class="shell">
          <aside class="panel">
            <div class="eyebrow">OptiGrade · tutorial</div>
            <h1>${video.title}</h1>
            <p>${video.subtitle}</p>
            <div class="steps">
              ${video.steps.map((step, index) => `<div class="step ${index === active ? "active" : ""}">${index + 1}. ${step}</div>`).join("")}
            </div>
          </aside>
          <section class="panel preview">
            <div class="toolbar"><span class="dot"></span><span class="dot"></span><span class="dot"></span></div>
            <div class="form">
              <label>Perfil <div class="input">${video.name.includes("professor") ? "Professor convidado" : "Aluno de teste"}</div></label>
              <label>${video.name.includes("professor") ? "Disponibilidade" : "Semestre alvo"} <div class="input">${video.name.includes("professor") ? "Segunda 08:00-12:00 · Quarta 14:00-18:00" : "2026/2"}</div></label>
              <label>${video.name.includes("professor") ? "Cadeiras desejadas" : "Fila de preferência"}</label>
              <div class="queue">
                <div class="queue-item"><strong>#1</strong><span>${video.name.includes("professor") ? "Cálculo A" : "Cálculo A em outra engenharia"}</span></div>
                <div class="queue-item"><strong>#2</strong><span>${video.name.includes("professor") ? "Álgebra Linear" : "Física I"}</span></div>
                <div class="queue-item"><strong>#3</strong><span>${video.name.includes("professor") ? "Pesquisa Operacional" : "Programação"}</span></div>
              </div>
              <label>Restrição <div class="input">${video.name.includes("professor") ? "Não posso sexta à noite; prefiro manhã." : "Quero X, senão Y, senão Z."}</div></label>
              <div class="button">Enviar para o planejamento</div>
            </div>
          </section>
        </section>
        <div class="cursor"></div>
      </main>
    </body>
  </html>`;
}

async function encode(framesDir, output) {
  await new Promise((resolve, reject) => {
    const child = spawn(ffmpegPath, [
      "-y",
      "-framerate",
      "15",
      "-i",
      path.join(framesDir, "frame-%04d.png"),
      "-c:v",
      "libx264",
      "-pix_fmt",
      "yuv420p",
      "-movflags",
      "+faststart",
      output
    ], { stdio: "inherit" });
    child.on("exit", (code) => code === 0 ? resolve() : reject(new Error(`ffmpeg exited with ${code}`)));
    child.on("error", reject);
  });
}
