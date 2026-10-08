import bpy
import bmesh
import math
from mathutils import Vector, Matrix

# ---------------------------------------------------------------------------
# 1. PULIZIA SCENA
# ---------------------------------------------------------------------------
bpy.ops.wm.read_factory_settings(use_empty=True)

scene = bpy.context.scene
scene.unit_settings.system = 'METRIC'
scene.unit_settings.scale_length = 1.0

# ---------------------------------------------------------------------------
# 2. MATERIALI PBR FOTOREALISTICI
# ---------------------------------------------------------------------------
def make_mat(name, base_color, roughness=0.5, metallic=0.0, emission=None, emission_strength=0.0, alpha=1.0):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    bsdf = next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*base_color, 1.0)
        bsdf.inputs["Roughness"].default_value = roughness
        bsdf.inputs["Metallic"].default_value = metallic
        if alpha < 1.0:
            if "Alpha" in bsdf.inputs:
                bsdf.inputs["Alpha"].default_value = alpha
        if emission and emission_strength > 0:
            if "Emission Color" in bsdf.inputs:
                bsdf.inputs["Emission Color"].default_value = (*emission, 1.0)
                bsdf.inputs["Emission Strength"].default_value = emission_strength
            elif "Emission" in bsdf.inputs:
                bsdf.inputs["Emission"].default_value = (*emission, 1.0)
    return mat

mat_platform      = make_mat("Platform_Dark",     (0.11, 0.15, 0.20), roughness=0.45, metallic=0.15)
mat_driveway      = make_mat("Driveway_Dark",     (0.07, 0.09, 0.13), roughness=0.65, metallic=0.05)
mat_wall_white    = make_mat("Wall_White",        (0.93, 0.95, 0.97), roughness=0.60, metallic=0.0)
mat_wall_band     = make_mat("Wall_GreyBand",     (0.46, 0.50, 0.55), roughness=0.55, metallic=0.05)
mat_cornice_grey  = make_mat("Cornice_Grey",      (0.55, 0.59, 0.64), roughness=0.50, metallic=0.08)
mat_plinth_grey   = make_mat("Plinth_Grey",       (0.76, 0.79, 0.83), roughness=0.65, metallic=0.0)
mat_railing_metal = make_mat("Railing_Metal",     (0.62, 0.66, 0.70), roughness=0.35, metallic=0.75)
mat_balcony_floor = make_mat("Balcony_Floor",     (0.82, 0.84, 0.87), roughness=0.55, metallic=0.0)
mat_shutter_white = make_mat("Shutter_White",     (0.90, 0.92, 0.94), roughness=0.45, metallic=0.05)
mat_window_glass  = make_mat("Window_Glass",      (0.12, 0.18, 0.26), roughness=0.10, metallic=0.2, emission=(0.95, 0.82, 0.55), emission_strength=0.18)
mat_garage_door   = make_mat("Garage_Door_Grey",  (0.40, 0.43, 0.47), roughness=0.45, metallic=0.45)
mat_roof_base     = make_mat("Roof_Terracotta",   (0.64, 0.30, 0.21), roughness=0.65, metallic=0.0)
mat_roof_tile_1   = make_mat("Roof_Tile_Warm",    (0.73, 0.37, 0.26), roughness=0.58, metallic=0.0)
mat_roof_tile_2   = make_mat("Roof_Tile_Dark",    (0.58, 0.27, 0.19), roughness=0.62, metallic=0.0)
mat_solar_cell    = make_mat("Solar_TotalBlack",  (0.03, 0.05, 0.09), roughness=0.12, metallic=0.65, emission=(0.02, 0.12, 0.30), emission_strength=0.15)
mat_solar_frame   = make_mat("Solar_BlackFrame",  (0.08, 0.10, 0.13), roughness=0.28, metallic=0.80)
mat_alu_rail      = make_mat("Alu_MountingRail",  (0.78, 0.81, 0.85), roughness=0.30, metallic=0.85)
mat_hw_white      = make_mat("Huawei_White",      (0.95, 0.96, 0.98), roughness=0.25, metallic=0.15)
mat_hw_dark       = make_mat("Huawei_Anthracite", (0.14, 0.16, 0.20), roughness=0.30, metallic=0.50)
mat_led_green     = make_mat("LED_Green",         (0.0, 0.92, 0.60),  roughness=0.15, emission=(0.0, 0.95, 0.62), emission_strength=2.2)
mat_led_cyan      = make_mat("LED_SOC_Cyan",      (0.0, 0.82, 1.0),   roughness=0.15, emission=(0.0, 0.85, 1.0),  emission_strength=1.8)
mat_pipe_grey     = make_mat("Conduit_Grey",      (0.36, 0.40, 0.45), roughness=0.40, metallic=0.60)
mat_pole_metal    = make_mat("Grid_Pole_Metal",   (0.45, 0.49, 0.54), roughness=0.45, metallic=0.70)

