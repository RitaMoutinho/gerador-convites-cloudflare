// Funções comuns dos scripts. Os convites NOVOS ficam em backend/site-cf3 e vão pro projeto digital-convites-cf3.
const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const siteRoot = path.join(__dirname, '..', 'site-cf3');
const PROJECT = process.env.CF3_PAGES_PROJECT || 'digital-convites-cf3';
const BASE = (process.env.SITE_BASE_URL_CF3 || 'https://digital-convites-cf3.pages.dev').replace(/\/+$/, '');
const manifestFile = path.join(siteRoot, '.manifest.json');
const trackedManifest = path.join(__dirname, '..', 'manifests', 'cf3.json');

// O Cloudflare Pages publica a PASTA INTEIRA: se faltar convite aqui, ele sai do ar. Esta trava impede isso.
function assertSynced() {
    const wanted = JSON.parse(fs.readFileSync(trackedManifest, 'utf-8'));
    const missing = wanted.filter((s) => !fs.existsSync(path.join(siteRoot, s)));
    if (missing.length) {
        throw new Error(
            `DEPLOY BLOQUEADO: faltam ${missing.length} convite(s) nesta pasta (ex.: ${missing.slice(0, 3).join(', ')}). ` +
            'Publicar assim tiraria eles do ar. Rode "npm run sync" (dentro de backend) pra baixar do site publicado e tente de novo.'
        );
    }
}

function deploy() {
    assertSynced();
    console.log('Publicando no Cloudflare Pages (' + PROJECT + ')...');
    execSync(`npx wrangler pages deploy . --project-name ${PROJECT} --branch main --commit-dirty=true`, { cwd: siteRoot, stdio: 'inherit' });
}

async function verifyAudio(slug, expectedSize) {
    for (let i = 0; i < 8; i++) {
        await new Promise((r) => setTimeout(r, 6000));
        const r = await fetch(`${BASE}/${slug}/music.mp3?x=${Date.now()}`).catch(() => null);
        if (r && /audio/.test(r.headers.get('content-type') || '')) {
            const n = (await r.arrayBuffer()).byteLength;
            if (!expectedSize || n === expectedSize) { console.log('OK: música no ar (' + n + ' bytes).'); return; }
        }
    }
    console.log('AVISO: não consegui confirmar a música no ar ainda. Abra o link e confira.');
}

module.exports = { siteRoot, PROJECT, BASE, manifestFile, trackedManifest, deploy, assertSynced, verifyAudio };
