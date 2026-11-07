# Confirmação de presença (site à parte)

- Convidados: `https://convite-presenca.fizz-site.workers.dev/`
- Painel: `https://convite-presenca.fizz-site.workers.dev/admin`  (sem senha; para proteger: `npx wrangler secret put ADMIN_PASSWORD`)

Só quem está na lista (`guests.txt`) consegue confirmar. Respostas ficam no banco D1 `convite-presenca`.

## Trocar textos (título, mensagens)
Edite `public/config.js` e rode `npx wrangler deploy`.

## Trocar a lista de convidados
1. Edite `guests.txt` (um por linha: `12 - Nome`; criança sem pagar: `13 - Nome (não paga) 5 anos`).
2. `node scripts/seed.js`
3. Para recomeçar do zero (APAGA as respostas): `npx wrangler d1 execute convite-presenca --remote --file=schema.sql` e depois `--file=seed.sql`.

## Trocar a senha do painel
`npx wrangler secret put ADMIN_PASSWORD`

## Publicar
`npx wrangler deploy`
