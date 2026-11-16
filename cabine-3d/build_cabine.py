"""
CLPS - Cabine lunar 3D (reconstrução da imagem de referência)
=============================================================
Gera a cena completa no Blender (>= 4.2, testado em 5.3) a partir de código.

Uso dentro do Blender (GUI):  Scripting > Open > build_cabine.py > Run Script
Uso em linha de comando:      blender -b -P build_cabine.py -- [--render] [--scale 0.5] [--samples 64]
Uso com o módulo pip `bpy`:   python build_cabine.py --render

Tudo é posicionado a partir de PIXELS da imagem de referência (1600x900) + profundidade,
via a função P(px, py, profundidade). Assim a câmera principal reproduz o enquadramento.
"""
import bpy, bmesh, math, random, sys, os
from mathutils import Vector, Matrix, Euler, noise

# ----------------------------------------------------------------------------- args
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
def arg(name, default):
    return argv[argv.index(name) + 1] if name in argv else default
DO_RENDER = "--render" in argv
SCALE = float(arg("--scale", 1.0))
SAMPLES = int(arg("--samples", 64))
HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
OUT = arg("--out", os.path.join(HERE, "out"))
os.makedirs(OUT, exist_ok=True)
random.seed(11)

# ----------------------------------------------------------------------------- cena limpa
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.name = "CLPS_Cabine"

RES_X, RES_Y = 1600, 900
LENS, SENSOR = 28.0, 36.0
F = LENS / SENSOR * RES_X                     # focal em pixels
CAM_LOC = Vector((0, 0, 1.0))                 # olhos do usuário (m)
CAM_PITCH = 5.5                               # graus olhando pra baixo
CAM_ROT = Euler((math.radians(90 - CAM_PITCH), 0, 0), "XYZ")
CAM_MAT = Matrix.Translation(CAM_LOC) @ CAM_ROT.to_matrix().to_4x4()

def P(px, py, d):
    """Ponto no mundo que aparece no pixel (px,py) da referência a 'd' metros da câmera."""
    return CAM_MAT @ Vector(((px - RES_X / 2) / F * d, -(py - RES_Y / 2) / F * d, -d))

def dash_d(py):
    """Profundidade da superfície do painel inferior em função da linha de pixel."""
    if py < 780: return 2.4 + (py - 398) * (1.78 - 2.4) / (780 - 398)
    return 1.52 + (py - 780) * (0.82 - 1.52) / (908 - 780)

# ----------------------------------------------------------------------------- coleções
COLL = {}
for key, nm in [("cab", "01_Estrutura_Cabine"), ("win", "02_Janelas"), ("con", "03_Console_Principal"),
                ("mon", "04_Monitores"), ("ctl", "05_Controles"), ("dec", "06_Objetos_Decorativos"),
                ("ter", "07_Terreno_Lunar"), ("ear", "08_Terra"), ("sky", "09_Ceu"),
                ("lit", "10_Iluminacao"), ("cam", "11_Cameras")]:
    c = bpy.data.collections.new(nm)
    scene.collection.children.link(c)
    COLL[key] = c

# ----------------------------------------------------------------------------- materiais
def mat_new(name):
    m = bpy.data.materials.new(name)
    try:
        m.use_nodes = True
    except Exception:
        pass
    return m

def bsdf(m):
    return m.node_tree.nodes["Principled BSDF"]

def mix_rgba(n, l, fac, a, b):
    mx = n.new("ShaderNodeMix"); mx.data_type = "RGBA"
    if isinstance(fac, (int, float)): mx.inputs[0].default_value = fac
    else: l.new(fac, mx.inputs[0])
    for idx, v in ((6, a), (7, b)):
        if hasattr(v, "node"): l.new(v, mx.inputs[idx])
        else: mx.inputs[idx].default_value = v
    return mx.outputs[2]

def ramp(n, l, src, stops):
    r = n.new("ShaderNodeValToRGB")
    while len(r.color_ramp.elements) > len(stops):
        r.color_ramp.elements.remove(r.color_ramp.elements[-1])
    while len(r.color_ramp.elements) < len(stops):
        r.color_ramp.elements.new(0.5)
    for e, (pos, col) in zip(r.color_ramp.elements, stops):
        e.position = pos; e.color = col
    l.new(src, r.inputs["Fac"])
    return r

def mat_metal(name, color, rough=0.5, wear=1.0, rust=0.5, scale=1.0):
    """Metal pintado envelhecido: desgaste nas bordas (Bevel), ferrugem, riscos e juntas de painel."""
    m = mat_new(name); n, l = m.node_tree.nodes, m.node_tree.links; b = bsdf(m)
    tc = n.new("ShaderNodeTexCoord")
    nz = n.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 14 * scale; nz.inputs["Detail"].default_value = 9
    l.new(tc.outputs["Object"], nz.inputs["Vector"])
    nz2 = n.new("ShaderNodeTexNoise"); nz2.inputs["Scale"].default_value = 3.5 * scale; nz2.inputs["Detail"].default_value = 6
    l.new(tc.outputs["Object"], nz2.inputs["Vector"])
    vor = n.new("ShaderNodeTexVoronoi"); vor.feature = "DISTANCE_TO_EDGE"; vor.inputs["Scale"].default_value = 5 * scale
    l.new(tc.outputs["Object"], vor.inputs["Vector"])
    seam = ramp(n, l, vor.outputs["Distance"], [(0.0, (0.55, 0.55, 0.55, 1)), (0.012, (1, 1, 1, 1))])
    # máscara de borda
    bev = n.new("ShaderNodeBevel"); bev.inputs["Radius"].default_value = 0.012
    geo = n.new("ShaderNodeNewGeometry")
    dot = n.new("ShaderNodeVectorMath"); dot.operation = "DOT_PRODUCT"
    l.new(bev.outputs["Normal"], dot.inputs[0]); l.new(geo.outputs["Normal"], dot.inputs[1])
    inv = n.new("ShaderNodeMath"); inv.operation = "SUBTRACT"; inv.inputs[0].default_value = 1.0
    l.new(dot.outputs["Value"], inv.inputs[1])
    edge = ramp(n, l, inv.outputs["Value"], [(0.0, (0, 0, 0, 1)), (0.03, (1, 1, 1, 1))])
    grun = ramp(n, l, nz.outputs["Fac"], [(0.35, (0, 0, 0, 1)), (0.62, (1, 1, 1, 1))])
    wmask = n.new("ShaderNodeMath"); wmask.operation = "MULTIPLY"; wmask.inputs[1].default_value = wear
    l.new(edge.outputs["Color"], wmask.inputs[0])
    wm2 = n.new("ShaderNodeMath"); wm2.operation = "MULTIPLY"
    l.new(wmask.outputs["Value"], wm2.inputs[0]); l.new(grun.outputs["Color"], wm2.inputs[1])
    # cor: tinta -> ferrugem -> aço exposto
    rust_mask = ramp(n, l, nz2.outputs["Fac"], [(0.58, (0, 0, 0, 1)), (0.78, (1, 1, 1, 1))])
    rm = n.new("ShaderNodeMath"); rm.operation = "MULTIPLY"; rm.inputs[1].default_value = rust
    l.new(rust_mask.outputs["Color"], rm.inputs[0])
    paint = mix_rgba(n, l, rm.outputs["Value"], tuple(color) + (1,), (0.16, 0.07, 0.03, 1))
    paint = mix_rgba(n, l, seam.outputs["Color"], (0.0, 0.0, 0.0, 1), paint)
    col = mix_rgba(n, l, wm2.outputs["Value"], paint, (0.42, 0.40, 0.36, 1))
    l.new(col, b.inputs["Base Color"])
    # rugosidade / metalicidade
    rr = ramp(n, l, nz.outputs["Fac"], [(0.3, (rough - 0.18,) * 3 + (1,)), (0.7, (rough + 0.2,) * 3 + (1,))])
    rw = n.new("ShaderNodeMix"); rw.data_type = "FLOAT"
    l.new(wm2.outputs["Value"], rw.inputs[0]); l.new(rr.outputs["Color"], rw.inputs[2]); rw.inputs[3].default_value = 0.32
    # (saída de rr é cor; usa canal R via separar)
    sep = n.new("ShaderNodeSeparateColor"); l.new(rr.outputs["Color"], sep.inputs[0])
    l.new(sep.outputs[0], rw.inputs[2])
    l.new(rw.outputs[0], b.inputs["Roughness"])
    mt = n.new("ShaderNodeMath"); mt.operation = "MULTIPLY_ADD"
    l.new(wm2.outputs["Value"], mt.inputs[0]); mt.inputs[1].default_value = 0.35; mt.inputs[2].default_value = 0.62
    l.new(mt.outputs[0], b.inputs["Metallic"])
    bump = n.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 0.25; bump.inputs["Distance"].default_value = 0.01
    nz3 = n.new("ShaderNodeTexNoise"); nz3.inputs["Scale"].default_value = 120 * scale; nz3.inputs["Detail"].default_value = 4
    l.new(tc.outputs["Object"], nz3.inputs["Vector"])
    l.new(nz3.outputs["Fac"], bump.inputs["Height"])
    l.new(bump.outputs["Normal"], b.inputs["Normal"])
    return m

