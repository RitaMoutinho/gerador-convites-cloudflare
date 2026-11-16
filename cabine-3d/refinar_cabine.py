"""
Refino visual/estrutural da cabine EXISTENTE (não reconstrói; sem otimização de desempenho).

Entrada : out/cabine_clps_v2_backup.blend  (cópia de segurança da versão otimizada, não é sobrescrita)
Saída   : out/cabine_clps_v3.blend
Joystick: caminho do .glb em --joy (ou variável JOY_GLB); se não existir, o script PARA e avisa.

Uso: blender -b -P refinar_cabine.py -- --joy caminho/modelojoystick.glb
"""
import bpy, bmesh, math, os, sys
from mathutils import Vector, Matrix

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
SRC = os.path.join(HERE, "out", "cabine_clps_v2_backup.blend")
DST = os.path.join(HERE, "out", "cabine_clps_v3.blend")
JOY = argv[argv.index("--joy") + 1] if "--joy" in argv else os.environ.get("JOY_GLB", os.path.join(HERE, "modelojoystick.glb"))
if not os.path.exists(JOY):
    raise SystemExit("Joystick .glb não encontrado: " + JOY + " — informe o caminho com --joy antes de criar substituto.")

bpy.ops.wm.open_mainfile(filepath=SRC)
scene = bpy.context.scene; D = bpy.data
MAT = D.materials
cam = D.objects["CAM_Principal"]
F = cam.data.lens / cam.data.sensor_width * 1600.0
CAM_LOC = cam.matrix_world.translation.copy()
def P(px, py, d):
    return cam.matrix_world @ Vector(((px - 800) / F * d, -(py - 450) / F * d, -d))
def COL(name, parent=None):
    c = D.collections.get(name)
    if c is None:
        c = D.collections.new(name); (parent or scene.collection).children.link(c)
    return c

# ----------------------------------------------------------------- helpers (mesmos da construção original)
def mesh_from(name, verts, faces):
    me = D.meshes.new(name); me.from_pydata([tuple(v) for v in verts], [], faces); me.update()
    bm = bmesh.new(); bm.from_mesh(me); bmesh.ops.recalc_face_normals(bm, faces=bm.faces); bm.to_mesh(me); bm.free()
    return me
def box_mesh(name, sx, sy, sz):
    hx, hy, hz = sx / 2, sy / 2, sz / 2
    v = [(-hx, -hy, -hz), (hx, -hy, -hz), (hx, hy, -hz), (-hx, hy, -hz), (-hx, -hy, hz), (hx, -hy, hz), (hx, hy, hz), (-hx, hy, hz)]
    return mesh_from(name, v, [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)])
def ring_mesh(name, ow, oh, iw, ih, hz):
    """Aro retangular (moldura com furo): encaixe/cavidade real para botões e telas."""
    v = []
    for z in (0, hz):
        for w, h in ((ow, oh), (iw, ih)):
            v += [(-w / 2, -h / 2, z), (w / 2, -h / 2, z), (w / 2, h / 2, z), (-w / 2, h / 2, z)]
    f = []
    for i in range(4):
        j = (i + 1) % 4
        f += [(i, j, 8 + j, 8 + i), (4 + i, 12 + i, 12 + j, 4 + j), (8 + i, 8 + j, 12 + j, 12 + i), (i, 4 + i, 4 + j, j)]
    return mesh_from(name, v, f)
def basis(x, z):
    x = Vector(x).normalized(); z = Vector(z); z = (z - x * z.dot(x)).normalized(); y = z.cross(x)
    return Matrix(((x.x, y.x, z.x, 0), (x.y, y.y, z.y, 0), (x.z, y.z, z.z, 0), (0, 0, 0, 1)))
