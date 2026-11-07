require('dotenv').config();
const express = require('express');
const cors = require('cors');
const multer = require('multer');
const puppeteer = require('puppeteer');
const sharp = require('sharp');
const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');
const { get } = require('https');

// Um erro solto (ex.: EBUSY ao apagar pasta temporária do Chrome no Windows)
// não pode derrubar o backend inteiro — antes isso acontecia e a UI só mostrava
// "Erro ao gerar o convite". Registra no log e segue.
process.on('unhandledRejection', function (err) { console.error('[unhandledRejection]', err && err.message ? err.message : err); });
process.on('uncaughtException', function (err) { console.error('[uncaughtException]', err && err.message ? err.message : err); });

// WhatsApp/Facebook link previews (og:image) render at this exact size,
// so every uploaded preview image gets cropped/resized to match it.
const OG_IMAGE_WIDTH = 1366;
const OG_IMAGE_HEIGHT = 768;

// Same idea as fizzconvites: ONE Vercel project, deployed once and reused
// forever, instead of a brand-new project per convite. Every convite is
// just a new folder under SITE_ROOT/<slug>, and each deploy pushes
// the whole accumulated site. SITE_ROOT must already be `vercel link`-ed
// (see backend/README-DEPLOY.md) and SITE_BASE_URL must match that project's
// real domain — exactly like fizzconvites' NEXT_PUBLIC_BASE_URL.
const SITE_ROOT = path.join(__dirname, 'site');
const SITE_BASE_URL = (process.env.SITE_BASE_URL || '').replace(/\/+$/, '');

// Segundo destino, só pra convites NOVOS a partir de agora — a Vercel
// (SITE_ROOT acima) já está permanentemente acima do limite de 15.000
// arquivos por deploy dela, e migrar os convites já publicados lá seria
// arriscado sem necessidade. Convites novos vão pro Cloudflare Pages em vez
// disso, que não tem esse teto. Os convites antigos continuam 100% na
// Vercel, sem tocar em nada.
const SITE_ROOT_CF = path.join(__dirname, 'site-cf');
const SITE_BASE_URL_CF = (process.env.SITE_BASE_URL_CF || 'https://digital-convites-cf.pages.dev').replace(/\/+$/, '');
const CF_PROJECT_NAME = process.env.CF_PAGES_PROJECT || 'digital-convites-cf';
if (!fs.existsSync(SITE_ROOT_CF)) fs.mkdirSync(SITE_ROOT_CF, { recursive: true });

// Terceiro destino: o projeto Cloudflare acima chegou perto do limite de
// 20.000 arquivos por deploy (o plano gratuito recusa o deploy inteiro
// acima disso). Então convites NOVOS agora vão pra um segundo projeto
// Pages, com outro endereço — os que já estão em site/ e site-cf/
// continuam exatamente onde estão.
const SITE_ROOT_CF2 = path.join(__dirname, 'site-cf2');
const SITE_BASE_URL_CF2 = (process.env.SITE_BASE_URL_CF2 || 'https://digital-convites-cf2.pages.dev').replace(/\/+$/, '');
const CF2_PROJECT_NAME = process.env.CF2_PAGES_PROJECT || 'digital-convites-cf2';
if (!fs.existsSync(SITE_ROOT_CF2)) fs.mkdirSync(SITE_ROOT_CF2, { recursive: true });

// Dado um slug, descobre em qual dos três sites ele já foi publicado —
// assim /api/update funciona pra convites antigos (Vercel) e pros dois
// projetos Cloudflare sem precisar saber de antemão onde cada um está.
function resolveConviteLocation(slug) {
    if (fs.existsSync(path.join(SITE_ROOT_CF2, slug))) {
        return { platform: 'cf2', siteRoot: SITE_ROOT_CF2, siteBaseUrl: SITE_BASE_URL_CF2 };
    }
    if (fs.existsSync(path.join(SITE_ROOT_CF, slug))) {
        return { platform: 'cf', siteRoot: SITE_ROOT_CF, siteBaseUrl: SITE_BASE_URL_CF };
    }
    return { platform: 'vercel', siteRoot: SITE_ROOT, siteBaseUrl: SITE_BASE_URL };
}

const app = express();
app.use(cors());
app.use(express.json());

// Set up storage for uploaded preview images
const uploadDir = path.join(__dirname, 'uploads');
if (!fs.existsSync(uploadDir)) fs.mkdirSync(uploadDir);

const storage = multer.diskStorage({
    destination: function (req, file, cb) {
        cb(null, uploadDir)
    },
    filename: function (req, file, cb) {
        cb(null, Date.now() + '-' + file.originalname)
    }
});
const upload = multer({ storage: storage });

// Turns "Davi Emanuel" into "davi-emanuel" — keeps only what's safe in a
// filesystem path / URL segment.
function slugify(text) {
    return text
        .normalize('NFD').replace(/[̀-ͯ]/g, '') // strip accents
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/^-+|-+$/g, '');
}