# ---------------------------------------------------------------------------
# HELPER FUNCTIONS PER GEOMETRIA PULITA
# ---------------------------------------------------------------------------
def add_box(name, size, location, mat, rotation=(0, 0, 0), bevel=0.0):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=location, rotation=rotation)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = (size[0], size[1], size[2])
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if bevel > 0:
        mod = obj.modifiers.new(name="Bevel", type='BEVEL')
        mod.width = bevel
        mod.segments = 2
        bpy.ops.object.modifier_apply(modifier=mod.name)
    if mat:
        obj.data.materials.append(mat)
    return obj

def add_cyl(name, radius, depth, location, mat, rotation=(0, 0, 0), vertices=16):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth, location=location, rotation=rotation)
    obj = bpy.context.active_object
    obj.name = name
    if mat:
        obj.data.materials.append(mat)
    return obj

# ---------------------------------------------------------------------------
# 3. PIATTAFORMA BASE DARK SLATE + RAMPA GARAGE (come nell'anteprima scelta)
# ---------------------------------------------------------------------------
# Dimensioni casa: X da -7.5 a +7.5 (L=15m), Y da -5.0 a +5.0 (W=10m)
# Facciata balconi: Y = -5.0 (fronte-sinistra nella vista isometrica)
# Facciata Inverter/Batteria/Garage: X = +7.5 (fronte-destra nella vista isometrica)

add_box("Base_Platform", (22.5, 16.5, 0.45), (0.5, 0.0, -0.225), mat_platform, bevel=0.06)
add_box("Base_Border_Rim", (22.7, 16.7, 0.12), (0.5, 0.0, -0.38), mat_wall_band, bevel=0.03)

# Area rampa garage sul lato destro (X > 6.5, Y da 0.4 a 4.0)
add_box("Garage_Driveway_Flat", (4.4, 4.2, 0.04), (9.4, 2.2, 0.01), mat_driveway)
# Muretto contenimento rampa
add_box("Ramp_Wall_Front", (3.6, 0.18, 0.55), (9.3, 0.15, 0.25), mat_wall_band)
add_box("Ramp_Wall_Back",  (3.6, 0.18, 0.55), (9.3, 4.25, 0.25), mat_wall_band)

# ---------------------------------------------------------------------------
# 4. CORPO PRINCIPALE DELLA CASA + FASCE MARCAPIANO GRIGIE
# ---------------------------------------------------------------------------
HOUSE_L = 15.0  # X: -7.5 .. +7.5
HOUSE_W = 10.0  # Y: -5.0 .. +5.0
HOUSE_H = 6.50  # Z: 0.0 .. 6.50

# Zoccolatura / Seminterrato (Z: 0.0 .. 0.75)
add_box("House_Wall_Plinth", (HOUSE_L, HOUSE_W, 0.75), (0.0, 0.0, 0.375), mat_plinth_grey)

# Corpo principale intonaco bianco (Z: 0.75 .. 6.50)
add_box("House_Wall_Main", (HOUSE_L, HOUSE_W, 5.75), (0.0, 0.0, 3.625), mat_wall_white)

# Fasce marcapiano orizzontali grigio-azzurre (come nella foto reale e anteprima)
add_box("House_Band_Low",  (HOUSE_L + 0.06, HOUSE_W + 0.06, 0.16), (0.0, 0.0, 0.75), mat_wall_band)
add_box("House_Band_Mid",  (HOUSE_L + 0.06, HOUSE_W + 0.06, 0.22), (0.0, 0.0, 3.62), mat_wall_band)
add_box("House_Band_High", (HOUSE_L + 0.06, HOUSE_W + 0.06, 0.36), (0.0, 0.0, 6.28), mat_wall_band)

