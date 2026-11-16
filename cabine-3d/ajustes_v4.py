"""
Ajustes finais sobre a cabine EXISTENTE (não reconstrói, não otimiza).

Entrada : out/cabine_clps_v3_backup.blend (cópia de segurança da v3, não é sobrescrita)
Saída   : out/cabine_clps_v4.blend

1. Lua menor e à esquerda; Terra atrás, parcialmente encoberta (acima/direita).
2. "Luminárias laterais": eram REFLEXOS das lâmpadas superiores nos vidros -> reflexo desligado;
   no lugar, faixas de LED âmbar embutidas nas vigas, simétricas.
3. Mini rádio comunicador à esquerda da bancada.
4. Alça da caneca refeita (curva suave, espessura uniforme, duas junções).

Uso: blender -b -P ajustes_v4.py
"""
import bpy, bmesh, math, os
from mathutils import Vector, Matrix

HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
SRC = os.path.join(HERE, "out", "cabine_clps_v3_backup.blend")
DST = os.path.join(HERE, "out", "cabine_clps_v4.blend")
bpy.ops.wm.open_mainfile(filepath=SRC)
scene = bpy.context.scene; D = bpy.data; MAT = D.materials
cam = D.objects["CAM_Principal"]
F = cam.data.lens / cam.data.sensor_width * 1600.0
CAM_LOC = cam.matrix_world.translation.copy(); INV = cam.matrix_world.inverted()
def P(px, py, d): return cam.matrix_world @ Vector(((px - 800) / F * d, -(py - 450) / F * d, -d))
def PX(p):
    q = INV @ Vector(p); d = -q.z
    return round(800 + q.x / d * F), round(450 - q.y / d * F), round(d, 1)
n_antes = len(D.objects)

# ---------------------------------------------------------------- helpers
def mesh_from(name, verts, faces):
    me = D.meshes.new(name); me.from_pydata([tuple(v) for v in verts], [], faces); me.update()
    bm = bmesh.new(); bm.from_mesh(me); bmesh.ops.recalc_face_normals(bm, faces=bm.faces); bm.to_mesh(me); bm.free()
    return me
def box_mesh(name, sx, sy, sz):
    hx, hy, hz = sx / 2, sy / 2, sz / 2
    v = [(-hx, -hy, -hz), (hx, -hy, -hz), (hx, hy, -hz), (-hx, hy, -hz), (-hx, -hy, hz), (hx, -hy, hz), (hx, hy, hz), (-hx, hy, hz)]
    return mesh_from(name, v, [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)])
def basis(x, z):
    x = Vector(x).normalized(); z = Vector(z); z = (z - x * z.dot(x)).normalized(); y = z.cross(x)
    return Matrix(((x.x, y.x, z.x, 0), (x.y, y.y, z.y, 0), (x.z, y.z, z.z, 0), (0, 0, 0, 1)))
def finish(ob, bevel=0.003, seg=2):
    ob.data.shade_smooth()
    if bevel:
        b = ob.modifiers.new("Bisel", "BEVEL"); b.width = bevel; b.segments = seg; b.limit_method = "ANGLE"; b.angle_limit = math.radians(35)
    w = ob.modifiers.new("NormaisPonderadas", "WEIGHTED_NORMAL"); w.keep_sharp = True
    return ob
def obox(name, center, xdir, zdir, size, mat, col, bevel=0.003, seg=2):
    ob = D.objects.new(name, box_mesh(name, *size)); col.objects.link(ob); ob.data.materials.append(mat)
    m = basis(xdir, zdir); m.translation = Vector(center); ob.matrix_world = m
    return finish(ob, bevel, seg)
def cyl(name, center, axis, radius, depth, mat, col, seg=24):
    bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=radius, radius2=radius, depth=depth)
    me = D.meshes.new(name); bm.to_mesh(me); bm.free(); me.shade_smooth(); me.materials.append(mat)
    ob = D.objects.new(name, me); col.objects.link(ob)
    m = basis(Vector(axis).orthogonal(), axis); m.translation = Vector(center); ob.matrix_world = m
    return finish(ob, 0.0012, 2)
def bolt(name, pos, nrm, col, r=0.004):
    ob = D.objects.new(name, D.meshes["MalhaParafuso"]); col.objects.link(ob)
    m = basis(Vector(nrm).orthogonal(), nrm) @ Matrix.Scale(r, 4); m.translation = Vector(pos); ob.matrix_world = m