def mat_simple(name, color, rough=0.5, metal=0.0, emit=None, emit_strength=0.0, coat=0.0):
    m = mat_new(name); b = bsdf(m)
    b.inputs["Base Color"].default_value = tuple(color) + (1,)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    if coat: b.inputs["Coat Weight"].default_value = coat
    if emit:
        b.inputs["Emission Color"].default_value = tuple(emit) + (1,)
        b.inputs["Emission Strength"].default_value = emit_strength
    return m

OLIVE = (0.085, 0.115, 0.04)
M = {
    "olive": mat_metal("MET_Oliva_Envelhecido", OLIVE, 0.5, 1.0, 0.5),
    "olive_dark": mat_metal("MET_Oliva_Escuro", (0.05, 0.065, 0.025), 0.55, 0.9, 0.35),
    "olive_light": mat_metal("MET_Oliva_Claro", (0.15, 0.19, 0.06), 0.45, 1.2, 0.2),
    "dark": mat_metal("MET_Preto_Tecnico", (0.025, 0.027, 0.024), 0.5, 1.2, 0.1, 2.0),
    "steel": mat_simple("MET_Aco_Escovado", (0.45, 0.45, 0.43), 0.38, 1.0),
    "glass_dark": None,
    "screen": mat_simple("TELA_Provisoria", (0.004, 0.008, 0.005), 0.08, 0.0, (0.03, 0.5, 0.12), 0.1),
    "rubber": mat_simple("BORRACHA_Preta", (0.015, 0.015, 0.016), 0.4, coat=0.8),
    "cable": mat_simple("CABO_Preto", (0.02, 0.02, 0.02), 0.5),
    "white": mat_simple("TECIDO_Branco", (0.78, 0.76, 0.72), 0.6),
    "visor": mat_simple("VISOR_Preto", (0.005, 0.005, 0.006), 0.05, 0.6, coat=1.0),
    "ceramic": mat_simple("CERAMICA_Branca", (0.85, 0.85, 0.83), 0.12, coat=0.5),
    "nasa_blue": mat_simple("NASA_Azul", (0.005, 0.05, 0.4), 0.4),
    "nasa_white": mat_simple("NASA_Branco", (0.9, 0.9, 0.9), 0.5),
    "nasa_red": mat_simple("NASA_Vermelho", (0.7, 0.02, 0.01), 0.4),
    "orange": mat_simple("LED_Laranja", (0.3, 0.1, 0.01), 0.3, 0, (1.0, 0.38, 0.03), 14),
    "amber": mat_simple("LED_Ambar", (0.3, 0.14, 0.01), 0.2, 0, (1.0, 0.42, 0.04), 7),
    "lime": mat_simple("LED_Lima", (0.2, 0.3, 0.05), 0.3, 0, (0.7, 1.0, 0.25), 10),
    "red": mat_simple("LED_Vermelho", (0.3, 0.02, 0.0), 0.3, 0, (1.0, 0.07, 0.02), 14),
    "yellow": mat_simple("LED_Amarelo", (0.3, 0.25, 0.0), 0.3, 0, (1.0, 0.8, 0.05), 12),
}
# vidro das janelas: quase invisível
gl = mat_new("VIDRO_Janela"); n_, l_ = gl.node_tree.nodes, gl.node_tree.links
for nd in list(n_): n_.remove(nd)
tr = n_.new("ShaderNodeBsdfTransparent"); gx = n_.new("ShaderNodeBsdfGlossy"); gx.inputs["Roughness"].default_value = 0.02
fr = n_.new("ShaderNodeFresnel"); fr.inputs["IOR"].default_value = 1.45
mx = n_.new("ShaderNodeMixShader"); out_ = n_.new("ShaderNodeOutputMaterial")
l_.new(fr.outputs[0], mx.inputs[0]); l_.new(tr.outputs[0], mx.inputs[1]); l_.new(gx.outputs[0], mx.inputs[2]); l_.new(mx.outputs[0], out_.inputs[0])
M["glass"] = gl

# ----------------------------------------------------------------------------- helpers de geometria
def mesh_from(name, verts, faces):
    me = bpy.data.meshes.new(name); me.from_pydata([tuple(v) for v in verts], [], faces); me.update()
    bm = bmesh.new(); bm.from_mesh(me); bmesh.ops.recalc_face_normals(bm, faces=bm.faces); bm.to_mesh(me); bm.free()
    return me

def box_mesh(name, sx, sy, sz):
    hx, hy, hz = sx / 2, sy / 2, sz / 2
    v = [(-hx, -hy, -hz), (hx, -hy, -hz), (hx, hy, -hz), (-hx, hy, -hz), (-hx, -hy, hz), (hx, -hy, hz), (hx, hy, hz), (-hx, hy, hz)]
    return mesh_from(name, v, [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)])

def basis(x, z):
    x = Vector(x).normalized(); z = Vector(z); z = (z - x * z.dot(x)).normalized(); y = z.cross(x)
    return Matrix(((x.x, y.x, z.x, 0), (x.y, y.y, z.y, 0), (x.z, y.z, z.z, 0), (0, 0, 0, 1)))

def link(ob, col, mat=None, matrix=None):
    col.objects.link(ob)
    if mat is not None: ob.data.materials.append(mat)
    if matrix is not None: ob.matrix_world = matrix
    return ob

