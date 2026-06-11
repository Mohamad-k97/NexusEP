import json
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, PillowWriter
from matplotlib.patches import Rectangle, Circle


# ============================================================
# USER SETTINGS
# ============================================================


import json
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, PillowWriter
from matplotlib.patches import Rectangle, Circle
from matplotlib.colors import LinearSegmentedColormap


# ============================================================
# PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CSV_PATH = Path(r"abbey_v01_test_08.csv")
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "abbey" / "animations"

FRAME_STRIDE = 1
FPS = 15

# ============================================================
# GENERIC LAYOUT
# ============================================================

# Whole canvas includes "outside" around the dwelling
AX_XMIN = -4.0
AX_XMAX = 14.0
AX_YMIN = -4.0
AX_YMAX = 14.0

# Dwelling square
ROOM_X = 0.0
ROOM_Y = 0.0
ROOM_W = 10.0
ROOM_H = 10.0

# Door location
DOOR_INSIDE = (5.0, 0.2)
DOOR_OUTSIDE = (5.0, -1.2)

# Main activity points
LOCATIONS = {
    "idle": (5.0, 5.0),
    "bed": (2.0, 8.0),
    "coffeemaker": (8.0, 8.0),
    "kitchen": (8.0, 2.0),
    "washing_machine": (2.0, 2.0),
}

ACTION_TO_LOCATION = {
    "sleep": "bed",
    "wake_up": "bed",
    "make_hot_drink": "coffeemaker",
    "cook": "kitchen",
    "eat_simple": "idle",
    "run_washing_machine": "washing_machine",
    "use_laptop": "idle",
    "do_nothing": "idle",
    "open_window": "idle",
    "close_window": "idle",
    "turn_heating_on": "idle",
    "turn_heating_off": "idle",
    "turn_lights_on": "idle",
    "turn_lights_off": "idle",
    "open_curtain": "idle",
    "close_curtain": "idle",
    "shower": "idle",
    "go_to_work": "idle",
    "return_home": "idle",
}

# ============================================================
# COLOR MAPS
# ============================================================

TEMP_CMAP = plt.cm.coolwarm

LIGHT_CMAP = LinearSegmentedColormap.from_list(
    "lightmap",
    [
        (0.00, "#0b1020"),   # very dark
        (0.20, "#1d2a5b"),
        (0.40, "#394d8a"),
        (0.60, "#9a8f3c"),
        (0.80, "#e1c655"),
        (1.00, "#fff47a"),   # bright yellow
    ],
)

CO2_CMAP = plt.cm.plasma


# ============================================================
# HELPERS
# ============================================================

def parse_json_cell(value):
    if pd.isna(value):
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return []
        return json.loads(value)
    return []


def lerp(p0, p1, t):
    return (
        p0[0] + (p1[0] - p0[0]) * t,
        p0[1] + (p1[1] - p0[1]) * t,
    )


def ease_in_out(t):
    t = np.clip(t, 0.0, 1.0)
    return 3 * t**2 - 2 * t**3


def get_target_location(action_name):
    loc_name = ACTION_TO_LOCATION.get(action_name, "idle")
    return LOCATIONS[loc_name]


def normalize_temperature(temp_c):
    return np.clip((temp_c - 10.0) / (30.0 - 10.0), 0.0, 1.0)


def normalize_daylight(light_value):
    return np.clip(light_value, 0.0, 1.0)


def normalize_co2(co2_ppm):
    return np.clip((co2_ppm - 400.0) / (2000.0 - 400.0), 0.0, 1.0)


def get_indoor_light_level(frame):
    # Indoor brightness proxy:
    # daylight contributes naturally, but artificial lights can make the room
    # appear bright even when outside is dark.
    base = float(frame["daylight"])
    if frame["lights_on"]:
        return max(base, 0.95)
    return base


def get_outdoor_light_level(frame):
    return float(frame["daylight"])


def get_indoor_co2(frame):
    return float(frame["co2_ppm"])


def get_outdoor_co2(frame):
    return 420.0