def mat_simple(name, color, rough, emit=None, strength=0.0, coat=0.0):
    m = MAT.new(name); m.use_nodes = True; b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = tuple(color) + (1,); b.inputs["Roughness"].default_value = rough; b.inputs["Coat Weight"].default_value = coat
    if emit: b.inputs["Emission Color"].default_value = tuple(emit) + (1,); b.inputs["Emission Strength"].default_value = strength
    return m
OLIVE, OLIVE_D, DARK, STEEL = MAT["MET_Oliva_Envelhecido"], MAT["MET_Oliva_Escuro"], MAT["MET_Preto_Tecnico"], MAT["MET_Aco_Escovado"]
UP = Vector((0, 0, 1)); X = Vector((1, 0, 0))
if "BORRACHA_Preta" not in MAT: mat_simple("BORRACHA_Preta", (0.015, 0.015, 0.016), 0.55, coat=0.3)   # saiu junto com o joystick antigo

# ================================================================ 1. LUA E TERRA
moon, earth, atmo = D.objects["LUA_Esfera"], D.objects["TERRA_Esfera"], D.objects["TERRA_Atmosfera"]
print("[1] antes  : Lua", PX(moon.location), "| Terra", PX(earth.location), " (px_x, px_y, profundidade m no eixo da câmera)")
M_PX, M_PY, M_R, M_D = 752, 244, 60, 180.0          # Lua: menor (86 -> 60 px de raio), mais à esquerda/baixo
E_PX, E_PY, E_R, E_D = 812, 196, 58, 900.0          # Terra: atrás, acima/direita, ~metade encoberta pela Lua
moon.location = P(M_PX, M_PY, M_D); moon.scale = (M_R * M_D / F,) * 3
earth.location = P(E_PX, E_PY, E_D); earth.scale = (E_R * E_D / F,) * 3
atmo.location = earth.location; atmo.scale = (E_R * E_D / F * 1.035,) * 3
dm, de = PX(moon.location)[2], PX(earth.location)[2]
sep = math.hypot(M_PX - E_PX, M_PY - E_PY)
print(f"[1] depois : Lua {PX(moon.location)} | Terra {PX(earth.location)} | Lua na frente: {dm < de} | sobreposição: {M_R + E_R - sep:.0f} px de {2*E_R} px da Terra")
print("[1] corpos celestes:", [o.name for o in D.objects if o.name.startswith(("LUA_", "TERRA_"))])

# ================================================================ 2. LUMINÁRIAS LATERAIS
# Causa real: os globos das 2 lâmpadas superiores (emissivos) refletiam nos 3 vidros das janelas -> discos/meias-luas brancas nas vigas.
# As lâmpadas superiores NÃO são alteradas na aparência; só deixam de aparecer em reflexos.
# (medido: desligar o reflexo só dos globos não bastou; quem refletia como disco branco eram as LUZES PONTUAIS das lâmpadas)
for nm in ("WIN_Lampada_Luz_0", "WIN_Lampada_Luz_1", "DEC_Luminaria_Vidro", "LUZ_Lampada_Topo_0", "LUZ_Lampada_Topo_1", "LUZ_Luminaria", "LUZ_Painel_Esq"):
    D.objects[nm].visible_glossy = False
c_win = D.collections["JANELAS"]; c_lit = D.collections["ILUMINACAO"]
old = D.objects.get("WIN_Faixa_Laranja_Dir")
if old: D.objects.remove(old, do_unlink=True)                      # estava 2 cm solta à frente da viga; refeita embutida, com par simétrico
def led_strip(tag, sgn):
    mx = (lambda px: px) if sgn > 0 else (lambda px: 1600 - px)
    a, b = P(mx(1205), 122, 3.02), P(mx(1420), 392, 2.52)           # corre sobre a face interna da viga principal
    off = Vector((0, -0.07, 0))                                     # face frontal da viga (espessura 0,14)
    obox(f"WIN_Faixa_LED_{tag}_Canaleta", (a + b) / 2 + off + Vector((0, -0.004, 0)), b - a, (0, -1, 0), ((b - a).length + 0.03, 0.036, 0.012), DARK, c_win, 0.003)
    obox(f"WIN_Faixa_LED_{tag}", (a + b) / 2 + off + Vector((0, -0.010, 0)), b - a, (0, -1, 0), ((b - a).length, 0.016, 0.006), MAT["LED_Ambar"], c_win, 0.002)
    for k, p in enumerate((a, b)):
        obox(f"WIN_Faixa_LED_{tag}_Terminal_{k}", p + off + Vector((0, -0.008, 0)), b - a, (0, -1, 0), (0.035, 0.05, 0.02), OLIVE_D, c_win, 0.004)
    return a, b