def finish(ob, bevel=0.004, seg=2):
    ob.data.shade_smooth()
    if bevel:
        b = ob.modifiers.new("Bisel", "BEVEL"); b.width = bevel; b.segments = seg; b.limit_method = "ANGLE"; b.angle_limit = math.radians(35)
    w = ob.modifiers.new("NormaisPonderadas", "WEIGHTED_NORMAL"); w.keep_sharp = True
    return ob
def place(name, me, col, mat, center, xdir, zdir, bevel=0.004, seg=2):
    ob = D.objects.new(name, me); col.objects.link(ob)
    if mat: ob.data.materials.append(mat)
    m = basis(xdir, zdir); m.translation = Vector(center); ob.matrix_world = m
    return finish(ob, bevel, seg)
def obox(name, center, xdir, zdir, size, mat, col, bevel=0.004, seg=2):
    return place(name, box_mesh(name, *size), col, mat, center, xdir, zdir, bevel, seg)
def bolt(name, pos, nrm, col, r=0.006):
    ob = D.objects.new(name, D.meshes["MalhaParafuso"]); col.objects.link(ob)
    m = basis(Vector(nrm).orthogonal(), nrm) @ Matrix.Scale(r, 4); m.translation = Vector(pos); ob.matrix_world = m
    return ob
def remove(names):
    n = 0
    for nm in names:
        o = D.objects.get(nm)
        if o: D.objects.remove(o, do_unlink=True); n += 1
    return n
def mat_simple(name, color, rough, emit=None, strength=0.0, coat=0.0, metal=0.0):
    m = MAT.new(name); m.use_nodes = True; b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = tuple(color) + (1,); b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal; b.inputs["Coat Weight"].default_value = coat
    if emit:
        b.inputs["Emission Color"].default_value = tuple(emit) + (1,); b.inputs["Emission Strength"].default_value = strength
    return m

OLIVE, OLIVE_D, OLIVE_L, DARK, STEEL = (MAT["MET_Oliva_Envelhecido"], MAT["MET_Oliva_Escuro"], MAT["MET_Oliva_Claro"],
                                        MAT["MET_Preto_Tecnico"], MAT["MET_Aco_Escovado"])
UP = Vector((0, 0, 1)); X = Vector((1, 0, 0))

# ----------------------------------------------------------------- geometria da bancada (perfil original)
W0, W1 = P(800, 398, 2.4), P(800, 780, 1.78)      # parede inclinada atrás dos monitores
L0, L1 = P(800, 780, 1.52), P(800, 908, 0.82)      # prateleira (fundo -> borda frontal)
T = (L1 - L0).normalized(); LEN = (L1 - L0).length
N = X.cross(T).normalized()
if N.z < 0: N = -N
def ledge(x, s, h=0.0):
    """Ponto na prateleira: x lateral, s metros a partir do fundo, h acima da superfície."""
    return Vector((x, L0.y, L0.z)) + T * s + N * h
def surf_z(y):
    def lerp(a, b):
        return a.z + (b.z - a.z) * (y - a.y) / (b.y - a.y)
    if y <= L0.y: return lerp(L0, L1)
    if y <= W1.y: return lerp(L0, W1)
    return lerp(W1, W0)
print(f"[i] prateleira: comprimento {LEN:.2f} m, inclinação {math.degrees(math.atan2(T.z, -T.y)):.1f}°, fundo y={L0.y:.2f} z={L0.z:.2f}, frente y={L1.y:.2f} z={L1.z:.2f}")

c_pc, c_bt, c_mon, c_joy, c_dec = D.collections["PAINEL_CONTROLE"], COL("BOTOES"), D.collections["MONITORES"], COL("JOYSTICK"), D.collections["DECORACOES"]