// Converte PNGs pesados em WebP (mantendo transparência) sempre que o
// arquivo já baixado for grande o bastante pra valer a pena — muita imagem
// do Canva é foto exportada como PNG, que fica 5-10x maior que precisa.
// Só troca o arquivo quando o WebP sai pelo menos 30% menor (senão mantém
// o original), e reescreve toda ocorrência do nome antigo no HTML pro novo
// (mesma pasta, só muda a extensão). Roda em toda raspagem — criar convite
// e atualizar — então nunca mais precisa ser feito na mão depois.
async function optimizeImages(publicDir, html, { minKB = 30, quality = 82 } = {}) {
    const mediaDir = path.join(publicDir, '_assets', 'media');
    if (!fs.existsSync(mediaDir)) return html;

    const files = fs.readdirSync(mediaDir).filter((f) => f.toLowerCase().endsWith('.png'));
    for (const file of files) {
        const fullPath = path.join(mediaDir, file);
        const sizeKB = fs.statSync(fullPath).size / 1024;
        if (sizeKB < minKB) continue;

        const outName = file.replace(/\.png$/i, '.webp');
        try {
            const buffer = await sharp(fullPath).webp({ quality, effort: 4, alphaQuality: 90 }).toBuffer();
            const newSizeKB = buffer.length / 1024;
            if (newSizeKB < sizeKB * 0.7) {
                fs.writeFileSync(path.join(mediaDir, outName), buffer);
                fs.unlinkSync(fullPath);
                html = html.split(file).join(outName);
            }
        } catch (e) {
            // Se der erro num arquivo (corrompido, formato inesperado), só
            // pula ele e mantém o PNG original — nunca deixa a raspagem
            // inteira falhar por causa de otimização de imagem.
        }
    }
    return html;
}

// A Cloudflare Pages (site-cf) recusa o deploy inteiro se QUALQUER arquivo
// passar de 25 MiB — e vídeo exportado do Canva às vezes vem pesado o
// bastante pra estourar isso (já aconteceu: 43.7 MiB), o que derruba a
// publicação do site inteiro, não só daquele convite. Recomprime no lugar
// (mesmo nome de arquivo, então não precisa reescrever nada no HTML) até
// caber, tentando um CRF mais agressivo a cada tentativa. Se o ffmpeg não
// estiver disponível ou falhar, só pula o arquivo — nunca trava a
// raspagem por causa disso (o deploy que vai falhar depois, com o erro
// original do Cloudflare, é mais fácil de diagnosticar do que a raspagem
// quebrando aqui).
const CF_MAX_FILE_MB = 25;
async function optimizeVideos(publicDir, { targetMB = CF_MAX_FILE_MB - 1 } = {}) {
    const mediaDir = path.join(publicDir, '_assets', 'video');
    if (!fs.existsSync(mediaDir)) return;

    const files = fs.readdirSync(mediaDir).filter((f) => /\.mp4$/i.test(f));
    for (const file of files) {
        const fullPath = path.join(mediaDir, file);
        const sizeMB = fs.statSync(fullPath).size / (1024 * 1024);
        if (sizeMB <= targetMB) continue;

        const tmpPath = fullPath + '.tmp.mp4';
        let crf = 30;
        let ok = false;
        for (let attempt = 0; attempt < 3 && !ok; attempt++) {
            try {
                execSync(
                    `ffmpeg -y -i "${fullPath}" -c:v libx264 -crf ${crf} -preset veryfast -c:a aac -b:a 96k -movflags +faststart "${tmpPath}"`,
                    { stdio: 'ignore' }
                );
                const newSizeMB = fs.statSync(tmpPath).size / (1024 * 1024);
                if (newSizeMB <= targetMB) {
                    fs.renameSync(tmpPath, fullPath);
                    ok = true;
                } else {
                    crf += 6; // ainda grande demais: comprime mais e tenta de novo
                }
            } catch (e) {
                break; // ffmpeg indisponível ou falhou — mantém o arquivo original
            }
        }
        if (!ok) {
            try { fs.unlinkSync(tmpPath); } catch (e) {}
        }
    }
}

// Pulls the "<slug>" out of a full published link, or just returns the
// input if it's already a bare slug — so the "update" flow accepts either.
function extractSlug(input) {
    const trimmed = (input || '').trim();
    for (const base of [SITE_BASE_URL, SITE_BASE_URL_CF, SITE_BASE_URL_CF2]) {
        if (base && trimmed.startsWith(base)) {
            return trimmed.slice(base.length).replace(/^\/+|\/+$/g, '');
        }
    }
    return trimmed.replace(/\/+$/, '').split('/').pop();
}