def get_color_value(frame, mode, where):
    if mode == "temperature":
        value = frame["indoor_temp"] if where == "indoor" else frame["outdoor_temp"]
        return normalize_temperature(float(value))
    elif mode == "light":
        if where == "indoor":
            return normalize_daylight(get_indoor_light_level(frame))
        return normalize_daylight(get_outdoor_light_level(frame))
    elif mode == "co2":
        if where == "indoor":
            return normalize_co2(get_indoor_co2(frame))
        return normalize_co2(get_outdoor_co2(frame))
    else:
        return 0.5


def get_colormap(mode):
    if mode == "temperature":
        return TEMP_CMAP
    elif mode == "light":
        return LIGHT_CMAP
    elif mode == "co2":
        return CO2_CMAP
    return plt.cm.viridis


def mode_title(mode):
    if mode == "temperature":
        return "Temperature"
    elif mode == "light":
        return "Light"
    elif mode == "co2":
        return "CO₂"
    return mode


# ============================================================
# DATA EXPANSION
# ============================================================

def expand_simulation_to_frames(df):
    frames = []
    frame_idx = 0

    for _, row in df.iterrows():
        chunk_records = parse_json_cell(row["chunk_records"])

        base_info = {
            "step": int(row["step"]),
            "day": int(row["day"]),
            "hour": float(row["hour"]),
            "indoor_temp": float(row["observation_indoor_temp"]),
            "outdoor_temp": float(row["observation_outdoor_temp"]),
            "co2_ppm": float(row["observation_co2_ppm"]),
            "daylight": float(row["observation_indoor_daylight"]),
            "noise": float(row["observation_indoor_noise"]),
            "tariff": float(row["observation_electricity_tariff"]),
            "heating_on": bool(row["systems_heating_on"]),
            "lights_on": bool(row["systems_lights_on"]),
            "window_open": bool(row["systems_window_open"]),
            "curtain_closed": bool(row.get("systems_curtain_closed", False)),
            "blind_closed": bool(row.get("systems_blind_closed", False)),
            "is_home": bool(row["person_is_home"]),
            "is_sleeping": bool(row["person_is_sleeping"]),
        }

        if not chunk_records:
            frames.append({
                **base_info,
                "frame_idx": frame_idx,
                "chunk_minutes": 1,
                "minute_offset": 0,
                "chunk_phase": 0.0,
                "action_name": "do_nothing",
                "washing_machine_on": False,
            })
            frame_idx += 1
            continue

        for chunk in chunk_records:
            chunk_minutes = int(round(float(chunk.get("chunk_minutes", 1.0))))
            chunk_minutes = max(1, chunk_minutes)

            chunk_label = str(chunk.get("chunk_label", "do_nothing"))
            power_breakdown = chunk.get("power_breakdown", [])

            washing_machine_on = any(
                item.get("name") == "run_washing_machine"
                for item in power_breakdown
            )

            action_name = chunk_label
            if action_name == "continue_blocking_action":
                foreground_names = [
                    item.get("name")
                    for item in power_breakdown
                    if item.get("execution_type") != "background"
                ]
                if foreground_names:
                    action_name = foreground_names[0]
                else:
                    action_name = "do_nothing"

            for m in range(chunk_minutes):
                phase = 0.0 if chunk_minutes == 1 else m / float(chunk_minutes - 1)

                frames.append({
                    **base_info,
                    "frame_idx": frame_idx,
                    "chunk_minutes": chunk_minutes,
                    "minute_offset": m,
                    "chunk_phase": phase,
                    "action_name": action_name,
                    "washing_machine_on": washing_machine_on,
                })
                frame_idx += 1

    return frames


# ============================================================
# MOVEMENT TRACK
# ============================================================

