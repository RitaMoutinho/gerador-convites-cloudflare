"""
Otimiza e ajusta a cabine JÁ EXISTENTE (não recria nada do zero).

Entrada : out/cabine_clps_ORIGINAL_backup.blend (cópia de segurança, nunca é sobrescrita)
Saída   : out/cabine_clps_otimizada.blend

O que faz
 1. Remove o astronauta (DEC_Astronauta_*) e os dados órfãos que eram só dele.
 2. Terra atrás, Lua em primeiro plano (esfera LUA_Esfera nova), com profundidade.
 3. Otimização guiada por medição (ver README): atmosfera sem Mix Shader estocástico,
    luzes de preenchimento sem sombra, Bevel node mais barato, Cycles/viewport com denoise,
    rochas e terreno com menos polígonos.
 4. Reorganiza as COLEÇÕES (objetos NÃO são renomeados).

Uso: blender -b -P otimizar_cabine.py   |   python otimizar_cabine.py   (com o módulo bpy)
"""
import bpy, math, os
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
SRC = os.path.join(HERE, "out", "cabine_clps_ORIGINAL_backup.blend")
DST = os.path.join(HERE, "out", "cabine_clps_otimizada.blend")
bpy.ops.wm.open_mainfile(filepath=SRC)
scene = bpy.context.scene
D = bpy.data
n_obj_antes = len(D.objects)

# ------------------------------------------------------------------ 1. remover astronauta
astro = [o for o in D.objects if o.name.startswith("DEC_Astronauta_")]
meshes_astro = {o.data for o in astro if o.data}
for o in astro:
    D.objects.remove(o, do_unlink=True)
for d in meshes_astro:                       # malhas/curvas que só ele usava
    if d.users == 0:
        (D.meshes if isinstance(d, bpy.types.Mesh) else D.curves).remove(d)
for m in ("TECIDO_Branco", "VISOR_Preto"):   # materiais exclusivos do astronauta
    if m in D.materials and D.materials[m].users == 0:
        D.materials.remove(D.materials[m])
print(f"[1] astronauta removido: {len(astro)} objetos")

# ------------------------------------------------------------------ helpers de câmera (pixel da referência -> mundo)
cam = D.objects["CAM_Principal"]
F = cam.data.lens / cam.data.sensor_width * 1600.0
def P(px, py, d):
    return cam.matrix_world @ Vector(((px - 800) / F * d, -(py - 450) / F * d, -d))

# ------------------------------------------------------------------ 2. Terra atrás, Lua na frente
# Terra: mais longe, menor, deslocada pra cima/direita da Lua (parcialmente atrás dela)
E_PX, E_PY, E_R_PX, E_DIST = 905, 165, 66, 900.0
e_pos, e_rad = P(E_PX, E_PY, E_DIST), E_R_PX * E_DIST / F
for nm, k in (("TERRA_Esfera", 1.0), ("TERRA_Atmosfera", 1.035)):
    o = D.objects[nm]; o.location = e_pos; o.scale = (e_rad * k,) * 3
