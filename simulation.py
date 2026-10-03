from ursina import *
from ursina.models.procedural.cylinder import Cylinder
import random

app = Ursina()

window.title = "Advanced Nuclear Fuel Reprocessing & Dissolution Simulator"
window.color = color.black
editor_camera = EditorCamera()
editor_camera.position = (4, 9, -26)
editor_camera.rotation_x = 18

# ---------------------------------------------------------------------------
# Етапи на цикъла на рециклиране
# ---------------------------------------------------------------------------
STAGE_IDLE = 0
STAGE_COOLING = 1
STAGE_DISSOLUTION = 2
STAGE_REPACKAGING = 3
STAGE_WASTE = 4
STAGE_COMPLETE = 5

STAGE_NAMES = {
    STAGE_IDLE: "STANDBY",
    STAGE_COOLING: "ЕТАП 1/4 — COOLING POOL (отвеждане на остатъчна топлина)",
    STAGE_DISSOLUTION: "ЕТАП 2/4 — DISSOLUTION (химическо разтваряне)",
    STAGE_REPACKAGING: "ЕТАП 3/4 — REPACKAGING (формиране на ново MOX гориво)",
    STAGE_WASTE: "ЕТАП 4/4 — WASTE CONDITIONING (остъкляване на отпадъка)",
    STAGE_COMPLETE: "ЦИКЪЛЪТ Е ЗАВЪРШЕН — Горивото е рециклирано",
}

TEMP_LABELS = {
    STAGE_COOLING: "Остатъчна топлина",
    STAGE_DISSOLUTION: "Температура на разтвора",
    STAGE_REPACKAGING: "Температура на синтероване",
    STAGE_WASTE: "Температура на остъкляване",
}

# x-позиции на отделните станции по протежение на горещата клетка
STATION_X = {
    STAGE_COOLING: -14,
    STAGE_DISSOLUTION: 0,
    STAGE_REPACKAGING: 14,
    STAGE_WASTE: 28,
}

stage = STAGE_IDLE
progress = 0.0            # прогрес (0-100) в рамките на текущия етап
reaction_speed = 1.0       # скорост на процеса, управлявана от UP/DOWN
overall_efficiency = 0.0

# ---------------------------------------------------------------------------
# Защитена горещата клетка, обхващаща всички станции
# ---------------------------------------------------------------------------
hot_cell = Entity(
    model='cube', color=color.rgb(20, 30, 40),
    scale=(50, 8, 8), position=(7, 0, 0),
    transparency=True, alpha=0.12,
)

# 1. Cooling pool
cooling_pool = Entity(
    model='cube', color=color.rgb(0, 120, 220),
    scale=(5, 2, 5), position=(STATION_X[STAGE_COOLING], -2, 0),
    transparency=True, alpha=0.5,
)

# 2. Dissolver tank
tank = Entity(
    model=Cylinder(), color=color.rgb(0, 180, 100),
    scale=(3, 5, 3), position=(STATION_X[STAGE_DISSOLUTION], -1, 0),
    transparency=True, alpha=0.4,
)

# 3. Repackaging mould (нова MOX кладинг тръба)
mould = Entity(
    model=Cylinder(), color=color.rgb(140, 140, 150),
    scale=(1.6, 4, 1.6), position=(STATION_X[STAGE_REPACKAGING], -1, 0),
    transparency=True, alpha=0.35,
)

# 4. Waste cask + капак
waste_cask = Entity(
    model='cube', color=color.rgb(90, 90, 20),
    scale=(3.5, 3, 3.5), position=(STATION_X[STAGE_WASTE], -1.8, 0),
)
waste_lid = Entity(
    model='cube', color=color.rgb(130, 130, 40),
    scale=(3.7, 0.4, 3.7), position=(STATION_X[STAGE_WASTE], 0.2, 0),
)

# Роботизирана ръка (следва активната станция)
robot_base = Entity(model='cube', color=color.gray, scale=(1, 0.5, 1), position=(STATION_X[STAGE_COOLING], 3.5, 0))
robot_arm = Entity(model='cube', color=color.light_gray, scale=(0.3, 3, 0.3), position=(STATION_X[STAGE_COOLING], 2, 0))

# Основен продукт: отработеното гориво, което преминава през всички станции
product = Entity(model='sphere', color=color.orange, scale=1.2, position=(STATION_X[STAGE_COOLING], 0.5, 0))