aR, bR = led_strip("Dir", 1); aL, bL = led_strip("Esq", -1)
lr = D.objects["LUZ_Faixa_Laranja"]                                 # luz que acompanha a faixa direita: mantém; cria par à esquerda
ll = D.objects.new("LUZ_Faixa_Laranja_Esq", lr.data.copy()); c_lit.objects.link(ll)
mm = lr.matrix_world.copy(); loc = mm.translation.copy(); tgt = loc + (mm.to_3x3() @ Vector((0, 0, -1)))
loc.x, tgt.x = -loc.x, -tgt.x
ll.location = loc; ll.rotation_euler = (tgt - loc).to_track_quat("-Z", "Y").to_euler(); ll.visible_glossy = False; ll.visible_camera = False
lr.data.energy = 50; ll.data.energy = 50                           # 70 W de um lado só -> 50 W de cada lado (quente, suave, simétrico)
print("[2] faixas de LED âmbar embutidas: Dir", PX((aR + bR) / 2), "| Esq", PX((aL + bL) / 2))

# ================================================================ 3. MINI RÁDIO COMUNICADOR
c_dec = D.collections["DECORACOES"]; c_rad = D.collections.new("RADIO"); c_dec.children.link(c_rad)
L0, L1 = P(800, 780, 1.52), P(800, 908, 0.82)                       # prateleira da bancada (fundo -> frente)
T = (L1 - L0).normalized(); N = X.cross(T).normalized()
if N.z < 0: N = -N
def ledge(x, s, h=0.0): return Vector((x, L0.y, L0.z)) + T * s + N * h
RW, RD, RH = 0.150, 0.062, 0.074                                    # largura, profundidade, altura (compacto)
RX, RS, YAW = -0.535, 0.315, math.radians(-16)                       # à esquerda, entre o monitor esquerdo e o joystick; frente girada p/ a câmera
Rz = Matrix.Rotation(YAW, 3, N)
rx, rt = (Rz @ X).normalized(), (Rz @ T).normalized()               # eixos do rádio: lateral e "para a frente" (em direção ao usuário)
base = ledge(RX, RS)
C = base + N * (RH / 2 + 0.006)
for sx in (-1, 1):                                                  # pés de borracha: apoio real sobre a bancada
    obox(f"RAD_Pe_{'E' if sx < 0 else 'D'}", base + rx * sx * (RW / 2 - 0.02) + N * 0.003, rx, N, (0.024, RD - 0.012, 0.006), MAT["BORRACHA_Preta"], c_rad, 0.002)
obox("RAD_Corpo", C, rx, N, (RW, RD, RH), OLIVE_D, c_rad, 0.006, 3)
FR = C + rt * (RD / 2)                                              # centro da face frontal
def fp(u, v, h=0.0): return FR + rx * u + N * v + rt * h            # ponto na face frontal
obox("RAD_Painel_Frontal", fp(0, 0, 0.0015), rx, rt, (RW - 0.012, RH - 0.012, 0.003), DARK, c_rad, 0.002)
obox("RAD_Tela_Moldura", fp(-0.030, 0.008, 0.003), rx, rt, (0.070, 0.040, 0.004), STEEL, c_rad, 0.002)
tela = mat_simple("RAD_Tela_Verde", (0.01, 0.05, 0.02), 0.25, (0.15, 1.0, 0.3), 0.9, coat=0.5)
obox("SCR_Radio_Tela", fp(-0.030, 0.008, 0.0052), rx, rt, (0.062, 0.032, 0.001), tela, c_rad, 0)
for k, u in enumerate((0.028, 0.052)):                              # 2 controles físicos
    cyl(f"RAD_Botao_Giratorio_{k}", fp(u, 0.012, 0.008), rt, 0.0085, 0.012, STEEL, c_rad)
    obox(f"RAD_Botao_Marca_{k}", fp(u, 0.0165, 0.0142), rx, rt, (0.0015, 0.006, 0.0008), DARK, c_rad, 0)