# ================================================================= PRIORIDADE 1 — MONITOR ESQUERDO (+ integração dos 3)
MONS = {  # mesmos parâmetros com que os monitores foram construídos
    "Central": dict(c=P(812, 588, 1.62), w=0.84, h=0.47, yaw=0, tilt=14, b=0.065, t=0.10),
    "Direito": dict(c=P(1312, 612, 1.42), w=0.36, h=0.33, yaw=-26, tilt=10, b=0.05, t=0.08),
    "Esquerdo": dict(c=P(305, 650, 1.40), w=0.34, h=0.26, yaw=24, tilt=10, b=0.05, t=0.10),
}
for nm, m in MONS.items():
    Mx = Matrix.Rotation(math.radians(m["yaw"]), 3, "Z") @ Matrix.Rotation(math.radians(-m["tilt"]), 3, "X")
    m["r"], m["u"] = Mx @ X, Mx @ UP
    n = m["r"].cross(m["u"])
    m["n"] = n if n.dot(CAM_LOC - m["c"]) > 0 else -n
    m["iw"], m["ih"] = m["w"] - 2 * m["b"], m["h"] - m["b"] - m["b"] * 1.35
    m["sc"] = m["c"] + m["u"] * (m["b"] * 0.175) - m["n"] * (m["t"] * 0.28)

# 1a. remove a carcaça redundante que engolia a tela esquerda
print("[1] carcaça esquerda removida:", remove(["CON_Carcaca_Esquerda"]))
# 1b. caixa traseira do monitor esquerdo: 20 cm -> 8 cm (volume proporcional)
m = MONS["Esquerdo"]; d2 = 0.08
ob = D.objects["MON_Esquerdo_Caixa_Traseira"]; old = ob.data
ob.data = box_mesh("MON_Esquerdo_Caixa_Traseira", m["w"] * 0.96, m["h"] * 0.96, d2); ob.data.materials.append(OLIVE_D); ob.data.shade_smooth()
mt = basis(m["r"], m["n"]); mt.translation = m["c"] - m["n"] * (m["t"] / 2 + d2 / 2 - 0.01); ob.matrix_world = mt
if old.users == 0: D.meshes.remove(old)
# 1c. tampa superior fina (onde a luminária apoia) — substitui a função de "prateleira" da carcaça
rh = Vector((m["r"].x, m["r"].y, 0)).normalized(); back = UP.cross(rh)          # horizontal, para trás do monitor
if back.dot(m["n"]) > 0: back = -back
top_c = m["c"] + m["u"] * (m["h"] / 2)
cap_c = Vector((top_c.x, top_c.y, top_c.z + 0.010)) + back * 0.045
obox("MON_Esquerdo_Tampa_Superior", cap_c, rh, UP, (m["w"] + 0.016, 0.17, 0.022), OLIVE, c_mon, 0.005)
cap_top = cap_c.z + 0.011
# luminária: reapoia sobre a tampa
lb = D.objects["DEC_Luminaria_Base"]
delta = (cap_c + back * 0.01 - rh * 0.07) - lb.matrix_world.translation; delta.z = (cap_top + 0.014) - lb.matrix_world.translation.z
for nm in ("DEC_Luminaria_Base", "DEC_Luminaria_Vidro", "DEC_Luminaria_Tampa", "LUZ_Luminaria"):
    D.objects[nm].location += delta