def finish(ob, bevel=0.006, seg=2):
    ob.data.shade_smooth()
    if bevel:
        b = ob.modifiers.new("Bisel", "BEVEL"); b.width = bevel; b.segments = seg
        b.limit_method = "ANGLE"; b.angle_limit = math.radians(35)
    w = ob.modifiers.new("NormaisPonderadas", "WEIGHTED_NORMAL"); w.keep_sharp = True
    return ob

def obox(name, center, xdir, zdir, size, mat, col, bevel=0.006):
    me = box_mesh(name, *size)
    mt = basis(xdir, zdir); mt.translation = Vector(center)
    return finish(link(bpy.data.objects.new(name, me), col, mat, mt), bevel)

def beam(name, a, b, w, t, nrm, mat, col, bevel=0.006):
    a, b = Vector(a), Vector(b)
    return obox(name, (a + b) / 2, b - a, nrm, ((b - a).length, w, t), mat, col, bevel)

_bolt_mesh = None
def bolt(name, pos, nrm, col, r=0.011):
    global _bolt_mesh
    if _bolt_mesh is None:
        bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=True, segments=6, radius1=1, radius2=0.9, depth=0.6)
        for v in bm.verts: v.co.z += 0.3
        _bolt_mesh = bpy.data.meshes.new("MalhaParafuso"); bm.to_mesh(_bolt_mesh); bm.free()
        _bolt_mesh.shade_smooth()
    ob = bpy.data.objects.new(name, _bolt_mesh)
    mt = basis(Vector(nrm).orthogonal(), nrm) @ Matrix.Scale(r, 4); mt.translation = Vector(pos)
    return link(ob, col, M["steel"], mt)

def prim(kind, name, loc, scale, mat, col, rot=(0, 0, 0), seg=24):
    bm = bmesh.new()
    if kind == "sphere": bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=seg // 2, radius=1)
    elif kind == "cyl": bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=1, radius2=1, depth=2)
    elif kind == "cone": bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=1, radius2=0.45, depth=2)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free(); me.shade_smooth()
    ob = bpy.data.objects.new(name, me); link(ob, col, mat)
    ob.location = Vector(loc); ob.scale = Vector(scale); ob.rotation_euler = Euler(rot)
    return ob

def prism(name, pts, ext, mat, col, bevel=0.004):
    """Polígono + extrusão ao longo do vetor ext."""
    n = len(pts); v = list(pts) + [Vector(p) + Vector(ext) for p in pts]
    f = [tuple(range(n)), tuple(range(2 * n - 1, n - 1, -1))]
    for i in range(n): f.append((i, (i + 1) % n, n + (i + 1) % n, n + i))
    ob = bpy.data.objects.new(name, mesh_from(name, v, f)); link(ob, col, mat)
    return finish(ob, bevel)

def rect3d(center, w, h, yaw=0, tilt=0):
    """Retângulo 3D que olha pra câmera. yaw: giro em Z; tilt: topo inclinado pra trás."""
    Mx = Matrix.Rotation(math.radians(yaw), 3, "Z") @ Matrix.Rotation(math.radians(-tilt), 3, "X")
    r, u = Mx @ Vector((1, 0, 0)), Mx @ Vector((0, 0, 1))
    c = Vector(center)
    return c - r * w / 2 + u * h / 2, c + r * w / 2 + u * h / 2, c + r * w / 2 - u * h / 2, c - r * w / 2 - u * h / 2, r, u

def monitor(name, center, w, h, yaw, tilt, border, thick, depth_back=0.2):
    """Moldura grossa + tela SEPARADA (SCR_*) + caixa traseira + cantoneiras chanfradas."""
    A, B, C, D, r, u = rect3d(center, w, h, yaw, tilt)
    n = r.cross(u)
    if n.dot(CAM_LOC - Vector(center)) < 0: n = -n
    bw, bh = border, border
    def Q(uu, vv): return A + (B - A) * uu + (D - A) * vv
    t = thick
    beam(f"MON_{name}_Moldura_Sup", Q(0, bh / h / 2), Q(1, bh / h / 2), bh, t, n, M["olive"], COLL["mon"], 0.008)
    beam(f"MON_{name}_Moldura_Inf", Q(0, 1 - bh / h / 2 * 1.35), Q(1, 1 - bh / h / 2 * 1.35), bh * 1.35, t, n, M["olive"], COLL["mon"], 0.008)
    beam(f"MON_{name}_Moldura_Esq", Q(bw / w / 2, 0), Q(bw / w / 2, 1), bw, t * 0.9, n, M["olive_light"], COLL["mon"], 0.008)
    beam(f"MON_{name}_Moldura_Dir", Q(1 - bw / w / 2, 0), Q(1 - bw / w / 2, 1), bw, t * 0.9, n, M["olive_light"], COLL["mon"], 0.008)
    obox(f"MON_{name}_Caixa_Traseira", Vector(center) - n * (t / 2 + depth_back / 2 - 0.01), r, n, (w * 0.96, h * 0.96, depth_back), M["olive_dark"], COLL["mon"], 0.01)
    iw, ih = w - 2 * bw, h - bh - bh * 1.35
    sc = Vector(center) + u * (bh * 0.175) - n * (t * 0.28)
    scr = obox(f"SCR_{name}_Tela", sc, r, n, (iw, ih, 0.006), M["screen"], COLL["mon"], 0)
    # cantoneiras 45° nos cantos da tela
    for i, (uu, vv) in enumerate([(bw / w, bh / h), (1 - bw / w, bh / h), (1 - bw / w, 1 - bh * 1.35 / h), (bw / w, 1 - bh * 1.35 / h)]):
        pos = Q(uu, vv) + n * (t * 0.38)
        ob = obox(f"MON_{name}_Cantoneira_{i}", pos, r, n, (bw * 0.9, bw * 0.9, t * 0.35), M["olive_dark"], COLL["mon"], 0.004)
        ob.rotation_mode = "QUATERNION"
        ob.matrix_world = ob.matrix_world @ Matrix.Rotation(math.radians(45), 4, "Z")
    for i, (uu, vv) in enumerate([(0.012, 0.015), (0.988, 0.015), (0.988, 0.985), (0.012, 0.985)]):
        bolt(f"MON_{name}_Parafuso_{i}", Q(uu, vv) + n * (t / 2 - 0.002), n, COLL["mon"], 0.008)
    # luz verde que a tela projeta no ambiente
    lt = bpy.data.lights.new(f"LUZ_Tela_{name}", "AREA"); lt.color = (0.2, 1.0, 0.35); lt.shape = "RECTANGLE"
    lt.size, lt.size_y = iw, ih; lt.energy = 22 * iw * ih / 0.2
    lo = bpy.data.objects.new(f"LUZ_Tela_{name}", lt); COLL["lit"].objects.link(lo)
    lo.visible_glossy = False; lo.visible_camera = False
    lo.matrix_world = basis(r, n) @ Matrix.Identity(4)
    lo.matrix_world = Matrix(((r.x, -u.x, -n.x, 0), (r.y, -u.y, -n.y, 0), (r.z, -u.z, -n.z, 0), (0, 0, 0, 1)))
    lo.matrix_world.translation = sc + n * 0.05
    return A, B, C, D, r, u, n, sc, scr

