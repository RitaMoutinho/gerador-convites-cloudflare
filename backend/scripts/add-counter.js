// Coloca o contador de acessos (invisível) num convite e publica.
// Uso: node scripts/add-counter.js <slug> [--no-deploy]
// Ver quantas pessoas abriram:  node scripts/count.js <slug>
// Abrir o convite SEM contar:   adicionar ?nocount=1 no final do link.
const fs = require('fs');
const path = require('path');
const { deploy, siteRoot } = require('./lib');

const s = process.argv[2];
if (!s) { console.error('Uso: node scripts/add-counter.js <slug>'); process.exit(1); }
const f = path.join(siteRoot, s, 'index.html');
if (!fs.existsSync(f)) { console.error(`Convite "${s}" não existe em site-cf2. Rode "npm run sync" antes.`); process.exit(1); }
let h = fs.readFileSync(f, 'utf-8');
if (h.includes('digital-convites-rita/' + s)) { console.log('Esse convite já tem contador.'); process.exit(0); }
const blk = `<script>
// Contador de acessos (invisivel). ?nocount=1 ignora.
(function () { try {
    if (/[?&]nocount/.test(location.search)) return;
    if (sessionStorage.getItem('__hit_${s}')) return;
    sessionStorage.setItem('__hit_${s}', '1');
    fetch('https://abacus.jasoncameron.dev/hit/digital-convites-rita/${s}', { keepalive: true }).catch(function () {});
} catch (e) {} })();
</script>
`;
h = h.replace(/(<body[^>]*>)/, '$1' + blk);
fs.writeFileSync(f, h);
console.log('Contador colocado em ' + s);
if (!process.argv.includes('--no-deploy')) deploy();