def build_motion_track(frames):
    """
    Compute actual visible position per frame.
    This is done sequentially, so the guy actually moves.
    """
    pos = LOCATIONS["idle"]
    visible = True

    motion_frames = []

    for i, frame in enumerate(frames):
        action = frame["action_name"]
        phase = ease_in_out(frame["chunk_phase"])
        is_home = frame["is_home"]
        is_sleeping = frame["is_sleeping"]

        # Default outputs
        new_visible = visible
        new_pos = pos

        # ---------------------------------------------
        # Outside logic
        # ---------------------------------------------
        if action == "go_to_work":
            # Move toward door then disappear
            if phase < 0.6:
                local_t = phase / 0.6
                new_pos = lerp(pos, DOOR_INSIDE, local_t)
                new_visible = True
            elif phase < 0.85:
                local_t = (phase - 0.6) / 0.25
                new_pos = lerp(DOOR_INSIDE, DOOR_OUTSIDE, local_t)
                new_visible = True
            else:
                new_visible = False
                new_pos = DOOR_OUTSIDE

        elif (not is_home) and action != "return_home":
            new_visible = False
            new_pos = DOOR_OUTSIDE

        elif action == "return_home":
            # Appear from outside and move inside
            if phase < 0.35:
                local_t = phase / 0.35
                new_pos = lerp(DOOR_OUTSIDE, DOOR_INSIDE, local_t)
                new_visible = True
            else:
                target = LOCATIONS["idle"]
                local_t = (phase - 0.35) / 0.65
                new_pos = lerp(DOOR_INSIDE, target, local_t)
                new_visible = True

        # ---------------------------------------------
        # Sleep logic: actually lie on the bed
        # ---------------------------------------------
        elif is_sleeping or action == "sleep":
            new_visible = True
            new_pos = LOCATIONS["bed"]

        # ---------------------------------------------
        # Home actions: move to target, do action,
        # then go back to idle inside the same action chunk
        # ---------------------------------------------
        else:
            target = get_target_location(action)
            idle = LOCATIONS["idle"]

            if action == "do_nothing":
                target = idle

            if target == idle:
                # Smooth drift to idle
                new_pos = lerp(pos, idle, 0.35)
                new_visible = True
            else:
                if phase < 0.25:
                    local_t = phase / 0.25
                    new_pos = lerp(pos, target, local_t)
                elif phase < 0.75:
                    new_pos = target
                else:
                    local_t = (phase - 0.75) / 0.25
                    new_pos = lerp(target, idle, local_t)
                new_visible = True

        motion_frames.append({
            **frame,
            "x": new_pos[0],
            "y": new_pos[1],
            "visible": new_visible,
        })

        pos = new_pos
        visible = new_visible

    return motion_frames


# ============================================================
# DRAWING
# ============================================================