# ---------------------------------------------------------------------------
# 5. CORNICIONE GRIGIO SPORGENTE CON VASCHE ANGOLARI A SBALZO
# ---------------------------------------------------------------------------
# Cornicione perimetrale Z: 6.46 .. 7.02
CORN_Z = 6.74
CORN_H = 0.56
# Lato Frontale (Y = -5.45)
add_box("Cornice_Front", (16.4, 0.90, CORN_H), (0.0, -5.05, CORN_Z), mat_cornice_grey, bevel=0.02)
# Lato Posteriore (Y = +5.45)
add_box("Cornice_Back",  (16.4, 0.90, CORN_H), (0.0,  5.05, CORN_Z), mat_cornice_grey, bevel=0.02)
# Lato Destro (X = +7.95)
add_box("Cornice_Right", (0.90, 10.9, CORN_H), (7.55, 0.0,  CORN_Z), mat_cornice_grey, bevel=0.02)
# Lato Sinistro (X = -7.95)
add_box("Cornice_Left",  (0.90, 10.9, CORN_H), (-7.55, 0.0, CORN_Z), mat_cornice_grey, bevel=0.02)

# Vasca/Terrazzino angolare a sbalzo in alto a sinistra (X = -8.3, Y = -4.2) e a destra (X = +8.3, Y = +4.2)
def build_corner_box(prefix, cx, cy):
    add_box(f"{prefix}_Floor", (1.6, 2.2, 0.14), (cx, cy, 6.52), mat_cornice_grey)
    add_box(f"{prefix}_OuterX", (0.16, 2.2, 0.56), (cx + (0.72 if cx > 0 else -0.72), cy, 6.74), mat_cornice_grey)
    add_box(f"{prefix}_OuterY", (1.6, 0.16, 0.56), (cx, cy + (1.02 if cy > 0 else -1.02), 6.74), mat_cornice_grey)
    add_box(f"{prefix}_InnerY", (1.6, 0.16, 0.56), (cx, cy + (-1.02 if cy > 0 else 1.02), 6.74), mat_cornice_grey)

build_corner_box("CornerBox_Left",  -8.15, -4.0)
build_corner_box("CornerBox_Right",  8.15,  4.0)

# Pluviale verticale (tubo grondaia) sullo spigolo anteriore destro (X=7.52, Y=-5.02)
add_cyl("Rain_Downpipe", 0.055, 6.55, (7.48, -5.02, 3.28), mat_pipe_grey)

# ---------------------------------------------------------------------------
# 6. DOPPIO BALCONE CONTINUO SULLA FACCIATA PRINCIPALE (Y = -5.0 .. -6.35)
# ---------------------------------------------------------------------------
BALC_Y = -5.68
BALC_DEPTH = 1.36
BALC_LEN = 15.2

for floor_idx, z_floor in enumerate([0.78, 3.64], start=1):
    # Soletta balcone
    add_box(f"Balcony_Slab_F{floor_idx}", (BALC_LEN, BALC_DEPTH, 0.18), (0.0, BALC_Y, z_floor), mat_balcony_floor, bevel=0.02)
    add_box(f"Balcony_Fascia_F{floor_idx}", (BALC_LEN + 0.04, 0.08, 0.22), (0.0, BALC_Y - BALC_DEPTH/2, z_floor - 0.02), mat_cornice_grey)

    # Ringhiera metallica (altezza 0.95m)
    rail_z_top = z_floor + 0.98
    rail_z_mid = z_floor + 0.52
    rail_z_bot = z_floor + 0.14
    front_y = BALC_Y - BALC_DEPTH/2 + 0.06

    # Corrimano superiore e inferiore frontale
    add_box(f"Rail_Top_F{floor_idx}", (BALC_LEN, 0.05, 0.05), (0.0, front_y, rail_z_top), mat_railing_metal)
    add_box(f"Rail_Bot_F{floor_idx}", (BALC_LEN, 0.04, 0.04), (0.0, front_y, rail_z_bot), mat_railing_metal)

    # Corrimano laterali (sinistro e destro)
    for side_name, sx in [("L", -BALC_LEN/2 + 0.04), ("R", BALC_LEN/2 - 0.04)]:
        add_box(f"Rail_SideTop_{side_name}_F{floor_idx}", (0.05, BALC_DEPTH, 0.05), (sx, BALC_Y, rail_z_top), mat_railing_metal)
        add_box(f"Rail_SideBot_{side_name}_F{floor_idx}", (0.04, BALC_DEPTH, 0.04), (sx, BALC_Y, rail_z_bot), mat_railing_metal)
        # Bacchette verticali sui lati
        for sy_i in range(6):
            sy = BALC_Y - BALC_DEPTH/2 + 0.12 + sy_i * 0.22
            add_cyl(f"Baluster_Side_{side_name}_{sy_i}_F{floor_idx}", 0.012, 0.84, (sx, sy, rail_z_mid), mat_railing_metal, vertices=8)

    # Montanti principali e bacchette verticali frontali
    num_balusters = 68
    for bi in range(num_balusters + 1):
        bx = -BALC_LEN/2 + 0.06 + bi * ((BALC_LEN - 0.12) / num_balusters)
        is_post = (bi % 8 == 0)
        r_rad = 0.022 if is_post else 0.011
        add_cyl(f"Baluster_F{floor_idx}_{bi}", r_rad, 0.86, (bx, front_y, rail_z_mid), mat_railing_metal, vertices=8)

    # 4 Pannelli grigi sulla ringhiera del 1° piano (come nell'anteprima scelta!)
    if floor_idx == 1:
        for pi, px in enumerate([-5.3, -1.75, 1.75, 5.3]):
            add_box(f"Balcony_Panel_{pi}", (0.95, 0.03, 0.72), (px, front_y + 0.01, rail_z_mid), mat_wall_band)