def add_light(name, kind, loc, color, power, size=0.05, target=None, spot=None):
    lt = bpy.data.lights.new(name, kind); lt.color = color; lt.energy = power
    if kind == "POINT": lt.shadow_soft_size = size
    if kind == "AREA": lt.size = size
    ob = bpy.data.objects.new(name, lt); COLL["lit"].objects.link(ob); ob.location = Vector(loc)
    if kind == "AREA": ob.visible_glossy = False; ob.visible_camera = False
    if target is not None:
        ob.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    return ob

# ----------------------------------------------------------------------------- 01 ESTRUTURA DA CABINE (carcaça interna)
def build_shell():
    c = COLL["cab"]
    # painel do console: perfil lateral (parede inclinada atrás dos monitores + prateleira dos botões) extrudado em X
    prof = [(398, 2.4), (780, 1.78), (780, 1.52), (908, 0.82)]
    pts = []
    for py, d in prof:
        q = P(800, py, d); pts.append(Vector((-4.5, q.y, q.z)))
    pts += [Vector((-4.5, 0.5, -0.6)), Vector((-4.5, 2.6, -0.6))]
    pts = [pts[0], pts[1], pts[2], pts[3], pts[4], pts[5]]
    prism("CAB_Painel_Console_Base", pts, (9, 0, 0), M["dark"], c, 0.01)
    # borda superior do painel (a "soleira" brilhante sob as janelas)
    beam("CAB_Soleira_Janelas", P(-260, 392, dash_d(398) - 0.05), P(1860, 392, dash_d(398) - 0.05), 0.11, 0.08, (0, 0, 1), M["olive_light"], c, 0.012)
    # teto / painel superior com recorte das janelas
    pieces = {"Centro": [P(515, -400, 3.25), P(1085, -400, 3.25), P(1085, 68, 3.25), P(515, 68, 3.25)],
              "Esq": [P(-500, -400, 2.2), P(515, -400, 3.25), P(515, 68, 3.25), P(405, 118, 2.9), P(0, 140, 2.0), P(-500, 150, 1.9)],
              "Dir": [P(1085, -400, 3.25), P(2100, -400, 2.2), P(2100, 150, 1.9), P(1600, 140, 2.0), P(1195, 118, 2.9), P(1085, 68, 3.25)]}
    for k, pp in pieces.items():
        prism(f"CAB_Painel_Superior_{k}", pp, (0, 0.35, 0.05), M["dark"], c, 0.01)
    beam("CAB_Viga_Superior", P(360, 38, 3.0), P(1240, 38, 3.0), 0.16, 0.16, (0, -1, 0), M["olive"], c, 0.012)
    # paredes laterais, piso e fundo (para olhar ao redor sem ver vazio)
    obox("CAB_Parede_Esq", (-2.4, 0.5, 0.9), (0, 1, 0), (1, 0, 0), (7, 3.0, 0.12), M["olive_dark"], c, 0.01)
    obox("CAB_Parede_Dir", (2.4, 0.5, 0.9), (0, 1, 0), (-1, 0, 0), (7, 3.0, 0.12), M["olive_dark"], c, 0.01)
    obox("CAB_Piso", (0, 0.5, -0.45), (1, 0, 0), (0, 0, 1), (5, 7, 0.1), M["dark"], c, 0.01)
    obox("CAB_Parede_Fundo", (0, -3.4, 0.9), (1, 0, 0), (0, 1, 0), (5, 3.0, 0.1), M["olive_dark"], c, 0.01)
    obox("CAB_Teto_Interno", (0, 0.0, 2.35), (1, 0, 0), (0, 0, -1), (5, 7, 0.1), M["olive_dark"], c, 0.01)
    # painéis laterais do console, nervuras e suportes
    for s, nm in ((-1, "Esq"), (1, "Dir")):
        for i, y in enumerate((1.2, 0.7, 0.2)):
            obox(f"CAB_Nervura_{nm}_{i}", (s * 2.3, y, 0.9), (0, 0, 1), (-s, 0, 0), (0.12, 0.2, 2.8), M["olive"], c, 0.01)
    # suportes em L sob o painel
    for i, px in enumerate((120, 440, 812, 1180, 1480)):
        beam(f"CAB_Suporte_{i}", P(px, 640, dash_d(640)), P(px, 905, dash_d(905) - 0.15) - Vector((0, 0, 0.35)), 0.07, 0.07, (1, 0, 0), M["olive"], c, 0.008)

# ----------------------------------------------------------------------------- 02 JANELAS (estrutura diagonal)
def build_windows():
    c = COLL["win"]
    def w_beam(nm, a, b, wdt, thk=0.16, mat="olive", bolts=True):
        A, B = P(*a), P(*b)
        beam(nm, A, B, wdt, thk, (0, -1, 0), M[mat], c, 0.012)
        if bolts:
            ln = (B - A).length; k = max(2, int(ln / 0.32))
            for i in range(k + 1):
                p = A + (B - A) * (i / k) + Vector((0, -thk / 2 - 0.0, 0))
                bolt(f"{nm}_Parafuso_{i}", p, (0, -1, 0), c, 0.012)
    # esquerda
    w_beam("WIN_Viga_Esq_Principal", (500, 95, 3.3), (55, 455, 2.5), 0.17, 0.14)
    w_beam("WIN_Viga_Esq_Secundaria", (338, 135, 3.0), (30, 380, 2.3), 0.09, 0.1, "olive_light")
    w_beam("WIN_Viga_Esq_Interna", (548, 72, 3.2), (642, 380, 3.2), 0.07, 0.1, "olive_light", False)
    # direita
    w_beam("WIN_Viga_Dir_Principal", (1100, 95, 3.3), (1545, 455, 2.5), 0.17, 0.14)
    w_beam("WIN_Viga_Dir_Secundaria", (1262, 135, 3.0), (1570, 380, 2.3), 0.09, 0.1, "olive_light")
    w_beam("WIN_Viga_Dir_Interna", (1052, 72, 3.2), (958, 380, 3.2), 0.07, 0.1, "olive_light", False)
    # barras do topo da janela central e soleira inferior
    w_beam("WIN_Travessa_Superior", (520, 72, 3.2), (1080, 72, 3.2), 0.12, 0.14, "olive")
    w_beam("WIN_Travessa_Inferior", (640, 380, 3.2), (960, 380, 3.2), 0.1, 0.12, "olive_dark", False)
    # faixa laranja luminosa na viga direita
    a, b = P(1212, 108, 3.0), P(1428, 385, 2.5)
    beam("WIN_Faixa_Laranja_Dir", a + Vector((0, -0.1, 0)), b + Vector((0, -0.1, 0)), 0.022, 0.02, (0, -1, 0), M["amber"], c, 0)
    add_light("LUZ_Faixa_Laranja", "AREA", (a + b) / 2 + Vector((-0.2, -0.3, 0)), (1.0, 0.45, 0.08), 70, 0.5,
              target=(a + b) / 2 + Vector((-0.8, -1.2, -0.3)))
    # lâmpadas do topo
    for i, px in enumerate((532, 1068)):
        pos = P(px, 14, 2.9)
        prim("cyl", f"WIN_Lampada_Base_{i}", pos + Vector((0, -0.04, 0)), (0.1, 0.07, 0.1), M["dark"], c, (math.pi / 2, 0, 0), 20)
        prim("sphere", f"WIN_Lampada_Luz_{i}", pos + Vector((0, -0.13, -0.015)), (0.085, 0.07, 0.085), M["amber"], c, (0, 0, 0), 20)
        add_light(f"LUZ_Lampada_Topo_{i}", "POINT", pos + Vector((0, -0.3, -0.12)), (1.0, 0.5, 0.1), 38, 0.06)
    # vidros
    for nm, pts in (("Central", [P(555, 80, 3.2), P(1045, 80, 3.2), P(955, 378, 3.2), P(645, 378, 3.2)]),
                    ("Esq", [P(0, 180, 1.95), P(500, 110, 3.1), P(630, 378, 3.2), P(0, 450, 1.9)]),
                    ("Dir", [P(1600, 180, 1.95), P(1100, 110, 3.1), P(970, 378, 3.2), P(1600, 450, 1.9)])):
        ob = bpy.data.objects.new(f"WIN_Vidro_{nm}", mesh_from(f"WIN_Vidro_{nm}", pts, [(0, 1, 2, 3)]))
        link(ob, c, M["glass"]); ob.visible_shadow = False