# Lua: perto, grande, centro-esquerda da janela
M_PX, M_PY, M_R_PX, M_DIST = 770, 215, 115, 180.0
m_pos, m_rad = P(M_PX, M_PY, M_DIST), M_R_PX * M_DIST / F
bpy.ops.mesh.primitive_uv_sphere_add(segments=96, ring_count=48, radius=1.0, location=m_pos)
moon = bpy.context.active_object
moon.name = "LUA_Esfera"; moon.data.name = "LUA_Malha"; moon.scale = (m_rad,) * 3
moon.rotation_euler = (math.radians(75), 0, math.radians(200))
moon.data.shade_smooth()
# material: regolito claro com maria escuros + crateras por Voronoi (bump), sem texturas de imagem
mm = D.materials.new("LUA_Superficie"); mm.use_nodes = True
n, l = mm.node_tree.nodes, mm.node_tree.links; b = n["Principled BSDF"]
tc = n.new("ShaderNodeTexCoord")
big = n.new("ShaderNodeTexNoise"); big.inputs["Scale"].default_value = 1.6; big.inputs["Detail"].default_value = 6
l.new(tc.outputs["Object"], big.inputs["Vector"])
rmp = n.new("ShaderNodeValToRGB"); rmp.color_ramp.elements[0].position = 0.42; rmp.color_ramp.elements[0].color = (0.05, 0.048, 0.045, 1)
rmp.color_ramp.elements[1].position = 0.62; rmp.color_ramp.elements[1].color = (0.28, 0.265, 0.245, 1)
l.new(big.outputs["Fac"], rmp.inputs["Fac"]); l.new(rmp.outputs["Color"], b.inputs["Base Color"])
vor = n.new("ShaderNodeTexVoronoi"); vor.feature = "F1"; vor.inputs["Scale"].default_value = 9.0
l.new(tc.outputs["Object"], vor.inputs["Vector"])
vor2 = n.new("ShaderNodeTexVoronoi"); vor2.feature = "F1"; vor2.inputs["Scale"].default_value = 28.0
l.new(tc.outputs["Object"], vor2.inputs["Vector"])
add = n.new("ShaderNodeMath"); add.operation = "ADD"
l.new(vor.outputs["Distance"], add.inputs[0]); l.new(vor2.outputs["Distance"], add.inputs[1])
bp = n.new("ShaderNodeBump"); bp.inputs["Strength"].default_value = 0.55; bp.inputs["Distance"].default_value = 0.05
l.new(add.outputs[0], bp.inputs["Height"]); l.new(bp.outputs["Normal"], b.inputs["Normal"])
b.inputs["Roughness"].default_value = 0.95
moon.data.materials.append(mm)
print(f"[2] Lua r={m_rad:.1f} m a {M_DIST:.0f} m | Terra r={e_rad:.1f} m a {E_DIST:.0f} m")

# ------------------------------------------------------------------ 3. otimizações (todas medidas no README)
# 3a. atmosfera da Terra: troca Mix Shader (estocástico = ruído) por Transparente + Emissão (aditivo, determinístico)
am = D.materials["TERRA_Atmosfera"]; n, l = am.node_tree.nodes, am.node_tree.links
mix = next(x for x in n if x.bl_idname == "ShaderNodeMixShader")
fac_src = mix.inputs[0].links[0].from_socket
em = next(x for x in n if x.bl_idname == "ShaderNodeEmission")
tr = next(x for x in n if x.bl_idname == "ShaderNodeBsdfTransparent")
out = next(x for x in n if x.bl_idname == "ShaderNodeOutputMaterial")
sc = n.new("ShaderNodeMath"); sc.operation = "MULTIPLY"; sc.inputs[1].default_value = 0.8
l.new(fac_src, sc.inputs[0]); l.new(sc.outputs[0], em.inputs["Strength"])
ad = n.new("ShaderNodeAddShader"); l.new(tr.outputs[0], ad.inputs[0]); l.new(em.outputs[0], ad.inputs[1])
l.new(ad.outputs[0], out.inputs[0]); n.remove(mix)
for nm in ("TERRA_Atmosfera",):
    o = D.objects[nm]
    o.visible_diffuse = o.visible_glossy = o.visible_transmission = o.visible_volume_scatter = o.visible_shadow = False
# 3b. luzes de preenchimento: grandes e macias = ruído. Sem sombra (são só preenchimento).
for o in D.objects:
    if o.type == "LIGHT" and o.name.startswith("LUZ_Preench"):
        o.data.use_shadow = False
# 3c. Bevel node (desgaste de borda): 8 -> 4 amostras
for m in D.materials:
    if m.use_nodes:
        for nd in m.node_tree.nodes:
            if nd.bl_idname == "ShaderNodeBevel": nd.samples = 4