# ---------------------------------------------------------------------------
# 7. PORTE-FINESTRE CON PERSIANE BIANCHE SULLA FACCIATA BALCONI (4 per piano)
# ---------------------------------------------------------------------------
def add_shuttered_french_door(prefix, x_pos, z_base):
    door_w = 1.15
    door_h = 2.15
    z_center = z_base + door_h / 2.0
    y_wall = -5.01

    # Vetro scuro illuminato + telaio bianco
    add_box(f"Window_Glass_{prefix}", (door_w, 0.06, door_h), (x_pos, y_wall, z_center), mat_window_glass)
    add_box(f"Door_Frame_{prefix}",   (door_w + 0.14, 0.08, door_h + 0.10), (x_pos, y_wall + 0.02, z_center), mat_shutter_white)
    add_box(f"Door_Mullion_{prefix}", (0.05, 0.09, door_h), (x_pos, y_wall - 0.01, z_center), mat_shutter_white)

    # Persiane bianche a battente (leggermente socchiuse come nell'anteprima)
    shutter_w = 0.56
    for s_idx, (sx_off, rot_z) in enumerate([(-door_w/2 - 0.22, 0.28), (door_w/2 + 0.22, -0.28)]):
        sh = add_box(f"Shutter_{prefix}_{s_idx}", (shutter_w, 0.05, door_h), (x_pos + sx_off, y_wall - 0.06, z_center), mat_shutter_white, rotation=(0, 0, rot_z))

for f_idx, z_b in enumerate([0.88, 3.74], start=1):
    for d_idx, dx in enumerate([-5.3, -1.75, 1.75, 5.3]):
        add_shuttered_french_door(f"F{f_idx}_D{d_idx}", dx, z_b)

# Finestrelle seminterrato sotto il primo balcone
for vx in [-5.3, -1.75, 1.75, 5.3]:
    add_box(f"Basement_Vent_{vx}", (0.85, 0.08, 0.28), (vx, -5.01, 0.32), mat_hw_dark)

# ---------------------------------------------------------------------------
# 8. PARETE LATERALE DESTRA (X = +7.5): GARAGE, FINESTRE, BALCONCINO + HUAWEI
# ---------------------------------------------------------------------------
# 8a. Portone Garage Grigio a doghe orizzontali (Y da +0.6 a +3.6, Z da 0.05 a 2.35)
GAR_Y = 2.15
GAR_W = 2.85
GAR_H = 2.30
add_box("Garage_Frame", (0.18, GAR_W + 0.26, GAR_H + 0.16), (7.48, GAR_Y, GAR_H/2 + 0.05), mat_plinth_grey)
add_box("Garage_Door_Main", (0.10, GAR_W, GAR_H), (7.44, GAR_Y, GAR_H/2 + 0.05), mat_garage_door)
# Doghe orizzontali del garage + maniglia
for si in range(10):
    sz = 0.22 + si * 0.22
    add_box(f"Garage_Slat_{si}", (0.12, GAR_W - 0.06, 0.025), (7.46, GAR_Y, sz), mat_hw_dark)
add_box("Garage_Handle", (0.15, 0.18, 0.05), (7.50, GAR_Y, 0.95), mat_hw_dark)