# 1d/7. pedestais integrados + aro interno (profundidade de tela) nos TRÊS monitores; substituem os CAB_Suporte_* que atravessavam tudo
print("[5] suportes que atravessavam bancada/monitores removidos:", remove([f"CAB_Suporte_{i}" for i in range(5)]))
for nm, m in MONS.items():
    rh = Vector((m["r"].x, m["r"].y, 0)).normalized(); back = UP.cross(rh)
    if back.dot(m["n"]) > 0: back = -back
    B = m["c"] - m["u"] * (m["h"] / 2)                       # centro da borda inferior
    foot = B + back * 0.05
    zs = surf_z(foot.y)
    hgt = max(B.z - zs, 0.0) + 0.06
    obox(f"MON_{nm}_Pedestal", Vector((foot.x, foot.y, B.z + 0.02 - hgt / 2)), rh, UP, (m["w"] * 0.62, 0.13, hgt), OLIVE_D, c_mon, 0.008)
    obox(f"MON_{nm}_Sapata", Vector((foot.x, foot.y, zs + 0.006)) - back * 0.02, rh, UP, (m["w"] * 0.78, 0.2, 0.024), OLIVE, c_mon, 0.006)
    for sgn in (-1, 1):
        bolt(f"MON_{nm}_Sapata_Parafuso_{'E' if sgn < 0 else 'D'}", Vector((foot.x, foot.y, zs + 0.018)) - back * 0.085 + rh * sgn * m["w"] * 0.33, UP, c_mon, 0.007)
    # aro interno escuro em volta da tela (dá profundidade física; a tela SCR_* continua separada e intacta)
    lip = 0.012
    place(f"MON_{nm}_Aro_Interno", ring_mesh(f"MON_{nm}_Aro_Interno", m["iw"] + 0.004, m["ih"] + 0.004, m["iw"] - 2 * lip, m["ih"] - 2 * lip, 0.012),
          c_mon, DARK, m["sc"] + m["n"] * 0.003, m["r"], m["n"], 0.002)
    print(f"[1/7] {nm}: borda inferior z={B.z:.3f}, bancada z={zs:.3f}, pedestal {hgt*100:.0f} cm")

# ================================================================= PRIORIDADE 2 — BOTÕES
print("[2] botões antigos removidos:", remove([o.name for o in D.objects if o.name.startswith(("BTN_", "LED_Painel_"))]))
BM = {
    "verde": mat_simple("BTN_Verde", (0.10, 0.32, 0.08), 0.32, (0.25, 1.0, 0.15), 1.1, coat=0.6),
    "branco": mat_simple("BTN_Branco_Suave", (0.55, 0.55, 0.5), 0.35, (1.0, 0.93, 0.8), 0.6, coat=0.6),
    "ambar": mat_simple("BTN_Ambar", (0.4, 0.18, 0.02), 0.32, (1.0, 0.4, 0.04), 1.1, coat=0.6),
    "vermelho": mat_simple("BTN_Vermelho", (0.35, 0.02, 0.01), 0.32, (1.0, 0.05, 0.02), 1.1, coat=0.6),
}
BW_D = 0.030   # profundidade (ao longo da prateleira) padronizada
class Frame:
    """Superfície de montagem: origem + tangente + normal."""
    def __init__(self, o, t, n): self.o, self.t, self.n = Vector(o), Vector(t).normalized(), Vector(n).normalized()
    def pt(self, x, s, h=0.0): return self.o + X * x + self.t * s + self.n * h
BANC = Frame(Vector((0, L0.y, L0.z)), T, N)
# painel inclinado para o usuário (console dos botões): cunha embutida na bancada, sob o monitor central
FS0, FS1, FHB, FHF, FX0, FX1 = 0.150, 0.245, 0.072, 0.010, -0.275, 0.445
pa, pb = ledge(0, FS0, FHB), ledge(0, FS1, FHF)
Tf = (pb - pa).normalized(); Nf = X.cross(Tf).normalized()
if Nf.z < 0: Nf = -Nf
FASC = Frame((pa + pb) / 2, Tf, Nf)
vv = []
for x in (FX0, FX1): vv += [ledge(x, FS0 - 0.012, -0.01), ledge(x, FS1 + 0.006, -0.01), ledge(x, FS1 + 0.006, FHF), ledge(x, FS0, FHB), ledge(x, FS0 - 0.012, FHB)]
ff = [(0, 1, 2, 3, 4), (9, 8, 7, 6, 5)] + [(i, (i + 1) % 5, 5 + (i + 1) % 5, 5 + i) for i in range(5)]
wd_ob = D.objects.new("CON_Console_Botoes", mesh_from("CON_Console_Botoes", vv, ff)); c_pc.objects.link(wd_ob); wd_ob.data.materials.append(OLIVE_D); finish(wd_ob, 0.006, 3)
print(f"[2] painel dos botões inclinado {math.degrees(math.acos(max(-1, min(1, Nf.dot(UP))))):.0f}° em direção ao usuário")
def button(name, x, s, width, cor, fr=None):
    fr = fr or BANC; ledge = fr.pt; N = fr.n
    """Botão físico: aro metálico com cavidade + fundo escuro + tecla de cantos arredondados 2 mm ABAIXO do aro."""
    place(f"{name}_Aro", ring_mesh(f"{name}_Aro", width + 0.014, BW_D + 0.014, width + 0.002, BW_D + 0.002, 0.009), c_bt, STEEL, ledge(x, s, 0.004), X, N, 0.0015)
    obox(f"{name}_Fundo", ledge(x, s, 0.0045), X, N, (width + 0.004, BW_D + 0.004, 0.002), DARK, c_bt, 0)
    obox(f"{name}_Tecla", ledge(x, s, 0.0075), X, N, (width, BW_D, 0.007), BM[cor], c_bt, 0.0035, 3)
