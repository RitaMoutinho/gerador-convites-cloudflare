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