# 8b. Finestra 1° Piano sopra il Garage (Y = 2.15, Z = 3.15) con persiane bianche
WIN1_Z = 3.15
add_box("Window_Glass_Side1", (0.08, 1.35, 1.15), (7.51, 2.15, WIN1_Z), mat_window_glass)
add_box("Side_Win1_Frame",    (0.10, 1.48, 1.26), (7.49, 2.15, WIN1_Z), mat_shutter_white)
add_box("Side_Win1_ShutL1",   (0.06, 0.48, 1.18), (7.54, 1.15, WIN1_Z), mat_shutter_white)
add_box("Side_Win1_ShutL2",   (0.06, 0.48, 1.18), (7.54, 0.62, WIN1_Z), mat_shutter_white)
add_box("Side_Win1_ShutR",    (0.06, 0.48, 1.18), (7.54, 3.12, WIN1_Z), mat_shutter_white)

# 8c. Finestra cieca/persiana 2° Piano (Y = 1.35, Z = 5.10)
add_box("Side_Win2_Shutter",  (0.07, 0.58, 1.15), (7.52, 1.35, 5.10), mat_shutter_white)

# 8d. Balconcino angolare in alto a destra (X = 7.5..8.5, Y = 3.4..4.95, Z = 4.55)
add_box("Side_MiniBalcony_Slab", (1.25, 1.75, 0.16), (8.05, 4.15, 4.55), mat_balcony_floor, bevel=0.02)
add_box("Side_MiniBalcony_RailF", (0.04, 1.75, 0.04), (8.62, 4.15, 5.42), mat_railing_metal)
add_box("Side_MiniBalcony_RailS", (1.20, 0.04, 0.04), (8.05, 3.30, 5.42), mat_railing_metal)
for mbi in range(8):
    mby = 3.35 + mbi * 0.22
    add_cyl(f"MiniBalc_Bal_{mbi}", 0.011, 0.85, (8.62, mby, 5.00), mat_railing_metal, vertices=8)

# ---------------------------------------------------------------------------
# 9. APPARATI ENERGETICI HUAWEI SULLA PARETE DESTRA (X = +7.5, Y da -4.1 a -1.4)
#    (Esattamente come nell'immagine scelta: Wallbox a sinistra, Inverter al centro,
#     Batteria LUNA2000 a destra, con le canaline di collegamento!)
# ---------------------------------------------------------------------------
# 9a. Wallbox Smart (X = 7.58, Y = -4.05, Z = 1.50)
add_box("Wallbox_Body", (0.22, 0.42, 0.56), (7.58, -4.05, 1.50), mat_hw_white, bevel=0.04)
add_box("Wallbox_FrontFace", (0.06, 0.30, 0.42), (7.68, -4.05, 1.50), mat_hw_dark, bevel=0.02)
add_cyl("Wallbox_LED", 0.09, 0.04, (7.71, -4.05, 1.52), mat_led_green, rotation=(0, math.pi/2, 0), vertices=24)

# 9b. Inverter Huawei SUN2000 (X = 7.60, Y = -3.00, Z = 1.60)
add_box("Inverter_SUN2000", (0.26, 0.68, 0.78), (7.60, -3.00, 1.60), mat_hw_white, bevel=0.04)
add_box("Inverter_Heatsink", (0.20, 0.64, 0.72), (7.54, -3.00, 1.60), mat_hw_dark)
add_box("Inverter_BottomBay", (0.22, 0.52, 0.14), (7.60, -3.00, 1.16), mat_hw_dark)
add_box("Inverter_LED", (0.04, 0.16, 0.03), (7.73, -3.00, 1.75), mat_led_green)

# 9c. Batteria d'accumulo Huawei LUNA2000 (X = 7.62, Y = -1.75, Z = 1.80)
# Modulo batteria bianco inferiore + modulo di potenza antracite superiore
add_box("Battery_LUNA2000", (0.30, 0.76, 1.05), (7.62, -1.75, 1.68), mat_hw_white, bevel=0.03)
add_box("Battery_TopModule", (0.31, 0.76, 0.28), (7.62, -1.75, 2.34), mat_hw_dark, bevel=0.03)
# 5 Segmenti LED SOC (Battery_SOC_0 .. Battery_SOC_4)
for soc_i in range(5):
    sy = -1.95 + soc_i * 0.10
    add_box(f"Battery_SOC_{soc_i}", (0.04, 0.07, 0.035), (7.77, sy, 2.30), mat_led_cyan)

