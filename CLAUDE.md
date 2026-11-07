# Gerador de Convites (versão Cloudflare, pra usar em qualquer computador)

Leia isto inteiro antes de mexer em qualquer coisa. A dona é a Rita (fala português informal; responda em português, curto e direto).
Primeiro uso num computador novo: siga o `SETUP.md` (login do Cloudflare + `npm run sync`).

## O que o projeto faz
Pega um site do **Canva** (`https://seemg.my.canva.site/...`) e publica como convite com **link próprio**, **prévia bonita no WhatsApp**, e opcionalmente **música**, **contador de acessos** e **sequência de vídeo**.

- `frontend/` formulário React (Vite, porta **5173**): abas "Criar novo" e "Atualizar existente".
- `backend/server.js` Express + Puppeteer (porta **4000**): raspa o Canva, limpa os artefatos, publica.
- `rsvp/` site SEPARADO de confirmação de presença (Cloudflare Worker + D1). Ver `rsvp/README.md`.

## HOSPEDAGEM: É CLOUDFLARE PAGES. NÃO É VERCEL. (a Rita já ficou brava com isso)
- Convites NOVOS vão pro projeto `digital-convites-cf3` → `https://digital-convites-cf3.pages.dev/<slug>/`, pasta local `backend/site-cf3/<slug>/`.
- Cada convite é só uma pasta dentro de UM site único. **Cada deploy publica a PASTA INTEIRA** (`backend/site-cf3`): o que não estiver nela sai do ar.
- O `cf3` é um projeto NOVO, criado só pra este repositório (a Rita vai viajar e usa este gerador em outro computador). Ele começa VAZIO: não precisa baixar nada pra começar.
- Se este gerador for usado em mais de um computador, em cada um: antes de trabalhar `git pull` e `npm run sync` (em `backend/`, baixa os convites cf3 listados em `backend/manifests/cf3.json`); ao terminar `git add -A && git commit && git push` (a lista é atualizada sozinha a cada convite novo). A trava do servidor e dos scripts BLOQUEIA o deploy se faltar convite que a lista conhece.
- Convites antigos (projetos `digital-convites-cf2` e `digital-convites-cf`, e Vercel) **não são deste repositório e só podem ser mexidos no computador de casa** (pasta `Gerador Convites`). Se ela pedir pra mexer num deles daqui, avise que só dá lá. `/api/update` aqui só acha convites do cf3.
- Limite do plano grátis: 20.000 arquivos por projeto e 25 MB por arquivo. Se o cf3 chegar perto de 20.000, criar um projeto 4.
- Publicar à mão: `cd backend && npm run deploy` (equivale a `npx wrangler pages deploy . --project-name digital-convites-cf3 --branch main --commit-dirty=true` dentro de `site-cf3`).
- Login: `npx wrangler login` uma vez por computador (ou variável `CLOUDFLARE_API_TOKEN`).

## Rodar no dia a dia
```bash
cd backend && npm start        # porta 4000
cd frontend && npm run dev     # porta 5173
```
Se aparecer "Erro ao processar e publicar o convite": 1) confira `netstat -ano | grep :4000`; 2) se o backend estava ligado há muito tempo, **reinicie** (já travou assim); 3) rode `cd backend/site-cf3 && npx wrangler pages deploy . --project-name digital-convites-cf3 --branch main --commit-dirty=true` na mão pra ver o erro real. A resposta da API traz `details` com status/signal.
No Windows/Git Bash, `robocopy` e flags com `/` quebram: use PowerShell pra isso. `sleep` longo no terminal é bloqueado: use verificação em loop.

## Pedidos comuns da Rita (e o que fazer)
Sempre termine confirmando que subiu: `curl` no link (o Cloudflare devolve 200 + HTML de 12 bytes pra arquivo que não existe, então confira `content-type` e tamanho) e diga o link.