def plate(name, x0, x1, s, depth=0.062, fr=None):
    """Placa do agrupamento, semi-embutida na bancada, com 2 parafusos."""
    fr = fr or BANC; ledge = fr.pt; N = fr.n
    obox(name, ledge((x0 + x1) / 2, s, 0.001), X, N, (x1 - x0 + 0.036, depth, 0.008), OLIVE_D, c_bt, 0.003)
    for sx in (x0 - 0.011, x1 + 0.011):
        bolt(f"{name}_Parafuso_{'E' if sx < (x0 + x1) / 2 else 'D'}", ledge(sx, s - depth / 2 + 0.008, 0.005), N, c_bt, 0.004)
S_ROW = 0.0   # centro da face do painel inclinado
GROUPS = [("Aux", "ambar", 0.046, [-0.215, -0.150]), ("Principal", "verde", 0.064, [-0.045, 0.040, 0.125]),
          ("Secundario", "branco", 0.046, [0.230, 0.295]), ("Alerta", "vermelho", 0.046, [0.385])]
for g, cor, wd, xs in GROUPS:
    plate(f"BTN_Placa_{g}", xs[0] - wd / 2, xs[-1] + wd / 2, S_ROW, 0.058, FASC)
    for i, x in enumerate(xs): button(f"BTN_{g}_{i}", x, S_ROW, wd, cor, FASC)
# indicadores auxiliares laterais (eram blocos luminosos flutuando): agora encaixados na bancada
plate("LED_Placa_Esq", -0.66, -0.58, 0.42); button("LED_Painel_Esq", -0.62, 0.42, 0.07, "ambar")
plate("LED_Placa_Dir", 0.585, 0.695, 0.30)
for i, x in enumerate((0.61, 0.67)): button(f"LED_Painel_Dir_{i}", x, 0.30, 0.04, "ambar")
D.objects["LUZ_Painel_Esq"].location = ledge(-0.62, 0.42, 0.12); D.objects["LUZ_Painel_Esq"].data.energy = 3

# ================================================================= PRIORIDADE 3 — LUA E TERRA
luas = [o for o in D.objects if o.type == "MESH" and o.name.upper().startswith("LUA")]
terras = [o for o in D.objects if o.name == "TERRA_Esfera" or (o.name.startswith("TERRA_Esfera."))]
print(f"[3] Luas na cena: {[o.name for o in luas]} | Terras: {[o.name for o in terras]} (sem duplicação)")
M_PX, M_PY, M_R, M_D = 742, 232, 86, 180.0       # Lua: menor, primeiro plano, à esquerda
E_PX, E_PY, E_R, E_D = 872, 166, 66, 900.0       # Terra: atrás, acima e à direita
moon = D.objects["LUA_Esfera"]; moon.location = P(M_PX, M_PY, M_D); moon.scale = (M_R * M_D / F,) * 3
for nm, k in (("TERRA_Esfera", 1.0), ("TERRA_Atmosfera", 1.035)):
    o = D.objects[nm]; o.location = P(E_PX, E_PY, E_D); o.scale = (E_R * E_D / F * k,) * 3