# 9d. Canaline elettriche (Conduit) tra Tetto, Inverter, Batteria e Wallbox
# Discesa dal tetto lungo lo spigolo fino all'inverter
add_cyl("Conduit_PV_Drop", 0.025, 5.2, (7.53, -4.65, 3.85), mat_pipe_grey)
add_box("Conduit_PV_Horiz", (0.04, 1.65, 0.04), (7.53, -3.82, 1.25), mat_pipe_grey)
# Collegamento Wallbox <-> Inverter <-> Batteria
add_box("Conduit_WB_Inv",  (0.04, 1.05, 0.04), (7.54, -3.52, 1.05), mat_pipe_grey)
add_box("Conduit_Inv_Bat", (0.04, 1.25, 0.04), (7.54, -2.38, 1.05), mat_pipe_grey)
add_box("Conduit_WB_Up",   (0.04, 0.04, 0.35), (7.54, -4.05, 1.18), mat_pipe_grey)
add_box("Conduit_Inv_Up",  (0.04, 0.04, 0.20), (7.54, -3.00, 1.12), mat_pipe_grey)
add_box("Conduit_Bat_Up",  (0.04, 0.04, 0.20), (7.54, -1.75, 1.12), mat_pipe_grey)

# 9e. Scatola di derivazione / Contatore Rete Elettrica Enel sulla parete destra in alto (come nell'anteprima!)
add_box("Grid_Box", (0.16, 0.34, 0.46), (7.55, 3.05, 5.15), mat_cornice_grey, bevel=0.02)
add_cyl("Grid_Conduit", 0.022, 1.35, (7.53, 3.05, 4.30), mat_pipe_grey)

# ---------------------------------------------------------------------------
# 10. RETRO E LATO SINISTRO (per completezza a 360° quando si ruota il modello)
# ---------------------------------------------------------------------------
# Pensilina semitonda sopra ingresso laterale sinistro (X = -7.5, Y = -1.5, Z = 2.4)
add_cyl("Side_Entrance_Canopy", 1.15, 0.14, (-7.65, -1.5, 2.45), mat_cornice_grey, vertices=24)
add_box("Window_Glass_Left1", (0.08, 1.10, 2.10), (-7.51, -1.5, 1.15), mat_window_glass)
add_box("Window_Glass_Left2", (0.08, 1.20, 1.25), (-7.51, -1.5, 4.55), mat_window_glass)

# Corpo sporgente al piano terra sul retro (Y = +5.0..+6.6, X = -1.5..+1.5)
add_box("Rear_Extension_Body", (2.8, 1.6, 2.6), (0.0, 5.75, 1.30), mat_wall_white)
add_box("Rear_Extension_Roof", (3.0, 1.85, 0.16), (0.0, 5.80, 2.72), mat_roof_tile_1, rotation=(0.32, 0, 0))

# ---------------------------------------------------------------------------
# 11. TETTO A PADIGLIONE (4 FALDE) IN COPPI ROSSI + PANNELLI SOLARI REALI
# ---------------------------------------------------------------------------
# Costruiamo la piramide a padiglione (hipped roof) con bmesh
# Base del tetto: X in [-7.65, +7.65], Y in [-5.15, +5.15], Z_base = 6.95
# Colmo centrale (ridge): X in [-3.10, +3.10], Y = 0.0, Z_top = 9.75
EAVE_X = 7.65
EAVE_Y = 5.15
RIDGE_X = 3.10
Z_EAVE = 6.96
Z_RIDGE = 9.76

roof_mesh = bpy.data.meshes.new("Hipped_Roof_Mesh")
roof_obj = bpy.data.objects.new("Hipped_Roof", roof_mesh)
bpy.context.collection.objects.link(roof_obj)

bm = bmesh.new()
v_fl = bm.verts.new((-EAVE_X, -EAVE_Y, Z_EAVE))
v_fr = bm.verts.new(( EAVE_X, -EAVE_Y, Z_EAVE))
v_br = bm.verts.new(( EAVE_X,  EAVE_Y, Z_EAVE))
v_bl = bm.verts.new((-EAVE_X,  EAVE_Y, Z_EAVE))
v_rl = bm.verts.new((-RIDGE_X, 0.0,    Z_RIDGE))
v_rr = bm.verts.new(( RIDGE_X, 0.0,    Z_RIDGE))

bm.faces.new((v_fl, v_fr, v_rr, v_rl)) # Falda principale frontale (Y < 0)
bm.faces.new((v_fr, v_br, v_rr))       # Falda triangolare destra (X > 0)
bm.faces.new((v_br, v_bl, v_rl, v_rr)) # Falda posteriore (Y > 0)
bm.faces.new((v_bl, v_fl, v_rl))       # Falda triangolare sinistra (X < 0)
bm.faces.new((v_bl, v_br, v_fr, v_fl)) # Fondo