# 3d. rochas: variações com 1280 tris -> ~320 (distância mínima 14 m, ninguém vê a diferença). Instâncias já eram linkadas.
import bmesh
for me in D.meshes:
    if me.name.startswith("TER_Rocha_Malha_"):
        bm = bmesh.new(); bm.from_mesh(me)
        bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(8), verts=bm.verts, edges=bm.edges)
        bmesh.ops.triangulate(bm, faces=bm.faces)
        bm.to_mesh(me); bm.free()
        dm = me.users  # só para manter referência
tris_ter_antes = len(D.objects["TER_Superficie_Lunar"].data.polygons)
# 3e. terreno: decimação (anéis distantes eram densos demais; relevo de primeiro plano preservado pela razão moderada)
ter = D.objects["TER_Superficie_Lunar"]
bpy.context.view_layer.objects.active = ter
dm = ter.modifiers.new("Decimar", "DECIMATE"); dm.ratio = 0.5
bpy.ops.object.modifier_apply(modifier=dm.name)
# 3f. Cycles: render e viewport
c = scene.cycles
c.device = "CPU"; c.samples = 64; c.use_adaptive_sampling = True; c.adaptive_threshold = 0.02
c.use_denoising = True; c.denoiser = "OPENIMAGEDENOISE"
c.max_bounces = 5; c.diffuse_bounces = 3; c.glossy_bounces = 3; c.transmission_bounces = 2; c.transparent_max_bounces = 6
c.caustics_reflective = False; c.caustics_refractive = False; c.blur_glossy = 1.0
c.sample_clamp_indirect = 5.0; c.sample_clamp_direct = 0.0
c.preview_samples = 48; c.use_preview_adaptive_sampling = True; c.preview_adaptive_threshold = 0.05
c.use_preview_denoising = True; c.preview_denoiser = "AUTO"; c.preview_denoising_start_sample = 1
# 3g. limpeza de dados órfãos
D.orphans_purge(do_recursive=True)
print("[3] otimizações aplicadas")

# ------------------------------------------------------------------ 4. coleções (só as coleções são renomeadas, objetos não)
root = scene.collection
def col(nm): return D.collections[nm]
ren = {"01_Estrutura_Cabine": "CABINE_ESTRUTURA", "02_Janelas": "JANELAS", "03_Console_Principal": "PAINEL_CONTROLE",
       "04_Monitores": "MONITORES", "05_Controles": "CONTROLES", "06_Objetos_Decorativos": "DECORACOES",
       "07_Terreno_Lunar": "TERRENO_LUNAR", "08_Terra": "TERRA", "09_Ceu": "CEU", "10_Iluminacao": "ILUMINACAO", "11_Cameras": "CAMERAS"}
for old, new in ren.items(): col(old).name = new
ext = D.collections.new("ESPACO_EXTERIOR"); root.children.link(ext)
lua = D.collections.new("LUA"); ext.children.link(lua)
for nm in ("TERRENO_LUNAR", "TERRA", "CEU"):
    root.children.unlink(col(nm)); ext.children.link(col(nm))
root.children.unlink(col("CONTROLES")); col("PAINEL_CONTROLE").children.link(col("CONTROLES"))
for c_ in list(moon.users_collection): c_.objects.unlink(moon)
lua.objects.link(moon)
print("[4] coleções:", [c_.name for c_ in root.children])

# ------------------------------------------------------------------ validação
faltando = [o.name for o in D.objects if o.users == 0]
print(f"[V] objetos antes={n_obj_antes} depois={len(D.objects)} (−{len(astro)} astronauta, +1 Lua) | sem uso={faltando}")
mats_sem_nodes = [m.name for m in D.materials if not m.use_nodes]
print("[V] materiais sem nós:", mats_sem_nodes)
tris = sum(len(p.vertices) - 2 for o in D.objects if o.type == "MESH" for p in o.data.polygons)
print(f"[V] triângulos totais (contando instâncias): {tris} | terreno {tris_ter_antes} -> {len(ter.data.polygons)} polígonos")
bpy.ops.wm.save_as_mainfile(filepath=DST)
print("[V] salvo em", DST)