# ----------------------------------------------------------------------------- 03/04/05 CONSOLE, MONITORES, CONTROLES
def build_console():
    cc, cm, ck = COLL["con"], COLL["mon"], COLL["ctl"]
    # --- monitor central (computador principal)
    cen = monitor("Central", P(812, 588, 1.62), 0.84, 0.47, 0, 14, 0.065, 0.1)
    global CENTRAL
    CENTRAL = cen
    # --- monitor direito (Local C)
    monitor("Direito", P(1312, 612, 1.42), 0.36, 0.33, -26, 10, 0.05, 0.08)
    # --- monitor esquerdo (módulo lunar) + prateleira
    monitor("Esquerdo", P(305, 650, 1.4), 0.34, 0.26, 24, 10, 0.05, 0.1)
    # lateral esquerda: carcaça maior que serve de prateleira para o astronauta
    obox("CON_Carcaca_Esquerda", P(305, 640, 1.52), (1, 0, 0), (0, 0, 1), (0.42, 0.3, 0.3), M["olive_dark"], cc, 0.012)
    # --- painel de botões inferior
    # --- grelhas
    for i in range(9):
        obox(f"CON_Grelha_Esq_{i}", P(470 + i * 14, 850, 1.0), (0, 0, 1), (0, -1, 0.3), (0.006, 0.09, 0.03), M["dark"], cc, 0)
    obox("CON_Grelha_Esq_Base", P(530, 850, 1.01), (1, 0, 0), (0, -1, 0.3), (0.16, 0.12, 0.02), M["olive_dark"], cc, 0.004)
    for i in range(7):
        obox(f"CON_Grelha_Dir_{i}", P(1210 + i * 15, 870, 0.98), (1, 0, 0), (0, -1, 0.4), (0.014, 0.1, 0.004), M["dark"], cc, 0)
    # --- botões iluminados
    for i, (px, mat) in enumerate((("650", "orange"), ("724", "orange"), ("798", "lime"), ("884", "lime"), ("968", "lime"))):
        px = float(px); d = dash_d(808) - 0.012
        obox(f"BTN_Retangular_{i}", P(px, 808, d), (1, 0, 0), (0, -0.55, 1), (0.062 if i > 1 else 0.05, 0.03, 0.022), M[mat], ck, 0.003)
        obox(f"BTN_Base_{i}", P(px, 810, d + 0.005), (1, 0, 0), (0, -0.55, 1), (0.072 if i > 1 else 0.06, 0.04, 0.012), M["dark"], ck, 0.003)
    for i, (px, mat) in enumerate(((1128, "red"), (1196, "yellow"))):
        d = dash_d(815) - 0.03
        prim("cyl", f"BTN_Redondo_{i}", P(px, 815, d), (0.026, 0.026, 0.01), M[mat], ck, (math.radians(-60), 0, 0), 20)
        prim("cyl", f"BTN_Aro_{i}", P(px, 817, d + 0.006), (0.034, 0.034, 0.008), M["dark"], ck, (math.radians(-60), 0, 0), 20)
    # luzes de painel (esquerda inferior e direita)
    obox("LED_Painel_Esq", P(22, 730, 1.0), (1, 0, 0), (0, -1, 0), (0.09, 0.03, 0.05), M["orange"], ck, 0.004)
    obox("LED_Painel_Esq_Mold", P(22, 735, 1.02), (1, 0, 0), (0, -1, 0), (0.13, 0.04, 0.09), M["dark"], cc, 0.006)
    add_light("LUZ_Painel_Esq", "POINT", P(60, 720, 0.8), (1.0, 0.4, 0.08), 6, 0.05)
    for i, (px, py) in enumerate(((1562, 590), (1545, 640))):
        obox(f"LED_Painel_Dir_{i}", P(px, py, 1.15), (1, 0, 0), (0, -1, 0), (0.05, 0.02, 0.05), M["orange"], ck, 0.004)
    # interruptores e pequenos detalhes no painel
    for i in range(6):
        px = 1120 + i * 38; py = 870
        prim("cyl", f"CON_Interruptor_{i}", P(px, py, dash_d(py) - 0.01), (0.007, 0.007, 0.014), M["steel"], ck, (math.radians(-55), 0, 0), 12)
    # cabos na esquerda
    for k, pts in enumerate(([(0, 590, 1.1), (60, 640, 1.0), (110, 700, 0.9), (170, 760, 0.95)],
                             [(0, 625, 1.1), (50, 690, 1.0), (140, 740, 0.9), (200, 830, 0.85)])):
        cu = bpy.data.curves.new(f"CABO_{k}", "CURVE"); cu.dimensions = "3D"; cu.bevel_depth = 0.007; cu.bevel_resolution = 3
        sp = cu.splines.new("BEZIER"); sp.bezier_points.add(len(pts) - 1)
        for bp, pp in zip(sp.bezier_points, pts):
            bp.co = P(*pp); bp.handle_left_type = bp.handle_right_type = "AUTO"
        ob = bpy.data.objects.new(f"CON_Cabo_{k}", cu); link(ob, cc, M["cable"])
    # joystick
    jb = P(415, 905, 0.95)
    prim("cone", "CTL_Joystick_Base", jb, (0.075, 0.075, 0.05), M["dark"], ck, (0, 0, 0), 28)
    prim("cyl", "CTL_Joystick_Haste", jb + Vector((0, 0, 0.1)), (0.022, 0.022, 0.12), M["rubber"], ck, (0, 0, 0), 20)
    prim("sphere", "CTL_Joystick_Pomo", P(415, 778, 0.95), (0.052, 0.052, 0.062), M["rubber"], ck, (0, 0, 0), 32)
    prim("cyl", "CTL_Joystick_Anel", P(415, 835, 0.95), (0.034, 0.034, 0.006), M["steel"], ck, (0, 0, 0), 20)
    add_light("LUZ_Console_Baixo", "AREA", P(850, 700, 0.7), (1.0, 0.45, 0.1), 9, 0.4, target=P(850, 880, 1.0))