// Scrapes canvaUrl into SITE_ROOT/<slug>, applying every fix learned the
// hard way: strip Canva's "made with Canva" footer (both the static markup
// AND the runtime endpoint it re-fetches), convert blob: images to real
// files, rewrite absolute Canva CDN links to the local mirrored copies,
// preload the hero image/fonts, cover the brief unstyled flash with a
// discreet loading screen, and catch any lazily-loaded asset the headless
// scrape never triggered. Reuses an existing preview.jpg / music.mp3 in
// publicDir if present (update flow) unless a new previewImagePath is given.
async function scrapeConvite({ slug, canvaUrl, previewImagePath, siteRoot = SITE_ROOT, siteBaseUrl = SITE_BASE_URL }) {
    const publicDir = path.join(siteRoot, slug);
    fs.mkdirSync(publicDir, { recursive: true });

    // Pasta de perfil PRÓPRIA por raspagem. Com a pasta padrão do Puppeteer o
    // launch() falhava de forma intermitente no Windows ("The browser is
    // already running for ...puppeteer_dev_chrome_profile-XXXX") e, com o
    // EBUSY que vinha junto, derrubava o backend inteiro.
    const userDataDir = path.join(require('os').tmpdir(), 'convite_scrape_' + Date.now() + '_' + Math.random().toString(36).slice(2, 8));
    const browser = await puppeteer.launch({ userDataDir });
    // Garante que o Chrome SEMPRE fecha, mesmo se a raspagem falhar no
    // meio (Canva fora do ar, erro de rede...). Antes, o close() só
    // rodava no caminho de sucesso: uma raspagem com erro deixava o
    // Chrome aberto segurando a pasta de perfil temporária, e a próxima
    // raspagem batia nela e derrubava o backend inteiro (EBUSY).
    try {
    const page = await browser.newPage();

    page.on('response', async (response) => {
        const requestUrl = response.request().url();
        if (!requestUrl.startsWith('https://seemg.my.canva.site/')) return;
        try {
            const parsedUrl = new URL(requestUrl);
            let pathname = parsedUrl.pathname;
            const basePath = new URL(canvaUrl).pathname;
            pathname = pathname.replace(basePath, '');
            if (pathname === '/' || pathname === '') pathname = '/index.html';

            // Canva's own client-side JS re-fetches this endpoint on every
            // page load and re-injects the "made with Canva" footer bar
            // into the DOM at runtime — removing it from the static HTML
            // does nothing if this file is still served, so never mirror it.
            if (pathname.includes('/_footer') || pathname === '_footer') return;

            const filePath = path.join(publicDir, pathname);
            const dir = path.dirname(filePath);
            if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
            const buffer = await response.buffer();
            fs.writeFileSync(filePath, buffer);
        } catch (e) {
            // Ignore some failed assets
        }
    });

    await page.goto(canvaUrl, { waitUntil: 'networkidle2', timeout: 60000 }).catch(() => {});

    // Strip the footer bar (and its hidden modals) via the real DOM before
    // serializing — the easiest reliable way regardless of markup shape.
    await page.evaluate(() => {
        document.querySelectorAll('.footer-overflow-container, .modal-backdrop, .report-form-modal').forEach((el) => el.remove());
    });

    // Some images are loaded as blob: URLs (created in-memory by the
    // page's own JS) instead of being fetched from a stable address —
    // those URLs die the moment this browser session ends. Read them
    // back out as data URLs here, while the page is still alive.
    const blobImages = await page.evaluate(async () => {
        const imgs = Array.from(document.querySelectorAll('img[src^="blob:"]'));
        const out = [];
        for (const img of imgs) {
            try {
                const resp = await fetch(img.src);
                const blob = await resp.blob();
                const dataUrl = await new Promise((resolve, reject) => {
                    const reader = new FileReader();
                    reader.onload = () => resolve(reader.result);
                    reader.onerror = () => reject(reader.error);
                    reader.readAsDataURL(blob);
                });
                out.push({ src: img.src, dataUrl });
            } catch (e) {
                out.push({ src: img.src, error: String(e) });
            }
        }
        return out;
    });

    let html = await page.content();

    // Swap each blob: src for a real file saved next to the convite.
    const MIME_EXT = { 'image/png': 'png', 'image/jpeg': 'jpg', 'image/webp': 'webp', 'image/gif': 'gif', 'image/svg+xml': 'svg' };
    blobImages.forEach((entry, i) => {
        if (!entry.dataUrl) return;
        const match = entry.dataUrl.match(/^data:([^;]+);base64,(.*)$/s);
        if (!match) return;
        const ext = MIME_EXT[match[1]] || 'bin';
        const fileName = `_assets/blob/blob-${i}.${ext}`;
        const filePath = path.join(publicDir, fileName);
        fs.mkdirSync(path.dirname(filePath), { recursive: true });
        fs.writeFileSync(filePath, Buffer.from(match[2], 'base64'));
        html = html.split(`src="${entry.src}"`).join(`src="${fileName}"`);
    });

    // Some elements reference the ORIGINAL absolute Canva URL even though
    // we already mirrored that exact file locally (same path, just
    // relative). Left as absolute, the browser fetches straight from
    // Canva's CDN, which can 404/hotlink-block from another domain.
    const canvaOriginPrefix = new URL(canvaUrl).origin + new URL(canvaUrl).pathname + '/';
    html = html.split(canvaOriginPrefix).join('');

    // Adjust base tag — this convite lives under /<slug>/, not at the
    // domain root, so relative assets must resolve there.
    const baseHref = `/${slug}/`;
    const baseRegex = /<base href="[^"]*">/;
    if (baseRegex.test(html)) {
        html = html.replace(baseRegex, `<base href="${baseHref}">`);
    } else {
        html = html.replace('<head>', `<head><base href="${baseHref}">`);
    }

    // Speed up the actual load instead of masking it with an overlay: tell
    // the browser about the hero image and fonts up front so it fetches
    // them immediately with high priority.
    const heroImageMatch = html.match(/<img[^>]*src="(_assets\/[^"]+\.(?:png|jpe?g|webp))"/);
    const fontMatches = [...html.matchAll(/_assets\/fonts\/[a-zA-Z0-9_\-./]+\.woff2?/g)].map((m) => m[0]);
    const preloadLinks = [
        heroImageMatch && `<link rel="preload" as="image" href="${heroImageMatch[1]}" fetchpriority="high">`,
        ...new Set(fontMatches.slice(0, 4).map((f) => `<link rel="preload" as="font" type="font/${f.endsWith('.woff2') ? 'woff2' : 'woff'}" href="${f}" crossorigin>`)),
    ].filter(Boolean).join('\n');
    if (preloadLinks) {
        html = html.replace('<head>', `<head>${preloadLinks}`);
    }

    // A discreet loading cover — plain background, no spinner — so the
    // brief flash of unstyled content is hidden without looking like a
    // "loading screen". Fades out quickly once ready, with a short safety
    // timeout in case something never fires 'load'.
    const loadingOverlay = `
        <div id="__loading_overlay" style="position:fixed;inset:0;z-index:2147483647;background:#faf8f5;transition:opacity .3s ease;"></div>
        <script>
        (function () {
            function hideLoadingOverlay() {
                var el = document.getElementById('__loading_overlay');
                if (!el) return;
                el.style.opacity = '0';
                setTimeout(function () { el.remove(); }, 300);
            }
            if (document.readyState === 'complete') hideLoadingOverlay();
            else window.addEventListener('load', hideLoadingOverlay);
            setTimeout(hideLoadingOverlay, 2500);
        })();
        </script>
    `;
    html = html.replace(/<body([^>]*)>/, `<body$1>${loadingOverlay}`);

    // Alguns designs do Canva vêm com uma caixa de texto "ok" que sobrou
    // colada no rodapé de cada página — ela é montada em runtime a partir
    // dos dados (criptografados) do Canva, então não dá pra remover
    // editando o HTML estático. Este trecho apaga qualquer elemento de
    // texto (título, parágrafo, span, div…) cujo conteúdo seja só "ok",
    // assim que aparece, em todas as páginas. Não mexe em links/botões
    // (poderiam ter um "OK" legítimo).
    const okStripper = `
        <script>
        (function () {
            var SEL = 'h1,h2,h3,h4,h5,h6,p,span,div,strong,b,em,label';
            function isOk(el) {
                return el && el.childElementCount === 0 &&
                    (el.textContent || '').trim().toLowerCase() === 'ok';
            }
            function stripOk(scope) {
                var els = (scope && scope.querySelectorAll ? scope : document).querySelectorAll(SEL);
                for (var i = 0; i < els.length; i++) if (isOk(els[i])) els[i].remove();
            }
            stripOk(document);
            if (typeof MutationObserver !== 'undefined') {
                new MutationObserver(function (muts) {
                    for (var i = 0; i < muts.length; i++) {
                        var added = muts[i].addedNodes;
                        for (var j = 0; j < added.length; j++) {
                            var nd = added[j];
                            if (nd.nodeType !== 1) continue;
                            if (isOk(nd)) nd.remove();
                            else stripOk(nd);
                        }
                    }
                }).observe(document.documentElement, { childList: true, subtree: true });
            }
        })();
        </script>
    `;
    html = html.replace(/<body([^>]*)>/, `<body$1>${okStripper}`);

    // Open Graph metadata: a new upload always wins; otherwise reuse
    // whatever preview.jpg is already sitting in this convite's folder
    // (relevant for the "update" flow, so re-scraping doesn't lose it).
    if (previewImagePath) {
        // WhatsApp/Facebook always render the og:image at a fixed frame,
        // so force every upload to exactly 1366x768 (cropping to fill,
        // never stretching) instead of trusting whatever was sent.
        await sharp(previewImagePath)
            .resize(OG_IMAGE_WIDTH, OG_IMAGE_HEIGHT, { fit: 'cover', position: 'centre' })
            .jpeg({ quality: 90 })
            .toFile(path.join(publicDir, 'preview.jpg'));
        fs.unlink(previewImagePath, () => {});
    }
    const hasPreviewImage = previewImagePath || fs.existsSync(path.join(publicDir, 'preview.jpg'));
    if (hasPreviewImage) {
        // The scraped Canva page already ships its own og:title/og:image
        // (pointing at Canva's CDN). Crawlers use the FIRST tag they see,
        // so simply appending ours after would be silently ignored — strip
        // the originals first so ours are the only ones left.
        html = html.replace(/<meta[^>]*property="og:(title|image|image:width|image:height|type|url)"[^>]*>\s*/gi, '');
        html = html.replace(/<meta[^>]*name="twitter:(card|image|title)"[^>]*>\s*/gi, '');

        const conviteUrl = `${siteBaseUrl}${baseHref}`;
        const ogTags = `
            <meta property="og:title" content="Convite Especial">
            <meta property="og:image" content="${conviteUrl}preview.jpg">
            <meta property="og:image:width" content="${OG_IMAGE_WIDTH}">
            <meta property="og:image:height" content="${OG_IMAGE_HEIGHT}">
            <meta property="og:type" content="website">
            <meta name="twitter:card" content="summary_large_image">
            <meta name="twitter:image" content="${conviteUrl}preview.jpg">
        `;
        html = html.replace('</head>', ogTags + '</head>');
    }

    // Background music: if this convite already has a music.mp3 (added
    // manually or by a previous update), keep the play-on-first-tap hook
    // wired up so re-scraping the Canva content doesn't silently drop it.
    if (fs.existsSync(path.join(publicDir, 'music.mp3'))) {
        const musicBlock = `
            <audio id="__bgm" src="music.mp3" loop preload="auto"></audio>
            <script>
            (function () {
                var started = false;
                function tryPlay() {
                    if (started) return;
                    var audio = document.getElementById('__bgm');
                    if (!audio) return;
                    audio.play().then(function () { started = true; }).catch(function () {});
                }
                document.addEventListener('click', tryPlay, true);
                window.addEventListener('hashchange', tryPlay);
            })();
            </script>
        `;
        html = html.replace(/<body([^>]*)>/, `<body$1>${musicBlock}`);
    }

    await browser.close();

    // Catch-up pass: Canva sites lazy-load a lot of images (gift lists,
    // later "pages" of a multi-page invite, etc.) that only fire a network
    // request once scrolled/navigated to — our headless scrape never
    // triggers those, so any "_assets/..." path still mentioned in the
    // HTML but not yet saved to disk gets fetched directly here.
    const downloadAsset = (assetPath) => new Promise((resolve) => {
        const localPath = path.join(publicDir, assetPath);
        const dir = path.dirname(localPath);
        if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
        const fullUrl = new URL(canvaUrl).origin + new URL(canvaUrl).pathname + '/' + assetPath;
        const file = fs.createWriteStream(localPath);
        get(fullUrl, (response) => {
            if (response.statusCode !== 200) {
                file.close();
                fs.rm(localPath, () => {});
                return resolve();
            }
            response.pipe(file);
            file.on('finish', () => { file.close(); resolve(); });
        }).on('error', () => resolve());
    });

    const assetRefs = new Set([...html.matchAll(/_assets\/[a-zA-Z0-9_\-./]+\.[a-zA-Z0-9]+/g)].map((m) => m[0]));
    for (const assetPath of assetRefs) {
        if (!fs.existsSync(path.join(publicDir, assetPath))) {
            await downloadAsset(assetPath);
        }
    }

    // Vídeos em HLS trazem um manifesto "mestre" (.m3u) que aparece no
    // HTML — mas esse mestre, por sua vez, referencia sub-playlists (uma
    // por qualidade/resolução) que só existem DENTRO do próprio arquivo
    // .m3u, nunca no HTML. O catch-up pass acima (que só olha o HTML) não
    // as pega, então elas ficam faltando: o navegador recebe 404 ao tentar
    // tocar aquela qualidade, e o player recupera "reiniciando" o vídeo do
    // zero no meio da reprodução. Além disso, o Canva às vezes referencia
    // o arquivo de mídia com a extensão em MAIÚSCULA (.MP4/.M4A) dentro do
    // .m3u, mesmo quando o arquivo salvo é minúsculo — no Windows não faz
    // diferença, mas em host sensível a maiúscula/minúscula (Vercel/
    // Cloudflare) isso também 404. Resolve os dois problemas de uma vez:
    // baixa toda sub-playlist/segmento ainda faltando (varrendo
    // recursivamente, já que uma sub-playlist pode referenciar outra) e
    // corrige a referência pro nome exato que está em disco.
    await fetchMissingHlsReferences(publicDir, canvaUrl);

    // Otimização automática de imagens: o Canva exporta as imagens do
    // design como PNG, mesmo quando é conteúdo fotográfico — nesses casos
    // o PNG costuma pesar 5-10x mais que o necessário. Converte pra WebP
    // (mantém transparência) sempre que isso realmente compensar, e
    // reescreve as referências no HTML. Não mexe em nada que já é pequeno
    // (esses o PNG já é eficiente, ou já é a própria imagem otimizada de
    // uma raspagem anterior).
    html = await optimizeImages(publicDir, html);

    // Comprime qualquer vídeo que passe do limite de 25 MiB do Cloudflare
    // Pages — sem isso, o deploy do SITE INTEIRO falha por causa de um
    // convite só (já aconteceu). Não mexe no HTML: reescreve o arquivo no
    // mesmo nome.
    await optimizeVideos(publicDir);

    fs.writeFileSync(path.join(publicDir, 'index.html'), html);
    } finally {
        await browser.close().catch(function () {});
        // Limpa a pasta de perfil; se o Windows ainda estiver segurando algum
        // arquivo, ignora (não pode derrubar o backend por causa de lixo temporário).
        try { fs.rmSync(userDataDir, { recursive: true, force: true, maxRetries: 3, retryDelay: 300 }); } catch (e) {}
    }
}