# Остатъчен отпадък, който се отделя след разтварянето
waste_chunk = Entity(model='sphere', color=color.rgb(80, 120, 40), scale=0.6,
                      position=(STATION_X[STAGE_DISSOLUTION], -3, 0), enabled=False)

# ---------------------------------------------------------------------------
# Система от частици (преизползва се на всяка станция с различен цвят)
# ---------------------------------------------------------------------------
num_particles = 60
particles = []
for _ in range(num_particles):
    p = Entity(model='sphere', color=color.rgb(100, 100, 100), scale=0.2, enabled=False)
    p.velocity = Vec3(0, 0, 0)
    particles.append(p)

def scatter_particles(center_x, col):
    for p in particles:
        p.position = (
            center_x + random.uniform(-1.3, 1.3),
            random.uniform(-3, 1),
            random.uniform(-1.3, 1.3),
        )
        p.velocity = Vec3(random.uniform(-0.02, 0.02), random.uniform(0.01, 0.05), random.uniform(-0.02, 0.02))
        p.color = col
        p.enabled = True

# ---------------------------------------------------------------------------
# UI Панел
# ---------------------------------------------------------------------------
panel_bg = Entity(model='quad', color=color.rgba(0, 0, 0, 150), scale=(0.9, 0.45), position=(-0.45, 0.32), parent=camera.ui)
title_text = Text(text=STAGE_NAMES[STAGE_IDLE], position=(-0.85, 0.45), scale=0.8, color=color.yellow)
temp_text = Text(text="", position=(-0.85, 0.40), scale=0.8, color=color.cyan)
rate_text = Text(text=f"Скорост на процеса: {reaction_speed:.2f}x", position=(-0.85, 0.35), scale=0.8, color=color.cyan)
progress_text = Text(text="Прогрес на етапа: 0%", position=(-0.85, 0.30), scale=0.8, color=color.azure)
efficiency_text = Text(text="Енергийна ефективност (MOX): 0%", position=(-0.85, 0.25), scale=0.8, color=color.green)

Text(
    text="Натисни [ SPACE ] за стартиране на цикъла\n"
         "Натисни [ UP / DOWN ] за ускоряване / забавяне на процеса\n"
         "Натисни [ R ] за нулиране на симулацията",
    position=(-0.85, -0.42), scale=0.7, color=color.white,
)

# ---------------------------------------------------------------------------
# Логика за преминаване между етапи
# ---------------------------------------------------------------------------
def enter_stage(new_stage):
    global stage, progress
    stage = new_stage
    progress = 0.0
    title_text.text = STAGE_NAMES[stage]

    if stage in STATION_X:
        x = STATION_X[stage]
        robot_base.animate_position((x, 3.5, 0), duration=1.2, curve=curve.in_out_sine)
        robot_arm.animate_position((x, 2, 0), duration=1.2, curve=curve.in_out_sine)

    if stage == STAGE_COOLING:
        title_text.color = color.orange
        product.position = (STATION_X[STAGE_COOLING], 1.5, 0)
        product.scale = 1.2
        product.color = color.red
        product.animate_position((STATION_X[STAGE_COOLING], -1, 0), duration=1.5, curve=curve.in_out_sine)
        scatter_particles(STATION_X[STAGE_COOLING], color.rgb(150, 220, 255))

    elif stage == STAGE_DISSOLUTION:
        title_text.color = color.green
        product.animate_position((STATION_X[STAGE_DISSOLUTION], 0.5, 0), duration=1.5, curve=curve.in_out_sine)
        scatter_particles(STATION_X[STAGE_DISSOLUTION], color.rgb(random.randint(180, 255), random.randint(80, 150), 0))

    elif stage == STAGE_REPACKAGING:
        title_text.color = color.azure
        # Отделя се остатъчният отпадък към следващата станция
        waste_chunk.enabled = True
        waste_chunk.position = (STATION_X[STAGE_DISSOLUTION], -0.5, 0)
        waste_chunk.animate_position((STATION_X[STAGE_WASTE], -0.5, 0), duration=3.0, curve=curve.in_out_sine)

        product.scale = 0.2
        product.color = color.rgb(120, 200, 255)
        product.animate_position((STATION_X[STAGE_REPACKAGING], -1, 0), duration=1.5, curve=curve.in_out_sine)
        scatter_particles(STATION_X[STAGE_REPACKAGING], color.rgb(180, 220, 255))

    elif stage == STAGE_WASTE:
        title_text.color = color.rgb(200, 200, 0)
        scatter_particles(STATION_X[STAGE_WASTE], color.rgb(120, 200, 80))

    elif stage == STAGE_COMPLETE:
        title_text.color = color.lime
        for p in particles:
            p.enabled = False
        waste_lid.animate_position((STATION_X[STAGE_WASTE], 1.0, 0), duration=1.0, curve=curve.in_out_sine)


