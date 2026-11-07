# Convite de vídeo (música + passa os vídeos sozinho + para numa página)

Fluxo: clica na capa → começa a música (toca o convite todo) → passa sozinho pelas páginas de vídeo → para numa página interativa.
Bloco pronto (áudio + script) para colar logo depois do `<body>`: `docs/video-sequence-block.html` (exemplo real: convite Cecilia XV).

## Pedido da Rita (modelo)
> Convite de vídeo, [CRIAR NOVO a partir de `<link do Canva>`] ou [ATUALIZAR `<link publicado>` a partir de `<link do Canva>`].
> Capa: `<arquivo>` · Nome/título: `<Ex: Ana Clara XV>` · Música: `<arquivo.mp3>`
> Páginas: 1 capa/intro (clicar começa a música); páginas [__] vídeo(s) passam automático; **para na página [__]**.

## Spec (já resolvido, não redescobrir)
1. Re-scrape via `/api/update` (ou `/api/deploy` se novo). **O scrape SOBRESCREVE o `index.html`**: faça backup antes e depois reaplique o bloco custom no lugar do player simples.
2. Música começa no 1º clique/toque (gesto do usuário). Mesmo `<audio loop>` o convite todo.
3. Navegação: `history.pushState({key:<rand>}, '', alvo)` + `dispatchEvent(new PopStateEvent('popstate',{state:{key:<rand>}}))`. O objeto `{key}` é obrigatório (com `null` o roteador do Canva ignora).
4. NÃO forçar a 1ª troca (intro → pág 2): o clique nativo do Canva já faz. Assumir só a troca seguinte.
5. Rótulos de rota do Canva NÃO são sequenciais: achar no `index.html` a lista `"g":[{...,"L":"page-X"},...]` (ordem do array = ordem das páginas, `"L":""` = intro) e usar o `"L"` da página-alvo como caminho (ex.: a 3ª pode ser `page-5`). O bloco usa `/page-3` por padrão: AJUSTE.
6. Fim do vídeo: só LER `v.duration`/`currentTime` (nunca escrever, já causou navegação infinita). Sair ~0,9s antes do fim (`dur - t < 0.9 && t > 1`), com fallbacks: evento `ended`, pulo pra trás (`t + 1 < lastT`), teto `dur + 4s`.
   - **Medir cada convite**: alguns clipes do Canva reiniciam (loop) ANTES do fim real do arquivo (ex.: Cecilia reinicia em ~6,35 s, arquivo de 7,93 s). Amostre `currentTime` a cada 40 ms e, se houver loop cedo, adicione `if (t >= <tempo do loop - 0.45>) return finish();`.
7. Fade PRETO sólido entre páginas (nunca blur/vidro/opacity): intro→vídeo fade LONGO (`coverHide(1100)`, forçar o preto no clique); vídeo→página de parada fade curto (~0,3 s total).
8. Título: trocar `<title>` e `og:title` pro nome pedido e travar com MutationObserver (o Canva reescreve `document.title`).
9. Texto "ok" solto no design vira `<h1>ok</h1>` no fundo: remover com MutationObserver.
10. `sessionStorage` (chave `__ac_seq_step`) guarda o passo pra sobreviver a reload.
11. Capa: ver regra no `CLAUDE.md` (capa vertical mantém o tamanho original).
12. Teste de verdade é no celular da Rita; o navegador automatizado bloqueia autoplay (use `v.muted=true; v.play()` só pra medir tempos).
