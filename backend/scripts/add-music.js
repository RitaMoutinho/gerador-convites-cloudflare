// Coloca música de fundo num convite (cf3) e publica.
// Uso: node scripts/add-music.js <slug> <caminho/da/musica.mp3>
//  ou: node scripts/add-music.js <slug> --from <slug-de-outro-convite>   (copia a música de outro convite)
// Acrescente --no-deploy pra só preparar sem publicar.
// Toca em loop a partir do primeiro toque/clique na página (sem gesto do usuário o navegador não deixa tocar).
const fs = require('fs');
const path = require('path');
const { deploy, siteRoot, verifyAudio } = require('./lib');

const argv = process.argv.slice(2);
const slug = argv[0];
const fromIdx = argv.indexOf('--from');
if (!slug || (fromIdx === -1 && (!argv[1] || argv[1].startsWith('--')))) {
    console.error('Uso: node scripts/add-music.js <slug> <musica.mp3>   |   <slug> --from <outro-slug>');
    process.exit(1);
}
const dir = path.join(siteRoot, slug);
if (!fs.existsSync(dir)) { console.error(`Convite "${slug}" não existe em site-cf3. Rode "npm run sync" antes.`); process.exit(1); }

const src = fromIdx !== -1 ? path.join(siteRoot, argv[fromIdx + 1], 'music.mp3') : path.resolve(argv[1]);
if (!fs.existsSync(src)) { console.error('Arquivo de música não encontrado: ' + src); process.exit(1); }

fs.copyFileSync(src, path.join(dir, 'music.mp3'));
const f = path.join(dir, 'index.html');
let h = fs.readFileSync(f, 'utf-8');
if (/id="__bgm"/.test(h)) {
    console.log('Esse convite já tem o player: só troquei o arquivo music.mp3.');
} else {
    const blk = '<audio id="__bgm" src="music.mp3" loop preload="metadata"></audio>\n' +
        "<script>(function(){var started=false;function tryPlay(){if(started)return;var a=document.getElementById('__bgm');if(!a)return;a.play().then(function(){started=true}).catch(function(){})}document.addEventListener('click',tryPlay,true);window.addEventListener('hashchange',tryPlay);})();</script>";
    h = h.replace(/(<body[^>]*>)/, '$1\n' + blk);
    fs.writeFileSync(f, h);
}
console.log('Música colocada em ' + slug);
if (!argv.includes('--no-deploy')) {
    deploy();
    verifyAudio(slug, fs.statSync(path.join(dir, 'music.mp3')).size);
}
