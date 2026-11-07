// Tira um convite (cf2) do ar SEM apagar nada: move a pasta pra backend/_archived-cf/ e tira do manifesto.
// Uso: node scripts/archive.js <slug> [<slug2> ...]   e depois publicar:  npm run deploy
const fs = require('fs');
const path = require('path');
const { siteRoot, manifestFile, trackedManifest } = require('./lib');

const slugs = process.argv.slice(2);
if (!slugs.length) { console.error('Uso: node scripts/archive.js <slug>'); process.exit(1); }
const archive = path.join(__dirname, '..', '_archived-cf');
fs.mkdirSync(archive, { recursive: true });
const rd = (f) => (fs.existsSync(f) ? JSON.parse(fs.readFileSync(f, 'utf-8')) : []);
let man = rd(manifestFile);
let tracked = rd(trackedManifest);
for (const s of slugs) {
    const from = path.join(siteRoot, s);
    if (!fs.existsSync(from)) { console.log(s + ': não existe em site-cf2'); continue; }
    fs.renameSync(from, path.join(archive, `${s}-${Date.now()}`));
    man = man.filter((x) => x !== s);
    tracked = tracked.filter((x) => x !== s);
    console.log(s + ': arquivado (nada foi apagado)');
}
fs.writeFileSync(manifestFile, JSON.stringify(man, null, 2));
fs.writeFileSync(trackedManifest, JSON.stringify(tracked, null, 2));
