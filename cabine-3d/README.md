# Cabine CLPS 3D — Fase 1 (só a nave)

Reconstrução 3D da imagem de referência (cabine lunar retrofuturista). **Não** inclui o site nem as interfaces dos monitores.

## Como abrir
- Abrir `out/cabine_clps.blend` no Blender 4.2+ (gerado e testado no 5.3), ou
- Regenerar do zero no seu Blender: *Scripting → Open → `build_cabine.py` → Run Script*.
- Linha de comando: `blender -b -P build_cabine.py -- --render --all --glb --samples 96`
- Sem Blender instalado: `pip install bpy` e `python build_cabine.py --render` (foi assim que foi feito aqui).

Opções: `--scale 0.5` (resolução), `--samples N`, `--exposure X`, `--all` (renderiza as câmeras extras), `--glb` (exporta GLB), `--out pasta`.

## O que foi produzido de verdade
- Cena 3D real (geometria + materiais procedurais PBR + luzes + câmeras), tudo gerado por `build_cabine.py`.
- Posicionamento a partir de **pixels da referência + profundidade** (função `P(px, py, d)`), então a câmera `CAM_Principal` reproduz o enquadramento (28 mm, olhos a 1,0 m, inclinada 5,5° pra baixo).
- Coleções: `01_Estrutura_Cabine`, `02_Janelas`, `03_Console_Principal`, `04_Monitores`, `05_Controles`, `06_Objetos_Decorativos`, `07_Terreno_Lunar`, `08_Terra`, `09_Ceu`, `10_Iluminacao`, `11_Cameras`.
- Monitores (Central, Direito, Esquerdo): moldura em 4 peças + caixa traseira + cantoneiras + parafusos, e a **tela é um objeto separado** (`SCR_*_Tela`), escura com leve brilho verde, sem texto/UI — pronta para receber a interface por código.
- Terreno lunar: malha polar real (57 mil vértices, alta resolução perto, barata longe) com crateras e montanhas distantes + 260 rochas instanciadas (10 variações).
- Terra: esfera independente (textura procedural + atmosfera azul separada). Céu: World procedural com estrelas.
- Decorativos: astronauta miniatura (~15 cm) com logo NASA, luminária âmbar, caneca com logo NASA, joystick, botões iluminados, cabos.
- Câmeras: `CAM_Principal`, `CAM_Monitor_Central` (frontal), `CAM_Aux_Esquerda`, `CAM_Aux_Direita`, `CAM_Aux_Visao_Geral`.

## Estratégia escolhida
**Do zero (A)**: nenhum `.ply` ou `.glb` foi anexado, então não houve como avaliar os arquivos existentes. Quando você mandar a janela (`.ply`) e o joystick (`.glb`) eu avalio: o `.ply` provavelmente é Gaussian Splatting (não é malha, não serve como estrutura editável); o joystick pode substituir o `CTL_Joystick_*` se estiver bem modelado.

## Arquivos
- `build_cabine.py` — script completo.
- `out/cabine_clps.blend` — cena.
- `out/render_principal.png` — render da câmera principal (1600×900).
- `out/render_aux_*.png`, `out/render_monitor_central.png` — outros ângulos.
- `out/comparacao.png` — referência × render (lado a lado, overlay e diferença).
- `out/cabine_clps.glb` — exportação de teste (geometria + materiais básicos).

## O que ainda NÃO está pronto (honestamente)
- Os textos/HUD da imagem (CLPS, logo/legenda “Space Apps”, “Modo exploração”, “Polo Sul da Lua”) são UI de sobreposição e foram deixados de fora de propósito (serão do site).
- Fidelidade ainda aproximada: não tem bloom/glow de pós-processamento, os detalhes mecânicos do console (fiação, painéis, grelhas) estão mais simples que na referência, o terreno é menos rico em textura/relevo e a Terra é procedural (não tem textura real).
- Materiais são procedurais do Cycles: **não exportam para GLB**. Para o site é preciso: UV unwrap, bake (cor, rugosidade/metal, normal, AO e iluminação pré-calculada) e reaplicar como PBR com imagens; depois compressão Draco/KTX2.
- Os logos NASA são aproximações (disco azul + texto + órbita), não o arquivo oficial.
- Não foi feita otimização de polígonos (terreno e rochas são o que mais pesa) nem LODs.
- Etapa 8 (preparar para Three.js/R3F) só começou com o GLB de teste.

## Próximos passos sugeridos
1. Você revisa `render_principal.png` / `comparacao.png` e aponta o que está mais longe da referência.
2. Refinar console, vigas e iluminação (a parte que mais pesa na semelhança).
3. Anexar o `.ply`/`.glb` para avaliação técnica.
4. Bake + exportação GLB otimizada.

---
## Atualização: astronauta removido, Lua + Terra, otimização (`otimizar_cabine.py`)
Roda sobre `out/cabine_clps_ORIGINAL_backup.blend` (cópia intocada) e gera `out/cabine_clps_otimizada.blend`.

