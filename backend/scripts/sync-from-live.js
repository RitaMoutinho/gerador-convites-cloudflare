// Baixa os convites do site PUBLICADO (cf2) pra pasta backend/site-cf2 deste computador.
// Rodar uma vez em computador novo, ANTES de publicar qualquer coisa: o Cloudflare Pages publica
// a pasta inteira, então publicar sem os convites antigos tiraria eles do ar.
// Uso: npm run sync             (baixa só o que falta)
//      npm run sync -- <slug>   (baixa de novo só esse convite)
const fs = require('fs');
const path = require('path');
const { siteRoot, BASE, manifestFile, trackedManifest } = require('./lib');

fs.mkdirSync(siteRoot, { recursive: true });
const slugs = JSON.parse(fs.readFileSync(trackedManifest, 'utf-8'));
const only = process.argv.slice(2);
const todo = only.length ? only : slugs.filter((s) => !fs.existsSync(path.join(siteRoot, s, 'index.html')));

async function get(url, isHtml) {
    for (let i = 0; i < 4; i++) {
        try {
            const r = await fetch(url);
            if (r.status === 404) return null;
            if (!r.ok) throw new Error('HTTP ' + r.status);
            const type = r.headers.get('content-type') || '';
            if (!isHtml && /text\/html/.test(type)) return null; // o Cloudflare devolve a página inicial em vez de 404
            return Buffer.from(await r.arrayBuffer());
        } catch (e) {
            if (i === 3) throw e;
            await new Promise((x) => setTimeout(x, 1500 * (i + 1)));
        }
    }
}

async function save(slug, rel, isHtml) {
    const file = path.join(siteRoot, slug, rel);
    if (fs.existsSync(file) && !only.length) return true;
    const buf = await get(`${BASE}/${slug}/${rel}`, isHtml);
    if (!buf) return false;
    fs.mkdirSync(path.dirname(file), { recursive: true });
    fs.writeFileSync(file, buf);
    return true;
}

async function pool(items, n, fn) {
    let i = 0;
    await Promise.all(Array.from({ length: n }, async () => { while (i < items.length) await fn(items[i++]); }));
}

(async () => {
    console.log(`${todo.length} convite(s) pra baixar de ${BASE}`);
    let n = 0;
    for (const slug of todo) {
        n++;
        const html = await get(`${BASE}/${slug}/`, true);
        if (!html) { console.log(`[${n}/${todo.length}] ${slug}: NÃO ENCONTRADO no site publicado (pulei)`); continue; }
        fs.mkdirSync(path.join(siteRoot, slug), { recursive: true });
        fs.writeFileSync(path.join(siteRoot, slug, 'index.html'), html);
        // mesma regex ampla do servidor: pega até o que só aparece dentro dos blocos de dados do Canva
        const refs = new Set([...html.toString('utf-8').matchAll(/_assets\/[a-zA-Z0-9_\-.\/]+\.[a-zA-Z0-9]+/g)].map((m) => m[0]));
        let miss = 0;
        await pool([...refs], 8, async (r) => { if (!(await save(slug, r, false))) miss++; });
        for (const extra of ['music.mp3', 'preview.jpg']) await save(slug, extra, false);
        console.log(`[${n}/${todo.length}] ${slug}: ${refs.size} arquivos${miss ? ` (${miss} não encontrados, pode ser normal)` : ''}`);
    }
    fs.writeFileSync(manifestFile, JSON.stringify(slugs, null, 2));
    console.log('Pronto. Agora já pode criar/atualizar convites e publicar com segurança.');
})().catch((e) => { console.error('ERRO:', e.message); process.exit(1); });