def make_animation(frames, output_path, mode):
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(8, 8))
    ax.set_xlim(AX_XMIN, AX_XMAX)
    ax.set_ylim(AX_YMIN, AX_YMAX)
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_title("ABBEY top-view animation - " + mode_title(mode))

    # Outside zone
    outside_patch = Rectangle(
        (AX_XMIN, AX_YMIN),
        AX_XMAX - AX_XMIN,
        AX_YMAX - AX_YMIN,
        linewidth=1.5,
        edgecolor="black",
        fill=True,
        zorder=0,
    )
    ax.add_patch(outside_patch)

    # Inside room
    room_patch = Rectangle(
        (ROOM_X, ROOM_Y),
        ROOM_W,
        ROOM_H,
        linewidth=2.5,
        edgecolor="black",
        fill=True,
        zorder=1,
    )
    ax.add_patch(room_patch)

    # Door
    ax.plot([4.25, 5.75], [0.0, 0.0], color="black", linewidth=4, zorder=3)
    ax.text(5.0, -0.55, "Door", ha="center", va="top", fontsize=8)

    # Static objects
    bed_patch = Rectangle((1.0, 7.2), 2.2, 1.2, linewidth=1.5, edgecolor="black", fill=False, zorder=3)
    coffee_patch = Rectangle((7.4, 7.4), 1.0, 1.0, linewidth=1.5, edgecolor="black", fill=False, zorder=3)
    kitchen_patch = Rectangle((7.0, 1.3), 2.0, 1.0, linewidth=1.5, edgecolor="black", fill=False, zorder=3)
    wm_patch = Rectangle((1.2, 1.2), 1.2, 1.2, linewidth=1.5, edgecolor="black", fill=False, zorder=3)

    ax.add_patch(bed_patch)
    ax.add_patch(coffee_patch)
    ax.add_patch(kitchen_patch)
    ax.add_patch(wm_patch)

    ax.text(2.1, 8.7, "Bed", ha="center", fontsize=9)
    ax.text(7.9, 8.7, "Coffee", ha="center", fontsize=9)
    ax.text(8.0, 2.7, "Kitchen", ha="center", fontsize=9)
    ax.text(1.8, 2.8, "Washing\nMachine", ha="center", fontsize=9)
    ax.text(5.0, 5.45, "Idle", ha="center", fontsize=8)

    # Guy
    person_dot = Circle((5.0, 5.0), radius=0.22, color="black", zorder=5)
    ax.add_patch(person_dot)

    # Washing machine activity marker
    wm_indicator = Circle(LOCATIONS["washing_machine"], radius=0.38, fill=False, linewidth=2, edgecolor="red", zorder=4)
    ax.add_patch(wm_indicator)
    wm_indicator.set_visible(False)

    # Text boxes
    info_text = ax.text(
        0.02, 0.98, "",
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=9,
        bbox=dict(boxstyle="round", facecolor="white", alpha=0.85),
    )

    env_text = ax.text(
        0.02, 0.02, "",
        transform=ax.transAxes,
        ha="left",
        va="bottom",
        fontsize=9,
        bbox=dict(boxstyle="round", facecolor="white", alpha=0.85),
    )

    cmap = get_colormap(mode)

    def update(i):
        frame = frames[i]

        outside_scalar = get_color_value(frame, mode, "outdoor")
        indoor_scalar = get_color_value(frame, mode, "indoor")

        outside_patch.set_facecolor(cmap(outside_scalar))
        room_patch.set_facecolor(cmap(indoor_scalar))

        # Guy
        if frame["visible"]:
            person_dot.set_visible(True)
            person_dot.center = (frame["x"], frame["y"])
        else:
            person_dot.set_visible(False)

        # Washing machine pulse
        if frame["washing_machine_on"]:
            wm_indicator.set_visible(True)
            pulse = 0.28 + 0.10 * np.sin(i * 0.7)
            wm_indicator.set_radius(abs(pulse))
        else:
            wm_indicator.set_visible(False)

        info_text.set_text(
            "Day {day} | Step {step}\n"
            "Action: {action}\n"
            "At home: {home} | Sleeping: {sleeping}\n"
            "Heating: {heating} | Lights: {lights}\n"
            "Window: {window} | Curtain closed: {curtain}".format(
                day=frame["day"],
                step=frame["step"],
                action=frame["action_name"],
                home=frame["is_home"],
                sleeping=frame["is_sleeping"],
                heating=frame["heating_on"],
                lights=frame["lights_on"],
                window=frame["window_open"],
                curtain=frame["curtain_closed"],
            )
        )

        env_text.set_text(
            "Indoor T: {indoor_t:.1f} °C | Outdoor T: {outdoor_t:.1f} °C\n"
            "Indoor CO₂: {co2:.0f} ppm | Outdoor CO₂: 420 ppm\n"
            "Outdoor daylight: {daylight:.2f} | Indoor-light proxy: {indoor_light:.2f}\n"
            "Tariff: {tariff:.2f}\n"
            "Mode: {mode}".format(
                indoor_t=frame["indoor_temp"],
                outdoor_t=frame["outdoor_temp"],
                co2=frame["co2_ppm"],
                daylight=frame["daylight"],
                indoor_light=get_indoor_light_level(frame),
                tariff=frame["tariff"],
                mode=mode_title(mode),
            )
        )

        return outside_patch, room_patch, person_dot, wm_indicator, info_text, env_text

    anim = FuncAnimation(
        fig,
        update,
        frames=range(0, len(frames), FRAME_STRIDE),
        interval=1000.0 / FPS,
        blit=False,
        repeat=False,
    )

    anim.save(output_path, writer=PillowWriter(fps=FPS))
    plt.close(fig)


# ============================================================
# MAIN
# ============================================================

def main():
    df = pd.read_csv(CSV_PATH)
    frames = expand_simulation_to_frames(df)
    frames = build_motion_track(frames)

    if not frames:
        raise RuntimeError("No frames were created.")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    modes = [
        ("temperature", OUTPUT_DIR / "abbey_topview_temperature.gif"),
        ("light", OUTPUT_DIR / "abbey_topview_light.gif"),
        ("co2", OUTPUT_DIR / "abbey_topview_co2.gif"),
    ]

    for mode, out_path in modes:
        print("Rendering:", mode, "->", out_path)
        make_animation(frames, out_path, mode)

    print("Done.")


if __name__ == "__main__":
    main()