def update():
    global progress, overall_efficiency

    if stage in (STAGE_IDLE, STAGE_COMPLETE):
        return

    progress = min(100.0, progress + reaction_speed * time.dt * 6)

    # Движение на частиците (йони / мехурчета / искри в зависимост от етапа)
    for p in particles:
        p.y += p.velocity.y * reaction_speed
        p.x += p.velocity.x * reaction_speed
        p.z += p.velocity.z * reaction_speed
        if p.y > 1.5:
            p.y = -2.5
            cx = STATION_X.get(stage, 0)
            p.x = cx + random.uniform(-1.3, 1.3)
            p.z = random.uniform(-1.3, 1.3)

    # Визуални ефекти, специфични за етапа
    if stage == STAGE_COOLING:
        temperature = lerp(300, 25, progress / 100)
        product.color = lerp(color.red, color.gray, progress / 100)

    elif stage == STAGE_DISSOLUTION:
        temperature = lerp(25, 95, progress / 100)
        if product.scale_x > 0.2:
            product.scale -= Vec3(0.0015, 0.0015, 0.0015) * reaction_speed
        tank.color = color.rgb(min(255, int(80 + progress * 1.5)), max(0, int(180 - progress)), 50)

    elif stage == STAGE_REPACKAGING:
        temperature = lerp(400, 800, progress / 100)
        product.scale = lerp(0.2, 1.3, progress / 100)
        mould.color = color.rgb(140, 140, int(150 + progress))

    elif stage == STAGE_WASTE:
        temperature = lerp(200, 1150, progress / 100)
        waste_chunk.color = lerp(color.rgb(80, 120, 40), color.rgb(40, 200, 90), progress / 100)
        waste_cask.color = color.rgb(90, 90, int(20 + progress * 0.8))

    temp_text.text = f"{TEMP_LABELS[stage]}: {temperature:.0f} °C"
    progress_text.text = f"Прогрес на етапа: {int(progress)}%"
    rate_text.text = f"Скорост на процеса: {reaction_speed:.2f}x"

    if stage in (STAGE_REPACKAGING, STAGE_WASTE, STAGE_COMPLETE):
        overall_efficiency = min(99, 85 + reaction_speed * 3)
        efficiency_text.text = f"Енергийна ефективност (MOX): {overall_efficiency:.0f}%"

    if progress >= 100.0:
        if stage == STAGE_COOLING:
            enter_stage(STAGE_DISSOLUTION)
        elif stage == STAGE_DISSOLUTION:
            enter_stage(STAGE_REPACKAGING)
        elif stage == STAGE_REPACKAGING:
            enter_stage(STAGE_WASTE)
        elif stage == STAGE_WASTE:
            enter_stage(STAGE_COMPLETE)


def reset_simulation():
    global reaction_speed
    reaction_speed = 1.0
    waste_chunk.enabled = False
    waste_lid.position = (STATION_X[STAGE_WASTE], 0.2, 0)
    tank.color = color.rgb(0, 180, 100)
    mould.color = color.rgb(140, 140, 150)
    waste_cask.color = color.rgb(90, 90, 20)
    product.scale = 1.2
    product.color = color.orange
    product.position = (STATION_X[STAGE_COOLING], 0.5, 0)
    for p in particles:
        p.enabled = False
    robot_base.position = (STATION_X[STAGE_COOLING], 3.5, 0)
    robot_arm.position = (STATION_X[STAGE_COOLING], 2, 0)
    title_text.text = STAGE_NAMES[STAGE_IDLE]
    title_text.color = color.yellow
    temp_text.text = ""
    progress_text.text = "Прогрес на етапа: 0%"
    efficiency_text.text = "Енергийна ефективност (MOX): 0%"
    global stage, progress
    stage = STAGE_IDLE
    progress = 0.0


def input(key):
    global reaction_speed

    if key == 'space' and stage == STAGE_IDLE:
        enter_stage(STAGE_COOLING)

    elif key == 'up arrow':
        reaction_speed = min(5.0, reaction_speed + 0.5)

    elif key == 'down arrow':
        reaction_speed = max(0.5, reaction_speed - 0.5)

    elif key == 'r':
        reset_simulation()


app.run()