- **Astronauta:** 16 objetos removidos (inclui o logo NASA do traje, que era só dele) + materiais órfãos. Caneca/logo NASA da caneca, luminária e demais decorações intactos.
- **Composição:** `LUA_Esfera` (raio ~16,6 m a 180 m, centro-esquerda da janela) em primeiro plano; Terra a 900 m, menor, acima/direita e parcialmente atrás da Lua.
- **Origem do ruído (medida, 2 sementes sem denoise):** casca da atmosfera da Terra (Mix Shader estocástico) ≈ −30% de ruído ao remover; luzes de preenchimento grandes com sombra ≈ −23%; Bevel node não gera ruído mas custava ≈ 20% do tempo. Geometria e céu **não** eram a causa. O ruído do viewport vinha de preview 1024 amostras **sem** denoise.
- **Correções:** atmosfera = Transparente + Emissão (aditivo); fills sem sombra; Bevel 8→4 amostras; rochas ~1280→~320 tris; terreno 56,7 mil→33,3 mil polígonos (decimação 50%); Cycles 64 amostras adaptativas + OIDN, caustics off, clamp indireto 5; viewport 48 amostras + denoise.
- **Resultado (800×450, denoise):** 106,9 s → 71,6 s (−33%); ruído a 16 amostras 0,0737 → 0,0495 (−33%) mesmo com a Lua nova na cena.
- **Coleções:** CABINE_ESTRUTURA, JANELAS, PAINEL_CONTROLE (+CONTROLES), MONITORES, DECORACOES, ESPACO_EXTERIOR (+TERRENO_LUNAR, TERRA, LUA, CEU), ILUMINACAO, CAMERAS. Objetos não foram renomeados.
- **Texturas:** a cena não usa imagens (tudo procedural), então não havia textura pesada pra reduzir.
- **Joystick `.glb` anexado:** NÃO foi usado. Tem 281 mil vértices e 2 texturas WebP (~13 MB), pesado demais pra web; o joystick atual da cena tem poucas centenas de polígonos.

---
## Atualização v3: refino visual e estrutural (`refinar_cabine.py`)
Roda sobre `out/cabine_clps_v2_backup.blend` (cópia intocada) e gera `out/cabine_clps_v3.blend`. Precisa do joystick: `--joy caminho/modelojoystick.glb`.

- **Monitor esquerdo:** removida `CON_Carcaca_Esquerda` (a caixa que engolia a tela); caixa traseira 20→8 cm; tampa superior fina (a luminária apoia nela); pedestal + sapata.
- **Três monitores:** pedestal e sapata aparafusada na bancada, aro interno escuro em volta da tela. As telas `SCR_*_Tela` não foram tocadas.
- **Botões:** os 18 blocos antigos saíram. Novos: aro metálico com cavidade, fundo escuro, tecla de cantos arredondados 2 mm abaixo do aro, em placas por grupo, sobre um painel inclinado ~19° pro usuário (`CON_Console_Botoes`). Âmbar ×2 (auxiliares), verde ×3 (principais), branco ×2 (secundários), vermelho ×1 (alerta). Indicadores laterais âmbar encaixados na bancada.
- **Lua/Terra:** havia uma só de cada (sem duplicação). Lua menor, à esquerda, a 180 m; Terra a 900 m, acima e à direita.
- **Joystick:** o "vaso" era o joystick provisório (`CTL_Joystick_*`), removido. Instalado o `.glb` fornecido (`JOY_Joystick`, geometria e texturas originais, escala 0,165) num soquete nivelado e aparafusado.
- **Soltos/sem função:** 5 `CAB_Suporte_*` atravessavam bancada e monitores (um era o bloco sob o monitor central) → removidos, função assumida pelos pedestais. Grelha esquerda solta (o bloco retangular perto do vaso) → removida. Grelha direita, interruptores, cabos e caneca → reassentados na bancada.
- **Bancada:** frisos de transição no fundo e na borda frontal, juntas discretas dos módulos, chanfro maior.
- **Materiais:** tela menos espelhada, piso de rugosidade nos metais, lâmpadas âmbar sem estourar em branco.
- **Granulado:** as causas reais foram medidas e corrigidas na v2 (atmosfera da Terra e luzes de preenchimento); o que sobra no viewport é só baixa amostragem, resolvida pelo denoise.
- **Coleções:** CABINE_ESTRUTURA (+JANELAS), PAINEL_CONTROLE, BOTOES, MONITORES, JOYSTICK, DECORACOES, LUA, TERRA, CENARIO_ESPACIAL (+TERRENO_LUNAR, CEU), ILUMINACAO, CAMERAS.
- Renders: `out/v3_principal.png`, `out/v3_superior.png`, `out/v3_close_esquerda.png`, `out/v3_close_botoes.png`.
