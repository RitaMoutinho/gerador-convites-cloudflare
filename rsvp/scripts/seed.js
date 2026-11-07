// Lê guests.txt e gera seed.sql (só a lista de convidados — não mexe nas respostas).
// Uso: node scripts/seed.js
const fs = require('fs');
const path = require('path');

const root = path.join(__dirname, '..');
const norm = (s) => s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().replace(/\s+/g, ' ').trim();
const q = (s) => "'" + String(s).replace(/'/g, "''") + "'";

const guests = [];
for (const line of fs.readFileSync(path.join(root, 'guests.txt'), 'utf-8').split(/\r?\n/)) {
  if (/crian[cç]as\s*=/i.test(line)) continue;           // linha de total
  const m = line.match(/^\s*(\d+)\s*-\s*(.+?)\s*$/);
  if (!m) continue;
  let raw = m[2];
  const kid = /n[ãa]o\s*paga/i.test(raw);
  const ageM = raw.match(/(\d+)\s*anos?/i);
  const age = ageM ? Number(ageM[1]) : null;
  let label = null;
  const lab = raw.match(/^(m[ãa]e|pai)\s*-\s*(.+)$/i);
  if (lab) { label = lab[1].toLowerCase().startsWith('m') ? 'Mãe' : 'Pai'; raw = lab[2]; }
  raw = raw.replace(/\([^)]*n[ãa]o\s*paga[^)]*\)/gi, '')   // "(não paga)"
           .replace(/\d+\s*anos?/gi, '')
           .replace(/\s*-\s*$/, '')
           .replace(/\s+/g, ' ').trim();
  guests.push({ id: Number(m[1]), name: raw, label, kid: kid ? 1 : 0, age, norm: norm(raw) });
}

const ids = new Set(guests.map((g) => g.id));
if (ids.size !== guests.length) throw new Error('numeros repetidos na lista');

const sql = guests.map((g) =>
  `INSERT INTO guests (id,name,label,kid,age,norm) VALUES (${g.id},${q(g.name)},${g.label ? q(g.label) : 'NULL'},${g.kid},${g.age ?? 'NULL'},${q(g.norm)});`
).join('\n') + '\n';
fs.writeFileSync(path.join(root, 'seed.sql'), sql);
console.log(guests.length + ' convidados (' + guests.filter((g) => g.kid).length + ' criancas, ' + guests.filter((g) => !g.kid).length + ' adultos)');