# ----------------------------------------------------------------------------- 06 OBJETOS DECORATIVOS
def nasa_logo(name, center, normal, radius, col):
    n = Vector(normal).normalized(); r = Vector((0, 0, 1)).cross(n).normalized()
    mt = basis(r, n); mt.translation = Vector(center)
    d = prim("cyl", f"{name}_Disco", (0, 0, 0), (radius, radius, 0.0012), M["nasa_blue"], col, (0, 0, 0), 28)
    d.matrix_world = mt @ Matrix.Diagonal((radius, radius, 0.0012, 1.0))
    cu = bpy.data.curves.new(f"{name}_Texto", "FONT"); cu.body = "NASA"; cu.align_x = "CENTER"; cu.align_y = "CENTER"
    cu.size = radius * 0.62; cu.extrude = 0.0002
    t = bpy.data.objects.new(f"{name}_Texto", cu); link(t, col, M["nasa_white"])
    t.matrix_world = mt @ Matrix.Translation((0, -radius * 0.05, 0.0016))
    cs = bpy.data.curves.new(f"{name}_Orbita", "CURVE"); cs.dimensions = "3D"; cs.bevel_depth = radius * 0.035
    sp = cs.splines.new("BEZIER"); sp.bezier_points.add(2)
    for bp, (x, y) in zip(sp.bezier_points, [(-1.15, -0.55), (0.0, -0.05), (1.15, 0.75)]):
        bp.co = (x * radius, y * radius, 0.002); bp.handle_left_type = bp.handle_right_type = "AUTO"
    s = bpy.data.objects.new(f"{name}_Orbita", cs); link(s, col, M["nasa_red"]); s.matrix_world = mt

def build_decor():
    c = COLL["dec"]
    # --- astronauta (miniatura ~15 cm) sobre a carcaça esquerda
    base = P(362, 538, 1.46)
    H = 0.155
    def ap(kind, nm, loc, sc, mat, rot=(0, 0, 0)):
        return prim(kind, f"DEC_Astronauta_{nm}", base + Vector(loc) * H, Vector(sc) * H, mat, c, rot, 20)
    for s, sx in ((-1, "E"), (1, "D")):
        ap("sphere", f"Bota_{sx}", (s * 0.1, -0.03, 0.05), (0.075, 0.11, 0.05), M["white"])
        ap("cyl", f"Perna_{sx}", (s * 0.1, 0, 0.24), (0.065, 0.065, 0.17), M["white"])
        ap("cyl", f"Braco_{sx}", (s * 0.24, -0.03, 0.55), (0.055, 0.055, 0.15), M["white"], (0, s * math.radians(14), 0))
        ap("sphere", f"Luva_{sx}", (s * 0.28, -0.04, 0.38), (0.06, 0.06, 0.06), M["white"])
    ap("sphere", "Torso", (0, 0, 0.55), (0.23, 0.15, 0.2), M["white"])
    ap("cyl", "Cintura", (0, 0, 0.38), (0.19, 0.12, 0.04), M["white"])
    ap("sphere", "Mochila", (0, 0.15, 0.55), (0.17, 0.08, 0.19), M["white"])
    ap("sphere", "Capacete", (0, 0, 0.84), (0.185, 0.17, 0.17), M["white"])
    ap("sphere", "Visor", (0, -0.075, 0.845), (0.135, 0.1, 0.12), M["visor"])
    nasa_logo("DEC_Astronauta_Logo", base + Vector((0.07, -0.152, 0.56)) * H, (0, -1, 0), 0.028, c)
    # --- luminária âmbar
    lp = P(262, 538, 1.5)
    prim("cyl", "DEC_Luminaria_Base", lp + Vector((0, 0, 0.012)), (0.036, 0.036, 0.014), M["dark"], c, (0, 0, 0), 20)
    prim("cyl", "DEC_Luminaria_Vidro", lp + Vector((0, 0, 0.088)), (0.033, 0.033, 0.065), M["amber"], c, (0, 0, 0), 24)
    prim("cyl", "DEC_Luminaria_Tampa", lp + Vector((0, 0, 0.158)), (0.036, 0.036, 0.011), M["dark"], c, (0, 0, 0), 20)
    add_light("LUZ_Luminaria", "POINT", lp + Vector((0, -0.05, 0.09)), (1.0, 0.45, 0.08), 7, 0.03)
    # --- caneca com logo NASA (cortada pela borda direita, como na referência)
    mp = P(1522, 802, 0.8)
    prim("cyl", "DEC_Caneca_Corpo", mp, (0.042, 0.042, 0.048), M["ceramic"], c, (0, 0, 0), 40)
    prim("cyl", "DEC_Caneca_Interior", mp + Vector((0, 0, 0.046)), (0.036, 0.036, 0.002), M["dark"], c, (0, 0, 0), 32)
    hd = bpy.data.curves.new("DEC_Caneca_Alca", "CURVE"); hd.dimensions = "3D"; hd.bevel_depth = 0.009
    sp = hd.splines.new("BEZIER"); sp.bezier_points.add(2)
    for bp, p in zip(sp.bezier_points, [(0.04, 0.0, 0.032), (0.085, 0.0, 0.0), (0.04, 0.0, -0.032)]):
        bp.co = Vector(p); bp.handle_left_type = bp.handle_right_type = "AUTO"
    ho = bpy.data.objects.new("DEC_Caneca_Alca", hd); link(ho, c, M["ceramic"]); ho.location = mp
    ho.rotation_euler = (0, 0, math.radians(-20))
    toward = (CAM_LOC - mp); toward.z = 0; toward.normalize()
    nasa_logo("DEC_Caneca_Logo", mp + toward * 0.0425 + Vector((0, 0, 0.0)), toward, 0.027, c)

# ----------------------------------------------------------------------------- 07 TERRENO LUNAR
CRATERS = []
def terrain_h(x, y):
    r = math.hypot(x, y)
    h = noise.fractal(Vector((x * 0.012, y * 0.012, 0.3)), 1.0, 2.0, 5) * 3.2
    h += noise.fractal(Vector((x * 0.09, y * 0.09, 4.1)), 1.0, 2.0, 4) * 0.28
    for (cx, cy, cr, cd) in CRATERS:
        d = math.hypot(x - cx, y - cy)
        if d < cr * 1.5:
            q = d / cr
            if q < 1: h -= cd * (1 - q * q) ** 1.3
            h += cd * 0.28 * math.exp(-((q - 1.0) / 0.16) ** 2)
    mt = max(0.0, min(1.0, (r - 380) / 900.0))
    ridge = 1.0 - abs(noise.fractal(Vector((x * 0.0028, y * 0.0028, 9.0)), 1.0, 2.0, 5))
    h += mt * mt * (max(0.0, ridge) ** 2.2) * 130
    return h