| Pedido | Como |
|---|---|
| "Cria convite novo com esse link do Canva" | Backend ligado → `POST http://localhost:4000/api/deploy` (multipart: `canvaUrl`, `nome`, `idade`, `previewImage` opcional) ou pela tela. O slug sai `nome-idade-numero`. Entra sozinho no manifesto. |
| "Atualiza (fiz mudanças no Canva)" | `POST /api/update` com `link` (o link publicado) + `canvaUrl`. Mantém o mesmo link, `preview.jpg` e `music.mp3`. **A raspagem apaga o contador** (e o bloco de vídeo): recoloque depois se tinha. Um convite com música continua com música. |
| "Coloca a música do convite A no B" | `node scripts/add-music.js <slugB> --from <slugA>` (copia `music.mp3` + player e publica). Se A não tem `music.mp3`, **não chute**: pergunte qual música. |
| "Coloca essa música (arquivo mp3) no convite" | `node scripts/add-music.js <slug> "<caminho.mp3>"`. Toca em loop a partir do 1º toque. Música curta já fica em loop. Trocar música = mesmo comando. |
| "Coloca contagem / vê quantos entraram" | `node scripts/add-counter.js <slug>` e `node scripts/count.js <slug>`. "0 acessos"/"Key not found" = zero. Abrir sem contar: `?nocount=1`. Só conta a partir de quando foi colocada. |
| "Tira do ar" | `node scripts/archive.js <slug>` e `npm run deploy`. **NUNCA** `rm -rf` direto. Move pra `backend/_archived-cf/`. |
| "Capa" | A capa é o `preview.jpg` + metas `og:image`. O servidor sempre redimensiona pra **1366x768** (cover). **Capa vertical/diferente do padrão: manter o tamanho ORIGINAL** (copie o arquivo e ajuste `og:image:width/height`). A Rita já reclamou de capa cortada. |
| "WhatsApp não mostra a capa nova" | Cache do WhatsApp: mande o link com `?v=2` no final. |
| Convite de vídeo (clica na capa → música → passa os vídeos sozinho → para numa página) | Ver `docs/video-sequence.md` e o bloco pronto `docs/video-sequence-block.html`. |

## O que o pipeline de raspagem faz (`scrapeConvite` em `backend/server.js`). NÃO regrida nenhum
1. Remove a faixa "Criado com o Canva" e **nunca espelha o endpoint `/_footer`** (o JS do Canva reinjetaria a faixa).
2. Imagens `blob:` viram arquivos reais (`_assets/blob/`).
3. URLs absolutas do domínio do Canva viram relativas.
4. Assets "lazy": varre todo texto atrás de `_assets/...` e baixa o que faltar.
5. Remove `og:*` duplicadas do Canva antes de injetar as nossas (WhatsApp lê a primeira).
6. `og:image` 1366x768 via sharp (`fit: cover`).
7. `<base href="/<slug>/">`.
8. Preload de imagem principal e fontes.
9. Tela de carregamento **discreta** (fundo liso, sem spinner): a Rita pediu assim, não trocar.
10. Música: se existir `music.mp3` na pasta, reinjeta o player a cada re-raspagem. Toca no 1º clique/toque (`click` capture).
11. **NÃO** tente destravar o som de `<video>` do Canva automaticamente: já quebrou um convite (tela branca). Vídeos tocam mudos; é o comportamento aceito.

## Restaurar / baixar convites do site publicado
`npm run sync -- <slug>` rebaixa um convite. Ele usa a **regex ampla** `/_assets\/[a-zA-Z0-9_\-.\/]+\.[a-zA-Z0-9]+/g` no HTML, não só `src=`/`href=` (várias imagens ficam só dentro dos blocos de dados do Canva; só `src/href` já perdeu arquivos em restauração real).

## Zoom/proporção errada num convite
Compare com o Canva ORIGINAL (`getBoundingClientRect()` vs `naturalWidth`). Se o zoom já está no original, o problema é o design no Canva (corrigir lá e rodar `/api/update`), não a hospedagem.

## RSVP (confirmação de presença)
Projeto separado em `rsvp/` (Worker + D1, conta fizz-site.workers.dev). Só convidados da lista conseguem confirmar; painel em `/admin.html`. Instruções completas em `rsvp/README.md`. Dados de convidados ficam no D1 remoto (`guests.txt` é só a origem).

## Regras de ouro (aprendidas na marra)
- Nunca apagar convite; sempre arquivar (`scripts/archive.js`).
- Nunca publicar sem os convites antigos na pasta (a trava impede; não contorne).
- Não testar com som alto nem deixar aba do navegador aberta tocando música.
- Não inventar avaliações/fotos de banco nos sites da Rita.
- Antes de commit/push ou qualquer ação que publique algo novo além do pedido, pergunte.