for nd in MAT["LUA_Superficie"].node_tree.nodes:   # Lua estava escura e chapada: albedo mais claro e relevo mais marcado
    if nd.bl_idname == "ShaderNodeValToRGB":
        nd.color_ramp.elements[0].color = (0.11, 0.105, 0.10, 1); nd.color_ramp.elements[1].color = (0.42, 0.40, 0.37, 1)
    if nd.bl_idname == "ShaderNodeBump": nd.inputs["Strength"].default_value = 0.8

# ================================================================= PRIORIDADE 4 — JOYSTICK (modelo .glb fornecido)
print("[4] 'vaso' (joystick provisório) removido:", remove(["CTL_Joystick_Base", "CTL_Joystick_Haste", "CTL_Joystick_Pomo", "CTL_Joystick_Anel"]))
antes = set(D.objects)
bpy.ops.import_scene.gltf(filepath=JOY)
novos = [o for o in D.objects if o not in antes]
joy = next(o for o in novos if o.type == "MESH")
for o in novos:
    if o is not joy: D.objects.remove(o, do_unlink=True)          # empty "world" do glb
for c_ in list(joy.users_collection): c_.objects.unlink(joy)
c_joy.objects.link(joy)
joy.name = "JOY_Joystick"; joy.data.name = "JOY_Joystick_Malha"; joy.parent = None
JS = 0.165                                                          # ~21 cm de altura (modelo vem com ~1 unidade)
JX, JSs = -0.285, LEN - 0.10
zmin = min((Vector(c).z for c in joy.bound_box)); half_w = max(abs(Vector(c).x) for c in joy.bound_box) * JS; half_d = max(abs(Vector(c).y) for c in joy.bound_box) * JS
p_c = ledge(JX, JSs)
z_top = max(surf_z(p_c.y - half_d - 0.015), surf_z(p_c.y + half_d + 0.015)) + 0.006      # topo nivelado acima da rampa
z_low = min(surf_z(p_c.y - half_d - 0.015), surf_z(p_c.y + half_d + 0.015))
ph = (z_top - z_low) + 0.03
obox("JOY_Soquete_Bancada", Vector((JX, p_c.y, z_top - ph / 2)), X, UP, (2 * half_w + 0.03, 2 * half_d + 0.03, ph), OLIVE_D, c_joy, 0.006)
for sx in (-1, 1):
    for sy in (-1, 1):
        bolt(f"JOY_Soquete_Parafuso_{'E' if sx < 0 else 'D'}{'F' if sy < 0 else 'T'}", Vector((JX + sx * (half_w + 0.006), p_c.y + sy * (half_d + 0.006), z_top)), UP, c_joy, 0.005)
joy.rotation_mode = "XYZ"; joy.rotation_euler = (0, 0, 0); joy.scale = (JS,) * 3
joy.location = Vector((JX, p_c.y, z_top - zmin * JS - 0.002))        # base assentada 2 mm dentro do soquete; alavanca inclina p/ -Y (usuário)
print(f"[4] joystick instalado em x={JX:.2f} y={p_c.y:.2f} z_base={z_top:.3f}; {len(joy.data.vertices)} vértices, materiais {[m_.name for m_ in joy.data.materials]}")