def build_terrain():
    c = COLL["ter"]
    global CRATERS
    for _ in range(46):
        CRATERS.append((random.uniform(-110, 110), random.uniform(35, 260), random.uniform(5, 22), random.uniform(0.6, 3.5)))
    for _ in range(14):
        CRATERS.append((random.uniform(-500, 500), random.uniform(250, 900), random.uniform(40, 120), random.uniform(5, 18)))
    # malha polar com anéis exponenciais: alta resolução perto, barata longe
    n_r, n_a = 190, 300
    rings = [3.0 * (3000 / 3.0) ** (i / (n_r - 1)) for i in range(n_r)]
    verts, faces = [], []
    for ri, r in enumerate(rings):
        for ai in range(n_a):
            a = 2 * math.pi * ai / n_a
            x, y = r * math.sin(a), r * math.cos(a)             # a=0 aponta para +Y (frente da cabine)
            verts.append((x, y, -3.0 + terrain_h(x, y)))
    for ri in range(n_r - 1):
        for ai in range(n_a):
            a2 = (ai + 1) % n_a
            faces.append((ri * n_a + ai, ri * n_a + a2, (ri + 1) * n_a + a2, (ri + 1) * n_a + ai))
    me = bpy.data.meshes.new("TER_Superficie"); me.from_pydata(verts, [], faces); me.update(); me.shade_smooth()
    ob = bpy.data.objects.new("TER_Superficie_Lunar", me); c.objects.link(ob)
    # material regolito
    m = mat_new("TER_Regolito"); n, l = m.node_tree.nodes, m.node_tree.links; b = bsdf(m)
    tc = n.new("ShaderNodeTexCoord")
    n1 = n.new("ShaderNodeTexNoise"); n1.inputs["Scale"].default_value = 0.35; n1.inputs["Detail"].default_value = 10
    l.new(tc.outputs["Object"], n1.inputs["Vector"])
    n2 = n.new("ShaderNodeTexNoise"); n2.inputs["Scale"].default_value = 3.0; n2.inputs["Detail"].default_value = 10
    l.new(tc.outputs["Object"], n2.inputs["Vector"])
    rr = ramp(n, l, n1.outputs["Fac"], [(0.3, (0.05, 0.04, 0.035, 1)), (0.7, (0.17, 0.13, 0.105, 1))])
    l.new(rr.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.93
    bp = n.new("ShaderNodeBump"); bp.inputs["Strength"].default_value = 0.6; bp.inputs["Distance"].default_value = 0.4
    l.new(n2.outputs["Fac"], bp.inputs["Height"]); l.new(bp.outputs["Normal"], b.inputs["Normal"])
    ob.data.materials.append(m)
    # rochas (10 variações instanciadas)
    rock_m = mat_simple("TER_Rocha", (0.13, 0.12, 0.11), 0.85)
    nz = n_ = None
    rm = rock_m; nn, ll = rm.node_tree.nodes, rm.node_tree.links; bb = bsdf(rm)
    t2 = nn.new("ShaderNodeTexCoord"); nx = nn.new("ShaderNodeTexNoise"); nx.inputs["Scale"].default_value = 6; nx.inputs["Detail"].default_value = 8
    ll.new(t2.outputs["Object"], nx.inputs["Vector"])
    r2 = ramp(nn, ll, nx.outputs["Fac"], [(0.35, (0.07, 0.065, 0.06, 1)), (0.7, (0.24, 0.22, 0.2, 1))])
    ll.new(r2.outputs["Color"], bb.inputs["Base Color"])
    bm2 = nn.new("ShaderNodeBump"); bm2.inputs["Strength"].default_value = 0.5; ll.new(nx.outputs["Fac"], bm2.inputs["Height"]); ll.new(bm2.outputs["Normal"], bb.inputs["Normal"])
    variants = []
    for i in range(10):
        bm = bmesh.new(); bmesh.ops.create_icosphere(bm, subdivisions=3, radius=1.0)
        seed = random.uniform(0, 100)
        for v in bm.verts:
            p = v.co
            k = 1 + 0.38 * noise.fractal(Vector((p.x * 1.6 + seed, p.y * 1.6, p.z * 1.6)), 1.0, 2.0, 3)
            v.co = p * k
            v.co.z = max(v.co.z, -0.35)
        me = bpy.data.meshes.new(f"TER_Rocha_Malha_{i}"); bm.to_mesh(me); bm.free(); me.shade_smooth(); me.materials.append(rock_m)
        variants.append(me)
    for i in range(260):
        dist = random.choice((random.uniform(14, 60), random.uniform(30, 160), random.uniform(80, 420)))
        ang = random.gauss(0, 0.62)
        x, y = dist * math.sin(ang), dist * math.cos(ang)
        s = random.uniform(0.2, 0.9) * (1 + dist / 45) ** 0.9
        o = bpy.data.objects.new(f"TER_Rocha_{i:03d}", random.choice(variants))
        c.objects.link(o)
        o.location = (x, y, -3.0 + terrain_h(x, y) + s * 0.1)
        o.rotation_euler = (random.uniform(-0.2, 0.2), random.uniform(-0.2, 0.2), random.uniform(0, 6.28))
        o.scale = (s * random.uniform(0.8, 1.5), s * random.uniform(0.7, 1.3), s * random.uniform(0.45, 0.8))

# ----------------------------------------------------------------------------- 08 TERRA
def build_earth():
    c = COLL["ear"]
    pos = P(832, 218, 420); rad = 110 * 420 / F * 1.0
    e = prim("sphere", "TERRA_Esfera", pos, (rad, rad, rad), None, c, (math.radians(70), 0, math.radians(35)), 96)
    m = mat_new("TERRA_Superficie"); n, l = m.node_tree.nodes, m.node_tree.links; b = bsdf(m)
    tc = n.new("ShaderNodeTexCoord")
    nz = n.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 2.4; nz.inputs["Detail"].default_value = 8; nz.inputs["Roughness"].default_value = 0.55
    l.new(tc.outputs["Object"], nz.inputs["Vector"])
    land = ramp(n, l, nz.outputs["Fac"], [(0.0, (0.01, 0.04, 0.2, 1)), (0.46, (0.015, 0.08, 0.3, 1)), (0.5, (0.1, 0.085, 0.04, 1)), (0.65, (0.2, 0.15, 0.07, 1)), (0.8, (0.08, 0.1, 0.035, 1))])
    cl = n.new("ShaderNodeTexNoise"); cl.inputs["Scale"].default_value = 3.6; cl.inputs["Detail"].default_value = 10; cl.inputs["Distortion"].default_value = 0.6
    l.new(tc.outputs["Object"], cl.inputs["Vector"])
    cm = ramp(n, l, cl.outputs["Fac"], [(0.5, (0, 0, 0, 1)), (0.64, (1, 1, 1, 1))])
    col = mix_rgba(n, l, cm.outputs["Color"], land.outputs["Color"], (0.6, 0.62, 0.66, 1))
    l.new(col, b.inputs["Base Color"]); b.inputs["Roughness"].default_value = 0.55
    b.inputs["Emission Color"].default_value = (0.05, 0.12, 0.3, 1); b.inputs["Emission Strength"].default_value = 0.04
    e.data.materials.append(m)
    # atmosfera azul discreta
    a = prim("sphere", "TERRA_Atmosfera", pos, (rad * 1.035,) * 3, None, c, (0, 0, 0), 64)
    am = mat_new("TERRA_Atmosfera"); n, l = am.node_tree.nodes, am.node_tree.links
    for nd in list(n): n.remove(nd)
    lw = n.new("ShaderNodeLayerWeight"); lw.inputs["Blend"].default_value = 0.78
    pw = n.new("ShaderNodeMath"); pw.operation = "POWER"; pw.inputs[1].default_value = 2.2
    l.new(lw.outputs["Facing"], pw.inputs[0])
    inv = n.new("ShaderNodeMath"); inv.operation = "SUBTRACT"; inv.inputs[0].default_value = 1.0
    l.new(pw.outputs[0], inv.inputs[1]); inv.operation = 'MULTIPLY'; inv.inputs[0].default_value = 1.0; inv.inputs[1].default_value = 1.0
    cl2 = n.new("ShaderNodeMath"); cl2.operation = "MULTIPLY"; cl2.inputs[1].default_value = 0.7
    l.new(inv.outputs[0], cl2.inputs[0])
    em = n.new("ShaderNodeEmission"); em.inputs["Color"].default_value = (0.25, 0.55, 1.0, 1); em.inputs["Strength"].default_value = 0.8
    tr = n.new("ShaderNodeBsdfTransparent"); mx = n.new("ShaderNodeMixShader"); out = n.new("ShaderNodeOutputMaterial")
    l.new(inv.outputs[0], mx.inputs[0]); l.new(tr.outputs[0], mx.inputs[1]); l.new(em.outputs[0], mx.inputs[2]); l.new(mx.outputs[0], out.inputs[0])
    a.data.materials.append(am); a.visible_shadow = False

# ----------------------------------------------------------------------------- 09 CÉU + luz solar
def build_sky():
    w = bpy.data.worlds.new("CEU_Espacial"); scene.world = w; w.use_nodes = True
    n, l = w.node_tree.nodes, w.node_tree.links
    for nd in list(n): n.remove(nd)
    tc = n.new("ShaderNodeTexCoord")
    vo = n.new("ShaderNodeTexVoronoi"); vo.inputs["Scale"].default_value = 420; vo.inputs["Randomness"].default_value = 1.0
    l.new(tc.outputs["Generated"], vo.inputs["Vector"])
    st = ramp(n, l, vo.outputs["Distance"], [(0.0, (1, 1, 1, 1)), (0.045, (0, 0, 0, 1))])
    nz = n.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 30
    l.new(tc.outputs["Generated"], nz.inputs["Vector"])
    br = ramp(n, l, nz.outputs["Fac"], [(0.4, (0.1, 0.1, 0.1, 1)), (0.7, (1, 1, 1, 1))])
    mul = n.new("ShaderNodeMix"); mul.data_type = "RGBA"; mul.blend_type = "MULTIPLY"; mul.inputs[0].default_value = 1.0
    l.new(st.outputs["Color"], mul.inputs[6]); l.new(br.outputs["Color"], mul.inputs[7])
    bg = n.new("ShaderNodeBackground"); bg.inputs["Strength"].default_value = 1.6
    l.new(mul.outputs[2], bg.inputs["Color"])
    out = n.new("ShaderNodeOutputWorld"); l.new(bg.outputs[0], out.inputs[0])
    # sol
    sun = bpy.data.lights.new("LUZ_Sol", "SUN"); sun.energy = 3.0; sun.angle = math.radians(0.6); sun.color = (1.0, 0.97, 0.92)
    so = bpy.data.objects.new("LUZ_Sol", sun); COLL["lit"].objects.link(so)
    so.rotation_euler = Vector((-0.85, 0.3, -0.5)).to_track_quat("-Z", "Y").to_euler()
    # fill frio muito fraco
    add_light("LUZ_Preenchimento_Frio", "AREA", (0, -0.6, 2.0), (0.6, 0.7, 0.85), 70, 1.5, target=(0, 1.2, 0.6))
    add_light("LUZ_Preenchimento_Quente", "AREA", (-0.8, -0.3, 1.6), (1.0, 0.5, 0.15), 45, 1.0, target=(0.0, 1.5, 1.0))
    add_light("LUZ_Preenchimento_Quente_Dir", "AREA", (0.9, -0.3, 1.6), (1.0, 0.5, 0.15), 40, 1.0, target=(0.0, 1.5, 1.0))
    e = bpy.data.objects.new("CEU_Referencia_Skybox", None); COLL["sky"].objects.link(e)  # marcador: céu é o World procedural

# ----------------------------------------------------------------------------- 11 CÂMERAS
def make_cam(name, loc, target=None, lens=28.0, rot=None):
    cd = bpy.data.cameras.new(name); cd.lens = lens; cd.sensor_width = SENSOR; cd.clip_start = 0.05; cd.clip_end = 8000
    ob = bpy.data.objects.new(name, cd); COLL["cam"].objects.link(ob); ob.location = Vector(loc)
    if rot is not None: ob.rotation_euler = rot
    else: ob.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    return ob

def build_cameras():
    main = make_cam("CAM_Principal", CAM_LOC, lens=LENS, rot=CAM_ROT)
    A, B, C, D, r, u, nrm, sc, scr = CENTRAL
    make_cam("CAM_Monitor_Central", sc + nrm * 0.78, target=sc, lens=LENS)
    make_cam("CAM_Aux_Esquerda", (-1.4, -0.8, 1.15), target=P(812, 600, 1.6), lens=24)
    make_cam("CAM_Aux_Direita", (1.4, -0.8, 1.15), target=P(812, 600, 1.6), lens=24)
    make_cam("CAM_Aux_Visao_Geral", (-0.8, -1.1, 1.55), target=(0.1, 1.4, 0.75), lens=22)
    scene.camera = main
    return main

# ----------------------------------------------------------------------------- render
def setup_render():
    s = scene; s.render.engine = "CYCLES"
    s.cycles.device = "CPU"; s.cycles.samples = SAMPLES
    s.cycles.use_denoising = True
    try: s.cycles.denoiser = "OPENIMAGEDENOISE"
    except Exception: pass
    s.cycles.max_bounces = 6; s.cycles.glossy_bounces = 4; s.cycles.transparent_max_bounces = 8
    s.render.resolution_x = int(RES_X * SCALE); s.render.resolution_y = int(RES_Y * SCALE); s.render.resolution_percentage = 100
    s.view_settings.view_transform = "AgX"
    try: s.view_settings.look = "AgX - Punchy"
    except Exception: pass
    s.view_settings.exposure = float(arg("--exposure", 0.3))
    s.render.image_settings.file_format = "PNG"

def render(camname, filename, scale=None, samples=None):
    scene.camera = bpy.data.objects[camname]
    if scale: scene.render.resolution_x = int(RES_X * scale); scene.render.resolution_y = int(RES_Y * scale)
    if samples: scene.cycles.samples = samples
    scene.render.filepath = os.path.join(OUT, filename)
    bpy.ops.render.render(write_still=True)

# ----------------------------------------------------------------------------- main
if __name__ == "__main__" or True:
    CENTRAL = None
    build_sky(); build_shell(); build_windows(); build_console(); build_decor()
    build_terrain(); build_earth(); build_cameras(); setup_render()
    blend = os.path.join(OUT, "cabine_clps.blend")
    bpy.ops.wm.save_as_mainfile(filepath=blend)
    print("BLEND salvo em", blend)
    if "--glb" in argv:
        bpy.ops.export_scene.gltf(filepath=os.path.join(OUT, "cabine_clps.glb"), export_format="GLB", export_apply=True)
    if DO_RENDER:
        render("CAM_Principal", "render_principal.png")
        if "--all" in argv:
            for cn, fn in (("CAM_Monitor_Central", "render_monitor_central.png"), ("CAM_Aux_Esquerda", "render_aux_esquerda.png"),
                           ("CAM_Aux_Direita", "render_aux_direita.png"), ("CAM_Aux_Visao_Geral", "render_aux_visao_geral.png")):
                render(cn, fn, scale=0.5, samples=48)