bm.to_mesh(roof_mesh)
bm.free()
roof_obj.data.materials.append(mat_roof_base)

# Colmi in coppi (ridge & hip caps) lungo i 5 spigoli del tetto per realismo 3D
def add_ridge_beam(name, p1, p2, radius=0.11):
    v1 = Vector(p1)
    v2 = Vector(p2)
    diff = v2 - v1
    length = diff.length
    mid = (v1 + v2) * 0.5
    rot = diff.to_track_quat('Z', 'Y').to_euler()
    add_cyl(name, radius, length, mid, mat_roof_tile_1, rotation=rot, vertices=12)

add_ridge_beam("Roof_Ridge_Top", (-RIDGE_X, 0.0, Z_RIDGE+0.04), (RIDGE_X, 0.0, Z_RIDGE+0.04), 0.12)
add_ridge_beam("Roof_Hip_FL",    (-EAVE_X, -EAVE_Y, Z_EAVE+0.04), (-RIDGE_X, 0.0, Z_RIDGE+0.04), 0.11)
add_ridge_beam("Roof_Hip_FR",    ( EAVE_X, -EAVE_Y, Z_EAVE+0.04), ( RIDGE_X, 0.0, Z_RIDGE+0.04), 0.11)
add_ridge_beam("Roof_Hip_BR",    ( EAVE_X,  EAVE_Y, Z_EAVE+0.04), ( RIDGE_X, 0.0, Z_RIDGE+0.04), 0.11)
add_ridge_beam("Roof_Hip_BL",    (-EAVE_X,  EAVE_Y, Z_EAVE+0.04), (-RIDGE_X, 0.0, Z_RIDGE+0.04), 0.11)

# File di coppi 3D (cordoli orizzontali/verticali) sulle falde per dare la texture reale delle tegole
num_tile_courses = 16
for ci in range(num_tile_courses):
    t = (ci + 0.5) / num_tile_courses
    z_c = Z_EAVE + t * (Z_RIDGE - Z_EAVE) + 0.02
    half_x = EAVE_X - t * (EAVE_X - RIDGE_X)
    half_y = EAVE_Y * (1.0 - t)
    mat_t = mat_roof_tile_1 if (ci % 2 == 0) else mat_roof_tile_2
    # Corso falda frontale e posteriore
    add_box(f"TileRow_Front_{ci}", (half_x * 1.98, 0.12, 0.06), (0.0, -half_y, z_c), mat_t)
    add_box(f"TileRow_Back_{ci}",  (half_x * 1.98, 0.12, 0.06), (0.0,  half_y, z_c), mat_t)
    # Corso falda destra e sinistra
    add_box(f"TileRow_Right_{ci}", (0.12, half_y * 1.96, 0.06), ( half_x, 0.0, z_c), mat_t)
    add_box(f"TileRow_Left_{ci}",  (0.12, half_y * 1.96, 0.06), (-half_x, 0.0, z_c), mat_t)

# ---------------------------------------------------------------------------
# 12. PANNELLI FOTOVOLTAICI TOTAL BLACK (Disposizione esatta dell'anteprima!)
# ---------------------------------------------------------------------------
# Falda Frontale (Y < 0): inclinazione atan2(Z_RIDGE - Z_EAVE, EAVE_Y) = atan2(2.80, 5.15)
front_slope_angle = math.atan2(Z_RIDGE - Z_EAVE, EAVE_Y) # ~28.5 gradi

panel_idx = 0
def add_solar_panel_on_front_slope(x_center, t_height, p_width=1.08, p_len=1.02):
    global panel_idx
    panel_idx += 1
    y_pos = -EAVE_Y * (1.0 - t_height)
    z_pos = Z_EAVE + t_height * (Z_RIDGE - Z_EAVE) + 0.13
    rot = (front_slope_angle, 0.0, 0.0)
    # Cornice nera
    add_box(f"Solar_Frame_{panel_idx}", (p_width, p_len, 0.045), (x_center, y_pos, z_pos), mat_solar_frame, rotation=rot)
    # Cella fotovoltaica Total Black (chiamata Solar_Panel_* per l'animazione emissiva in Three.js!)
    add_box(f"Solar_Panel_{panel_idx}", (p_width - 0.05, p_len - 0.05, 0.052), (x_center, y_pos, z_pos + 0.005), mat_solar_cell, rotation=rot)

