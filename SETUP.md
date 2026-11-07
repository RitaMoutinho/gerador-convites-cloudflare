# Como usar o gerador em outro computador (só fazer login)

Você precisa: **Windows/Mac com Node.js 20+ e Git** instalados, e as contas **GitHub** e **Cloudflare** (as mesmas de sempre).

## 1. Baixar e instalar (uma vez)
```bash
git clone https://github.com/RitaMoutinho/gerador-convites-cloudflare.git
cd gerador-convites-cloudflare
cd backend && npm install && cd ..
cd frontend && npm install && cd ..
```
(O `npm install` do backend baixa o Chrome do Puppeteer, demora uns minutos.)

## 2. Logins (uma vez por computador)
```bash
gh auth login            # GitHub (se for usar o gh)
cd backend
npx wrangler login       # abre o navegador: entre na conta Cloudflare de sempre
```

## 3. Baixar os convites já publicados (uma vez; pode levar um tempo)
```bash
cd backend
npm run sync
```
Isso copia do site publicado todos os convites novos (cf2) pra pasta `backend/site-cf2`. **Não pule:** o Cloudflare publica a pasta inteira, então sem isso os convites antigos sairiam do ar. Se tentar publicar sem o sync, o sistema BLOQUEIA e avisa.

## 4. Ligar o gerador
```bash
# terminal 1
cd backend && npm start         # porta 4000
# terminal 2
cd frontend && npm run dev      # porta 5173
```
Abra http://localhost:5173.

## 5. Se você usa o Claude Code
Abra o Claude Code **dentro dessa pasta**: ele lê o `CLAUDE.md` e já sabe tudo (música, contador, capa, vídeo, tirar do ar). É só pedir do jeito de sempre, por exemplo:
- "coloca a música do convite X nesse Y"
- "atualiza, fiz mudanças no Canva: <link do Canva> <link do convite>"
- "coloca contagem nesse convite"

## Importante
- **Convites antigos** (projeto `digital-convites-cf` e os da Vercel) **só podem ser mexidos no computador de casa.** Aqui só os novos (`digital-convites-cf2`).
- Ao criar convite novo em outro computador, mande o código pro GitHub no fim (`git add -A && git commit -m "novo convite" && git push`) pra a lista `backend/manifests/cf2.json` ficar em dia. Senão, o computador de casa não sabe que ele existe e o `npm run sync` de lá não baixa ele. Se esquecer, no de casa dá pra rodar `npm run sync -- <slug>`.
- Os arquivos dos convites (`site-cf2`) **não vão pro GitHub** de propósito (são grandes); a cópia de verdade é a do site publicado.
- O arquivo `backend/.env` não é necessário (os endereços já têm padrão). Se quiser mudar, copie `backend/.env.example` para `backend/.env`.