function findFilesByExt(dir, ext) {
    let out = [];
    if (!fs.existsSync(dir)) return out;
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
        const p = path.join(dir, entry.name);
        if (entry.isDirectory()) out = out.concat(findFilesByExt(p, ext));
        else if (entry.name.toLowerCase().endsWith(ext)) out.push(p);
    }
    return out;
}

// Ver comentário no ponto de chamada (dentro de scrapeConvite) pro porquê
// disso existir: sub-playlists HLS que só aparecem dentro de outro .m3u
// (nunca no HTML) e referências de nome de arquivo com o "case" errado
// (.MP4 vs .mp4) — ambos causam 404 em host sensível a maiúscula/
// minúscula, e o player de vídeo reage a isso reiniciando o vídeo do zero.
async function fetchMissingHlsReferences(publicDir, canvaUrl) {
    const queue = findFilesByExt(publicDir, '.m3u');
    const seen = new Set(queue);
    while (queue.length) {
        const m3uPath = queue.shift();
        const dir = path.dirname(m3uPath);
        const relDir = path.relative(publicDir, dir).split(path.sep).join('/');
        let text;
        try {
            text = fs.readFileSync(m3uPath, 'utf-8');
        } catch {
            continue;
        }

        // Nomes referenciados: em `URI="..."` (variant streams, mapas de
        // init) ou em linha isolada sem "#" (segmentos/sub-playlists).
        const names = new Set();
        for (const m of text.matchAll(/URI="([^"]+)"/g)) names.add(m[1]);
        for (const line of text.split('\n')) {
            const t = line.trim();
            if (t && !t.startsWith('#')) names.add(t);
        }

        const existing = fs.existsSync(dir) ? fs.readdirSync(dir) : [];
        const existingLower = new Map(existing.map((f) => [f.toLowerCase(), f]));
        let changed = false;

        for (const name of names) {
            if (/^https?:\/\//i.test(name)) continue;
            if (existing.includes(name)) continue;
            const correctCase = existingLower.get(name.toLowerCase());
            if (correctCase) {
                // Existe, só com outro "case" — corrige a referência.
                text = text.split(name).join(correctCase);
                changed = true;
                continue;
            }
            // Não existe de jeito nenhum: baixa (essa é a sub-playlist ou
            // segmento que o catch-up pass baseado em HTML nunca via).
            const assetPath = (relDir ? `${relDir}/` : '') + name;
            const localPath = path.join(publicDir, assetPath);
            const fullUrl = `${new URL(canvaUrl).origin}${new URL(canvaUrl).pathname}/${assetPath}`;
            const ok = await new Promise((resolve) => {
                const file = fs.createWriteStream(localPath);
                get(fullUrl, (response) => {
                    if (response.statusCode !== 200) {
                        file.close();
                        fs.rm(localPath, () => {});
                        return resolve(false);
                    }
                    response.pipe(file);
                    file.on('finish', () => { file.close(); resolve(true); });
                }).on('error', () => resolve(false));
            });
            if (ok && name.toLowerCase().endsWith('.m3u') && !seen.has(localPath)) {
                seen.add(localPath);
                queue.push(localPath);
            }
        }

        if (changed) fs.writeFileSync(m3uPath, text);
    }
}

// Safety net: an append-only registry of every slug that has ever been
// published. Deleting a convite folder is something that should ONLY ever
// happen via `scripts/deactivate.js` (which removes it from here too, on
// purpose). If a folder that's still in this list goes missing from disk
// for any other reason — a stray `rm`, a bad script, anything — the next
// deploy gets blocked instead of silently publishing a site with that
// convite gone. This is how "nenhum convite pode sair do ar sem querer"
// is actually enforced, not just a hope.
function manifestPathFor(siteRoot) {
    return path.join(siteRoot, '.manifest.json');
}

function loadManifest(siteRoot = SITE_ROOT) {
    const manifestPath = manifestPathFor(siteRoot);
    if (!fs.existsSync(manifestPath)) return [];
    try {
        return JSON.parse(fs.readFileSync(manifestPath, 'utf-8'));
    } catch (e) {
        return [];
    }
}

function saveManifest(slugs, siteRoot = SITE_ROOT) {
    fs.writeFileSync(manifestPathFor(siteRoot), JSON.stringify([...new Set(slugs)].sort(), null, 2));
}

function registerSlug(slug, siteRoot = SITE_ROOT) {
    const manifest = loadManifest(siteRoot);
    if (!manifest.includes(slug)) {
        manifest.push(slug);
        saveManifest(manifest, siteRoot);
    }
    syncTrackedManifest(siteRoot);
}

// A lista de convites do cf2 também fica em backend/manifests/cf2.json (essa vai pro GitHub),
// pra um computador novo saber o que baixar com "npm run sync" e a trava funcionar lá também.
const TRACKED_CF2_MANIFEST = path.join(__dirname, 'manifests', 'cf2.json');
function syncTrackedManifest(siteRoot) {
    if (siteRoot !== SITE_ROOT_CF2) return;
    try {
        fs.mkdirSync(path.dirname(TRACKED_CF2_MANIFEST), { recursive: true });
        fs.writeFileSync(TRACKED_CF2_MANIFEST, JSON.stringify([...new Set(loadManifest(siteRoot))].sort(), null, 2));
    } catch (e) { console.warn('Aviso: não consegui atualizar manifests/cf2.json:', e.message); }
}

// Throws if any convite that's supposed to exist (per the manifest) is
// missing from disk. Called right before every deploy.
function assertNoConviteWentMissing(siteRoot = SITE_ROOT) {
    let manifest = loadManifest(siteRoot);
    if (siteRoot === SITE_ROOT_CF2 && fs.existsSync(TRACKED_CF2_MANIFEST)) {
        try { manifest = [...new Set([...manifest, ...JSON.parse(fs.readFileSync(TRACKED_CF2_MANIFEST, 'utf-8'))])]; } catch (e) {}
    }
    const missing = manifest.filter((slug) => !fs.existsSync(path.join(siteRoot, slug)));
    if (missing.length > 0) {
        throw new Error(
            `DEPLOY BLOQUEADO: ${missing.length} convite(s) que deveriam existir sumiram da pasta ${siteRoot}: ${missing.join(', ')}. ` +
            `Se é um computador novo, rode "npm run sync" (dentro de backend) pra baixar os convites do site publicado. ` +
            `Se foi intencional tirar do ar, rode "node scripts/archive.js <slug>" (arquiva sem apagar e atualiza o manifesto).`
        );
    }
}

// Deploys SITE_ROOT as a whole — this is the ONE persistent project,
// already linked via `.vercel/project.json` (one-time setup), so this
// always updates the same project/domain instead of creating a new one.
// Uses VERCEL_TOKEN if set (non-interactive), otherwise requires the
// machine to already be logged in (`vercel login`).
function deploySite() {
    assertNoConviteWentMissing();
    const tokenFlag = process.env.VERCEL_TOKEN ? ` --token ${process.env.VERCEL_TOKEN}` : '';
    let deployOutput;
    try {
        // Se o site passar de 15.000 arquivos, a Vercel recusa o upload
        // arquivo-por-arquivo ("files should NOT have more than 15000
        // items") e sugere `--archive=tgz`. NÃO liga essa flag por padrão:
        // ela reenvia o site INTEIRO comprimido a cada deploy (já vimos
        // isso virar 4+ GB e falhar por timeout de rede), em vez do envio
        // incremental normal (só o que mudou). Se esse erro aparecer de
        // novo, a solução certa é reduzir a contagem de convites ativos
        // (`node scripts/deactivate.js <slug>` nos mais antigos/duplicados)
        // e não usar essa flag.
        deployOutput = execSync(`npx vercel --prod --yes --archive=tgz${tokenFlag}`, {
            cwd: SITE_ROOT,
            encoding: 'utf-8',
            stdio: ['ignore', 'pipe', 'pipe'],
        });
    } catch (deployError) {
        const combined = `${deployError.stdout || ''}${deployError.stderr || ''}`;
        if (/not authoriz|log in|credentials/i.test(combined)) {
            throw new Error('O Vercel CLI não está logado neste servidor. Rode "npx vercel login" no terminal do backend (ou defina a variável de ambiente VERCEL_TOKEN) e tente novamente.');
        }
        if (/Project not found|link/i.test(combined)) {
            throw new Error('O site ainda não foi vinculado a um projeto Vercel. Veja backend/README-DEPLOY.md para o setup de uma vez.');
        }
        throw new Error(combined.trim() || deployError.message);
    }

    // `vercel alias set` points a domain at ONE specific deployment — it
    // does NOT auto-follow future deploys. So every time we deploy, we
    // re-point SITE_BASE_URL's domain at whatever we just published,
    // otherwise it would keep serving whatever was live when the alias
    // was first created (stale convites, 404s for new ones).
    const rawUrlMatch = deployOutput.match(/https:\/\/[^\s"'<>,]+/);
    const siteBaseHost = new URL(SITE_BASE_URL).host;
    if (rawUrlMatch && rawUrlMatch[0] !== SITE_BASE_URL && !rawUrlMatch[0].includes(siteBaseHost)) {
        const tokenFlag2 = process.env.VERCEL_TOKEN ? ` --token ${process.env.VERCEL_TOKEN}` : '';
        try {
            execSync(`npx vercel alias set ${rawUrlMatch[0]} ${siteBaseHost}${tokenFlag2}`, {
                cwd: SITE_ROOT,
                encoding: 'utf-8',
                stdio: ['ignore', 'pipe', 'pipe'],
            });
        } catch (aliasError) {
            console.error(`Não foi possível atualizar o alias ${siteBaseHost}:`, aliasError.message);
        }
    }
}

// Publica SITE_ROOT_CF inteiro no Cloudflare Pages. Diferente da Vercel,
// o Cloudflare Pages não tem esse limite de 15.000 arquivos por deploy, e
// o `wrangler pages deploy` já faz upload incremental sozinho (só reenvia o
// que mudou), então nunca precisou de nada equivalente ao --archive=tgz
// daqui. Precisa estar logado (`npx wrangler login`, uma vez só) ou ter
// CLOUDFLARE_API_TOKEN definido no ambiente.
function deploySiteCF(siteRoot = SITE_ROOT_CF, projectName = CF_PROJECT_NAME) {
    assertNoConviteWentMissing(siteRoot);
    try {
        // Wrangler lê CLOUDFLARE_API_TOKEN do ambiente sozinho se estiver
        // definida; senão usa a sessão OAuth salva por `wrangler login`.
        execSync(`npx wrangler pages deploy . --project-name ${projectName} --branch main --commit-dirty=true`, {
            cwd: siteRoot,
            encoding: 'utf-8',
            stdio: ['ignore', 'pipe', 'pipe'],
        });
    } catch (deployError) {
        const combined = `${deployError.stdout || ''}${deployError.stderr || ''}`;
        if (/not authenticated|log in|OAuth/i.test(combined)) {
            throw new Error('O Wrangler (Cloudflare) não está logado neste servidor. Rode "npx wrangler login" no terminal do backend (ou defina a variável de ambiente CLOUDFLARE_API_TOKEN) e tente novamente.');
        }
        throw new Error(`${combined.trim() || deployError.message} [status=${deployError.status} signal=${deployError.signal} code=${deployError.code}]`);
    }
}

app.post('/api/deploy', upload.single('previewImage'), async (req, res) => {
    const { canvaUrl, nome, idade } = req.body;
    const previewImage = req.file;

    if (!canvaUrl) {
        return res.status(400).json({ error: 'A URL do Canva é obrigatória.' });
    }
    if (!SITE_BASE_URL_CF2) {
        return res.status(500).json({
            error: 'SITE_BASE_URL_CF2 não está configurada no backend.',
        });
    }

    // Each convite is a folder inside the ONE persistent site, not a
    // standalone project — so this only needs to be a unique, readable
    // path segment (no DNS-label length limit to worry about).
    const randomSuffix = String(Math.floor(Math.random() * 1000000));
    const nameSlug = [nome && slugify(nome), idade && slugify(String(idade))]
        .filter(Boolean)
        .join('-');
    const slug = [nameSlug, randomSuffix].filter(Boolean).join('-').slice(0, 80).replace(/-+$/g, '');
    // Convites NOVOS vão pro segundo projeto Cloudflare (ver comentário em
    // SITE_ROOT_CF2) — os que já existem na Vercel e no primeiro projeto
    // Cloudflare continuam onde estão, sem qualquer mudança nesse fluxo.
    const publicDir = path.join(SITE_ROOT_CF2, slug);

    try {
        console.log(`[${slug}] Iniciando raspagem do site: ${canvaUrl}`);
        await scrapeConvite({ slug, canvaUrl, previewImagePath: previewImage && previewImage.path, siteRoot: SITE_ROOT_CF2, siteBaseUrl: SITE_BASE_URL_CF2 });

        console.log(`[${slug}] Fazendo deploy do site (todos os convites) para o Cloudflare Pages (projeto 2)...`);
        deploySiteCF(SITE_ROOT_CF2, CF2_PROJECT_NAME);
        registerSlug(slug, SITE_ROOT_CF2);

        const finalUrl = `${SITE_BASE_URL_CF2}/${slug}/`;
        res.json({ success: true, url: finalUrl });
    } catch (error) {
        console.error(error);
        res.status(500).json({ error: 'Erro ao processar e publicar o convite.', details: error.message });
        // Roll back this convite's folder so a failed attempt doesn't get
        // published on the next successful deploy.
        fs.rm(publicDir, { recursive: true, force: true }, () => {});
    }
});

// Re-scrapes an ALREADY-published convite in place — same link, same
// folder — after the Canva design was edited. Keeps whatever preview.jpg
// / music.mp3 that convite already has (or replaces the image if a new
// one is uploaded here).
app.post('/api/update', upload.single('previewImage'), async (req, res) => {
    const { canvaUrl, link } = req.body;
    const previewImage = req.file;

    if (!canvaUrl || !link) {
        return res.status(400).json({ error: 'O link do convite já publicado e a URL do Canva são obrigatórios.' });
    }

    const slug = extractSlug(link);
    // Convites antigos estão na Vercel, os criados desde a migração para o
    // Cloudflare estão em SITE_ROOT_CF — descobre automaticamente qual, pra
    // esse endpoint funcionar pros dois sem o formulário precisar saber.
    const { platform, siteRoot, siteBaseUrl } = resolveConviteLocation(slug);
    const publicDir = path.join(siteRoot, slug);
    if (!slug || !fs.existsSync(publicDir)) {
        return res.status(404).json({ error: 'Não encontrei esse convite publicado. Confira se o link está certo.' });
    }

    try {
        console.log(`[${slug}] Atualizando a partir de: ${canvaUrl}`);
        await scrapeConvite({ slug, canvaUrl, previewImagePath: previewImage && previewImage.path, siteRoot, siteBaseUrl });

        console.log(`[${slug}] Fazendo deploy do site (todos os convites) para ${platform === 'vercel' ? 'a Vercel' : 'o Cloudflare Pages'}...`);
        if (platform === 'cf2') deploySiteCF(SITE_ROOT_CF2, CF2_PROJECT_NAME);
        else if (platform === 'cf') deploySiteCF();
        else deploySite();

        const finalUrl = `${siteBaseUrl}/${slug}/`;
        res.json({ success: true, url: finalUrl });
    } catch (error) {
        console.error(error);
        res.status(500).json({ error: 'Erro ao atualizar o convite.', details: error.message });
    }
});

const PORT = 4000;
app.listen(PORT, () => {
    console.log(`Backend server running on http://localhost:${PORT}`);
    if (!SITE_BASE_URL) {
        console.warn('AVISO: variável de ambiente SITE_BASE_URL não definida — veja backend/README-DEPLOY.md.');
    }
});
