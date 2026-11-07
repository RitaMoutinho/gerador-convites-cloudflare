// Baixa os convites do site PUBLICADO (cf3) pra pasta backend/site-cf3 deste computador.
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
        // Fila que cresce: os .js do Canva citam outros pedaços ("<16 hex>.js", carregados só quando preciso)
        // e os .css citam fontes/imagens com url(...). Sem seguir esses, o convite quebra depois de publicado.
        const seen = new Set(refs);
        const queue = [...refs];
        const followRefs = (rel) => {
            if (!/\.(js|css)$/.test(rel)) return;
            const file = path.join(siteRoot, slug, rel);
            if (!fs.existsSync(file)) return;
            const txt = fs.readFileSync(file, 'utf-8');
            const add = (r) => { if (!seen.has(r)) { seen.add(r); queue.push(r); } };
            for (const m of txt.matchAll(/\b[0-9a-f]{16}(?:\.[A-Za-z0-9_-]+)*\.(?:js|css)\b/g)) add('_assets/' + m[0]);
            if (rel.endsWith('.css')) {
                for (const m of txt.matchAll(/url\(\s*["']?([^"')]+)["']?\s*\)/g)) {
                    const u = m[1].split(/[?#]/)[0];
                    if (!u || /^(data:|https?:|\/\/|\/)/.test(u)) continue;
                    add(path.posix.normalize(path.posix.join(path.posix.dirname(rel), u)));
                }
            }
        };
        let active = 0;
        const worker = async () => {
            while (true) {
                const r = queue.shift();
                if (r === undefined) { if (active === 0) return; await new Promise((x) => setTimeout(x, 30)); continue; }
                active++;
                try {
                    const ok = await save(slug, r, false);
                    if (ok) followRefs(r); else if (refs.has(r)) miss++;
                } finally { active--; }
            }
        };
        await Promise.all(Array.from({ length: 8 }, worker));
        for (const extra of ['music.mp3', 'preview.jpg']) await save(slug, extra, false);
        console.log(`[${n}/${todo.length}] ${slug}: ${seen.size} arquivos${miss ? ` (${miss} não encontrados, pode ser normal)` : ''}`);
    }
    fs.writeFileSync(manifestFile, JSON.stringify(slugs, null, 2));
    console.log('Pronto. Agora já pode criar/atualizar convites e publicar com segurança.');
})().catch((e) => { console.error('ERRO:', e.message); process.exit(1); });