cyl("RAD_Indicador_Aro", fp(0.040, -0.014, 0.004), rt, 0.0055, 0.004, STEEL, c_rad, 16)
cyl("RAD_Indicador_Ambar", fp(0.040, -0.014, 0.0055), rt, 0.0038, 0.004, MAT["BTN_Ambar"], c_rad, 16)
for k in range(5):                                                  # grelha do alto-falante
    obox(f"RAD_Grelha_{k}", fp(-0.052 + k * 0.011, -0.021, 0.0035), rx, rt, (0.007, 0.010, 0.0015), OLIVE, c_rad, 0)
for k, (u, v) in enumerate(((-1, -1), (1, -1), (1, 1), (-1, 1))):
    bolt(f"RAD_Parafuso_{k}", fp(u * (RW / 2 - 0.012), v * (RH / 2 - 0.012), 0.003), rt, c_rad, 0.0028)
cyl("RAD_Antena_Base", C + N * (RH / 2 + 0.004) + rx * (RW / 2 - 0.02) - rt * 0.012, N, 0.006, 0.008, STEEL, c_rad, 16)
cyl("RAD_Antena", C + N * (RH / 2 + 0.022) + rx * (RW / 2 - 0.02) - rt * 0.012, N, 0.003, 0.030, MAT["BORRACHA_Preta"], c_rad, 12)
obox("RAD_Friso_Superior", C + N * (RH / 2 + 0.001), rx, N, (RW - 0.05, RD - 0.02, 0.003), OLIVE, c_rad, 0.0015)
# checagens de interferência
joy = D.objects["JOY_Joystick"]; scr = D.objects["SCR_Esquerdo_Tela"]
top_px = PX(C + N * RH / 2); scr_low = min(PX(scr.matrix_world @ Vector(c))[1] for c in scr.bound_box)
scr_bot = max(PX(scr.matrix_world @ Vector(c))[1] for c in scr.bound_box)
print(f"[3] rádio em {PX(C)} | distância ao joystick {(joy.location - C).length:.2f} m | topo do rádio na linha {top_px[1]} px, base da tela esquerda na linha {scr_bot} px -> {'não obstrui' if top_px[1] > scr_bot else 'OBSTRUI'}")

# ================================================================ 4. ALÇA DA CANECA
alca = D.objects["DEC_Caneca_Alca"]; cu = alca.data
sp = cu.splines[0]; cu.splines.remove(sp)
sp = cu.splines.new("BEZIER")
pts = [(0.0395, 0.028), (0.056, 0.0335), (0.069, 0.016), (0.069, -0.012), (0.056, -0.030), (0.0395, -0.027)]   # (raio, altura) no plano da alça; corpo tem raio 0,042
sp.bezier_points.add(len(pts) - 1)
for bp, (x, z) in zip(sp.bezier_points, pts):
    bp.co = (x, 0.0, z); bp.handle_left_type = bp.handle_right_type = "AUTO"
cu.bevel_depth = 0.0058; cu.bevel_resolution = 6; cu.resolution_u = 24; cu.use_fill_caps = True
for k, (x, z) in enumerate((pts[0], pts[-1])):                    # junções (superior e inferior): transição suave no corpo
    bm = bmesh.new(); bmesh.ops.create_uvsphere(bm, u_segments=20, v_segments=10, radius=1.0)
    me = D.meshes.new(f"DEC_Caneca_Alca_Juncao_{k}"); bm.to_mesh(me); bm.free(); me.shade_smooth(); me.materials.append(MAT["CERAMICA_Branca"])
    j = D.objects.new(f"DEC_Caneca_Alca_Juncao_{'Sup' if k == 0 else 'Inf'}", me); c_dec.objects.link(j)
    j.matrix_world = alca.matrix_world @ Matrix.Translation((0.0415, 0, z)) @ Matrix.Diagonal((0.0065, 0.0085, 0.0105, 1))
print(f"[4] alça refeita: {len(pts)} pontos, espessura {cu.bevel_depth*2*1000:.1f} mm uniforme, sai {max(p[0] for p in pts) - 0.042 + cu.bevel_depth:.3f} m do corpo, pontas {0.042 - pts[0][0]:.4f} m dentro do corpo")

# ================================================================ validação e salvamento
print(f"[V] objetos {n_antes} -> {len(D.objects)} | Luas {len([o for o in D.objects if o.name.startswith('LUA_')])} | Terra atrás da Lua: {dm < de}")
bpy.ops.wm.save_as_mainfile(filepath=DST)
print("[V] salvo em", DST)