# ================================================================= PRIORIDADE 5 — OBJETOS SOLTOS / BLOCOS SEM FUNÇÃO
# bloco retangular à esquerda-frente do monitor central = base de uma grelha de ventilação solta, em cima do lugar do joystick -> removida
print("[5] grelha solta (bloco retangular) removida:", remove(["CON_Grelha_Esq_Base"] + [f"CON_Grelha_Esq_{i}" for i in range(9)]))
# grelha direita: reassentada rente à bancada, com moldura
gx, gs = 0.43, LEN - 0.14
for i in range(7):
    o = D.objects[f"CON_Grelha_Dir_{i}"]; mt = basis(X, N); mt.translation = ledge(gx - 0.045 + i * 0.015, gs, 0.003); o.matrix_world = mt
place("CON_Grelha_Dir_Moldura", ring_mesh("CON_Grelha_Dir_Moldura", 0.13, 0.125, 0.108, 0.103, 0.007), c_pc, OLIVE_D, ledge(gx, gs, 0.001), X, N, 0.002)
obox("CON_Grelha_Dir_Fundo", ledge(gx, gs, 0.0015), X, N, (0.11, 0.105, 0.002), DARK, c_pc, 0)
# interruptores: reassentados em linha sobre uma placa própria
ix0, isw = 0.255, LEN - 0.33
plate("CON_Interruptores_Placa", ix0 - 0.005, ix0 + 5 * 0.032 + 0.005, isw, 0.05)
for i in range(6):
    o = D.objects[f"CON_Interruptor_{i}"]; mt = basis(X, N) @ Matrix.Diagonal((0.006, 0.006, 0.012, 1)); mt.translation = ledge(ix0 + i * 0.032, isw, 0.014); o.matrix_world = mt
# cabos: saíam do ar perto da câmera; agora correm apoiados na bancada até a base do monitor esquerdo
routes = [[(-1.05, 0.36), (-0.86, 0.30), (-0.74, 0.22), (-0.66, 0.12)], [(-1.05, 0.46), (-0.90, 0.40), (-0.80, 0.26), (-0.72, 0.14)]]
for k, pts in enumerate(routes):
    cu = D.objects[f"CON_Cabo_{k}"].data; cu.bevel_depth = 0.006
    for bp, (x, s) in zip(cu.splines[0].bezier_points, pts):
        bp.co = ledge(x, s, 0.006); bp.handle_left_type = bp.handle_right_type = "AUTO"
# caneca: estava no ar, na frente da borda da bancada -> assentada na prateleira (rígido, logo NASA junto)
mug = [D.objects[n_] for n_ in ("DEC_Caneca_Corpo", "DEC_Caneca_Interior", "DEC_Caneca_Alca", "DEC_Caneca_Logo_Disco", "DEC_Caneca_Logo_Texto", "DEC_Caneca_Logo_Orbita")]
body = D.objects["DEC_Caneca_Corpo"]; old_c = body.matrix_world.translation.copy()
ang = UP.angle(N); Rm = Matrix.Rotation(-ang if T.z > 0 else ang, 4, "X")           # alinha o eixo da caneca à normal da bancada
new_c = ledge(0.52, LEN - 0.085, 0.048)
Tm = Matrix.Translation(new_c) @ Rm @ Matrix.Translation(-old_c)
for o in mug: o.matrix_world = Tm @ o.matrix_world
print("[5] caneca assentada; eixo da caneca·normal =", round((body.matrix_world.to_3x3() @ UP).normalized().dot(N), 3))

# ================================================================= PRIORIDADE 6 — BASE / BANCADA
c_cab = D.collections["CABINE_ESTRUTURA"]
obox("CAB_Bancada_Friso_Fundo", ledge(0, 0.0, 0.004) , X, N, (3.2, 0.03, 0.016), OLIVE, c_cab, 0.004)       # transição parede/prateleira
obox("CAB_Bancada_Friso_Frente", ledge(0, LEN - 0.012, 0.004), X, N, (3.2, 0.026, 0.018), OLIVE, c_cab, 0.005)  # borda frontal chanfrada
for sgn, nm in ((-1, "Esq"), (1, "Dir")):                                                                         # juntas discretas dos módulos
    obox(f"CAB_Bancada_Junta_{nm}", ledge(sgn * 0.50, LEN / 2, 0.0005), X, N, (0.006, LEN - 0.05, 0.003), DARK, c_cab, 0)