# 4 File scalate sulla falda principale frontale + binari in alluminio sporgenti a destra (come nella foto!)
front_rows = [
    # (t_height, num_panels, x_start_offset)
    (0.18, 7, -4.0),  # Fila 1 (bassa): 7 pannelli
    (0.40, 7, -3.5),  # Fila 2 (medio-bassa): 7 pannelli
    (0.62, 6, -2.9),  # Fila 3 (medio-alta): 6 pannelli
    (0.83, 5, -2.3),  # Fila 4 (alta): 5 pannelli
]

for r_i, (t_h, n_pan, x_start) in enumerate(front_rows):
    y_rail = -EAVE_Y * (1.0 - t_h)
    z_rail = Z_EAVE + t_h * (Z_RIDGE - Z_EAVE) + 0.08
    rail_len = n_pan * 1.12 + 0.75
    rail_cx = x_start + (n_pan - 1) * 1.12 * 0.5 + 0.18
    # Doppio binario in alluminio sotto ogni fila (sporge leggermente a destra come nell'anteprima!)
    add_box(f"Alu_Rail_F_{r_i}_A", (rail_len, 0.05, 0.04), (rail_cx, y_rail - 0.25, z_rail - 0.12), mat_alu_rail)
    add_box(f"Alu_Rail_F_{r_i}_B", (rail_len, 0.05, 0.04), (rail_cx, y_rail + 0.25, z_rail + 0.12), mat_alu_rail)
    for p_i in range(n_pan):
        px = x_start + p_i * 1.12
        add_solar_panel_on_front_slope(px, t_h, p_width=1.09, p_len=1.00)

# Falda Triangolare Destra (X > 0): inclinazione atan2(Z_RIDGE - Z_EAVE, EAVE_X - RIDGE_X) = atan2(2.80, 4.55)
right_slope_angle = math.atan2(Z_RIDGE - Z_EAVE, EAVE_X - RIDGE_X) # ~31.6 gradi

def add_solar_panel_on_right_slope(y_center, t_height, p_width=1.05, p_len=1.05):
    global panel_idx
    panel_idx += 1
    x_pos = EAVE_X - t_height * (EAVE_X - RIDGE_X)
    z_pos = Z_EAVE + t_height * (Z_RIDGE - Z_EAVE) + 0.13
    rot = (0.0, right_slope_angle, 0.0)
    add_box(f"Solar_Frame_{panel_idx}", (p_len, p_width, 0.045), (x_pos, y_center, z_pos), mat_solar_frame, rotation=rot)
    add_box(f"Solar_Panel_{panel_idx}", (p_len - 0.05, p_width - 0.05, 0.052), (x_pos, y_center, z_pos + 0.005), mat_solar_cell, rotation=rot)

# 3 File scalate sulla falda triangolare destra (come nell'anteprima scelta: 4 sotto, 3 in mezzo, 2 sopra)
right_rows = [
    (0.18, [-1.65, -0.55, 0.55, 1.65]),
    (0.41, [-1.45, -0.35, 0.75]),
    (0.64, [-1.20, -0.10]),
]

for r_i, (t_h, y_list) in enumerate(right_rows):
    for py in y_list:
        add_solar_panel_on_right_slope(py, t_h, p_width=1.06, p_len=1.02)

# Comignolo e lucernario sul retro del tetto
add_box("Roof_Chimney", (0.55, 0.55, 1.15), (-2.5, 2.8, 8.85), mat_plinth_grey)
add_box("Roof_Chimney_Cap", (0.70, 0.70, 0.10), (-2.5, 2.8, 9.45), mat_cornice_grey)

# ---------------------------------------------------------------------------
# 13. SALVATAGGIO .BLEND ED ESPORTAZIONE .GLB
# ---------------------------------------------------------------------------
import os
base_dir = os.path.dirname(os.path.abspath(__file__))
blend_path = os.path.join(base_dir, "Villa_Solare_FusionSolar.blend")
glb_path = os.path.join(base_dir, "static", "models", "villa_solare.glb")

bpy.ops.wm.save_as_mainfile(filepath=blend_path)
bpy.ops.export_scene.gltf(
    filepath=glb_path,
    export_format='GLB',
    use_selection=False,
    export_apply=True
)
print(f"EXPORT_SUCCESS: {glb_path} ({os.path.getsize(glb_path)} bytes)")
