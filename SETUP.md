# Como usar o gerador em outro computador (só fazer login)

Você precisa: **Windows/Mac com Node.js 20+ e Git** instalados, e as contas **GitHub** e **Cloudflare** (as mesmas de sempre).

Este gerador publica num projeto do Cloudflare Pages **só dele**: `digital-convites-cf3` → links `https://digital-convites-cf3.pages.dev/<convite>/`. Ele começa vazio, então **não precisa baixar nenhum convite antigo**. Os convites antigos (`cf2`, `cf` e Vercel) continuam intactos e só são mexidos no computador de casa.

## 1. Baixar e instalar (uma vez)
```bash
git clone https://github.com/RitaMoutinho/gerador-convites-cloudflare.git
cd gerador-convites-cloudflare
cd backend && npm install && cd ..
cd frontend && npm install && cd ..
```
(O `npm install` do backend baixa o Chrome do Puppeteer, demora uns minutos.)

## 2. Login do Cloudflare (uma vez por computador)
```bash
cd backend
npx wrangler login       # abre o navegador: entre na conta Cloudflare de sempre
```

## 3. Ligar o gerador
```bash
# terminal 1
cd backend && npm start         # porta 4000
# terminal 2
cd frontend && npm run dev      # porta 5173
```
Abra http://localhost:5173, cole o link do Canva e gere o convite.

## 4. Se você usa o Claude Code
Abra o Claude Code **dentro dessa pasta**, entre com a sua conta do Claude: ele lê o `CLAUDE.md` e já sabe tudo (música, contador, capa, vídeo, tirar do ar). É só pedir do jeito de sempre, por exemplo:
- "sobe esse convite: <link do Canva>"
- "coloca a música do convite X nesse Y"
- "atualiza, fiz mudanças no Canva: <link do Canva> <link do convite>"
- "coloca contagem nesse convite"

## Importante
- **Convites novos só entram no `cf3`.** Os links antigos (`...cf2.pages.dev`, `...cf.pages.dev`, vercel) não são mexidos por aqui.
- **Se usar este gerador em DOIS computadores:** antes de começar rode `git pull` e `npm run sync` (baixa os convites `cf3` feitos no outro computador); quando terminar, `git add -A && git commit -m "novos convites" && git push`. Sem isso, o computador que não sabe dos convites do outro tira eles do ar ao publicar (o sistema bloqueia e avisa quando conhece a lista).
- Se só usar um computador, nada disso é preciso.
- Os arquivos dos convites (`site-cf3`) **não vão pro GitHub** de propósito; a cópia de verdade é a do site publicado.
- O arquivo `backend/.env` não é necessário (os endereços já têm padrão). Se quiser mudar, copie `backend/.env.example` para `backend/.env`.