ob = D.objects["CAB_Painel_Console_Base"]
for md in ob.modifiers:
    if md.type == "BEVEL": md.width = 0.014; md.segments = 3

# ================================================================= PRIORIDADE 7 — MATERIAIS / ILUMINAÇÃO
b = MAT["TELA_Provisoria"].node_tree.nodes["Principled BSDF"]; b.inputs["Roughness"].default_value = 0.22   # tela menos espelhada
b = MAT["LED_Ambar"].node_tree.nodes["Principled BSDF"]; b.inputs["Emission Strength"].default_value = 2.6  # lâmpadas estouravam em branco
b.inputs["Emission Color"].default_value = (1.0, 0.36, 0.03, 1)
b = MAT["BORRACHA_Preta"].node_tree.nodes["Principled BSDF"]; b.inputs["Roughness"].default_value = 0.55
for mn in ("MET_Oliva_Envelhecido", "MET_Oliva_Escuro", "MET_Oliva_Claro", "MET_Preto_Tecnico"):            # piso de rugosidade: sem reflexo de espelho
    for nd in MAT[mn].node_tree.nodes:
        if nd.bl_idname == "ShaderNodeMix" and nd.data_type == "FLOAT": nd.inputs[3].default_value = 0.42
c = scene.cycles; c.sample_clamp_indirect = 3.0; c.use_denoising = True; c.use_preview_denoising = True

# ================================================================= COLEÇÕES
root = scene.collection
def move_col(child, new_parent):
    for p in [root] + list(D.collections):
        if child.name in p.children: p.children.unlink(child)
    new_parent.children.link(child)
ce = D.collections.get("ESPACO_EXTERIOR")
if ce: ce.name = "CENARIO_ESPACIAL"
ce = D.collections["CENARIO_ESPACIAL"]
for nm in ("LUA", "TERRA"): move_col(D.collections[nm], root)
move_col(D.collections["JANELAS"], D.collections["CABINE_ESTRUTURA"])
old_ctl = D.collections.get("CONTROLES")
if old_ctl:
    for o in list(old_ctl.objects): old_ctl.objects.unlink(o); c_pc.objects.link(o)
    move_col(old_ctl, root); root.children.unlink(old_ctl); D.collections.remove(old_ctl)
D.orphans_purge(do_recursive=True)
print("[11] coleções:", [(c_.name, [k.name for k in c_.children]) for c_ in root.children])

# ================================================================= VALIDAÇÃO
flut = []
for o in list(c_bt.objects) + list(c_pc.objects):
    if o.type != "MESH" or "Parafuso" in o.name: continue
    p = o.matrix_world.translation
    if L1.y - 0.02 <= p.y <= L0.y + 0.02:
        gap = (p - Vector((p.x, L0.y, L0.z))).dot(N)
        if o.name.startswith("BTN_") or o.name == "CON_Console_Botoes": gap = (p - FASC.o).dot(FASC.n)   # botões: medidos contra o painel inclinado
        if abs(gap) > 0.03: flut.append((o.name, round(gap, 3)))
print("[V] peças a mais de 3 cm da superfície da bancada:", flut or "nenhuma")
print("[V] Luas:", len([o for o in D.objects if o.name.startswith("LUA_")]), "| Terra atrás da Lua:", (D.objects["TERRA_Esfera"].location - CAM_LOC).length > (moon.location - CAM_LOC).length,
      "| astronauta:", len([o for o in D.objects if "Astronauta" in o.name]), "| objetos:", len(D.objects))
bpy.ops.wm.save_as_mainfile(filepath=DST)
print("[V] salvo em", DST)
