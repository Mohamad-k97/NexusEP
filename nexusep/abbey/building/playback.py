"""
Interactive HTML playback for ABBEY building simulations.

Creates one self-contained HTML file with:
- temperature mode
- lighting mode
- people/occupancy mode
- play/pause
- time slider
- speed control

No matplotlib. No GIF. No external JS libraries.
"""

from pathlib import Path
from typing import Any, Dict, List
import ast
import json
import math


ROOM_LAYOUT = {
    "bedroom_1": {"label": "Bedroom 1", "x": 0.05, "y": 0.62, "w": 0.28, "h": 0.33},
    "bedroom_2": {"label": "Bedroom 2", "x": 0.35, "y": 0.62, "w": 0.25, "h": 0.33},
    "office": {"label": "Office", "x": 0.62, "y": 0.62, "w": 0.33, "h": 0.33},
    "living_room": {"label": "Living room", "x": 0.05, "y": 0.30, "w": 0.43, "h": 0.30},
    "entrance": {"label": "Entrance", "x": 0.50, "y": 0.30, "w": 0.20, "h": 0.30},
    "kitchen": {"label": "Kitchen", "x": 0.72, "y": 0.30, "w": 0.23, "h": 0.30},
    "bathroom": {"label": "Bathroom", "x": 0.05, "y": 0.05, "w": 0.25, "h": 0.22},
    "laundry": {"label": "Laundry", "x": 0.32, "y": 0.05, "w": 0.23, "h": 0.22},
}


def save_building_playback_html(
    sim: Any,
    output_path: Any,
    max_hours: float = 24.0,
    frame_stride_minutes: int = 1,
) -> Path:
    zone_df = sim.building_zone_records_to_dataframe()

    if zone_df.empty:
        raise ValueError("No building zone records found. Run the simulation first.")

    action_df = None

    if hasattr(sim, "building_action_event_records_to_dataframe"):
        action_df = sim.building_action_event_records_to_dataframe()

    payload = _make_payload(
        zone_df=zone_df,
        action_df=action_df,
        max_hours=max_hours,
        frame_stride_minutes=frame_stride_minutes,
    )

    html = _make_html(payload)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as file:
        file.write(html)

    return output_path


def _make_payload(
    zone_df,
    action_df,
    max_hours: float,
    frame_stride_minutes: int,
) -> Dict[str, Any]:
    df = zone_df.copy()

    if "day" not in df.columns:
        df["day"] = 0

    if "hour" not in df.columns:
        df["hour"] = 0.0

    df["time_h"] = df["day"].astype(float) * 24.0 + df["hour"].astype(float)
    df["sim_minute"] = (df["time_h"] * 60.0).round().astype(int)

    start_minute = int(df["sim_minute"].min())
    end_minute = start_minute + int(max_hours * 60.0)

    df = df[
        (df["sim_minute"] >= start_minute)
        & (df["sim_minute"] < end_minute)
    ].copy()

    if frame_stride_minutes <= 0:
        frame_stride_minutes = 1

    valid_minutes = sorted(df["sim_minute"].unique())
    selected_minutes = [
        minute for minute in valid_minutes
        if (minute - start_minute) % frame_stride_minutes == 0
    ]

    actions_by_minute = _make_actions_by_minute(action_df)

    frames = []

    for frame_index, sim_minute in enumerate(selected_minutes):
        frame_df = df[df["sim_minute"] == sim_minute]

        minute_of_day = sim_minute % (24 * 60)
        day = sim_minute // (24 * 60)
        hour_int = minute_of_day // 60
        minute_int = minute_of_day % 60
        hour_float = hour_int + minute_int / 60.0

        zones = {}

        for _, row in frame_df.iterrows():
            zone_id = str(row.get("zone_id"))
            room_key = _room_key_from_zone_id(zone_id)

            people = _parse_people(row.get("occupied_person_ids", []))

            zones[room_key] = {
                "zone_id": zone_id,
                "zone_name": str(row.get("zone_name", room_key)),
                "room_key": room_key,
                "indoor_temp_c": _safe_float(row.get("indoor_temp_c", row.get("indoor_temp", 20.0)), 20.0),
                "co2_ppm": _safe_float(row.get("co2_ppm", 600.0), 600.0),
                "indoor_daylight": _safe_float(row.get("indoor_daylight", 0.5), 0.5),
                "heating_on": _safe_bool(row.get("heating_on", False)),
                "cooling_on": _safe_bool(row.get("cooling_on", False)),
                "lights_on": _safe_bool(row.get("lights_on", False)),
                "window_open": _safe_bool(row.get("window_open", False)),
                "curtain_open": not _safe_bool(row.get("curtain_closed", False)),
                "number_of_people": int(_safe_float(row.get("number_of_people", len(people)), len(people))),
                "people": people,
            }

        frames.append(
            {
                "frame_index": frame_index,
                "sim_minute": int(sim_minute),
                "day": int(day),
                "hour": int(hour_int),
                "minute": int(minute_int),
                "hour_float": float(hour_float),
                "outside_temp_c": _estimate_outdoor_temp(hour_float),
                "outside_light": _outside_light_fraction(hour_float),
                "zones": zones,
                "actions": actions_by_minute.get(int(sim_minute), {}),
            }
        )

    return {
        "room_layout": ROOM_LAYOUT,
        "frames": frames,
        "frame_stride_minutes": frame_stride_minutes,
        "max_hours": max_hours,
    }


def _make_actions_by_minute(action_df) -> Dict[int, Dict[str, str]]:
    out = {}

    if action_df is None or action_df.empty:
        return out

    df = action_df.copy()

    if "day" not in df.columns:
        df["day"] = 0

    if "hour" not in df.columns:
        df["hour"] = 0.0

    df["sim_minute"] = (
        (df["day"].astype(float) * 24.0 + df["hour"].astype(float)) * 60.0
    ).round().astype(int)

    for _, row in df.iterrows():
        minute = int(row["sim_minute"])
        person_id = str(row.get("occupant_id", row.get("actor_id", "")))
        action_name = str(row.get("action_name", ""))

        if not person_id or not action_name:
            continue

        out.setdefault(minute, {})[person_id] = action_name

    return out


def _room_key_from_zone_id(zone_id: Any) -> str:
    value = str(zone_id)

    if value.startswith("dwelling_"):
        parts = value.split("_")

        if len(parts) >= 3 and parts[0] == "dwelling" and parts[1].isdigit():
            return "_".join(parts[2:])

    return value


def _parse_people(value: Any) -> List[str]:
    if value is None:
        return []

    if isinstance(value, list):
        return [str(item) for item in value]

    if isinstance(value, tuple):
        return [str(item) for item in value]

    if isinstance(value, str):
        text = value.strip()

        if not text:
            return []

        try:
            parsed = ast.literal_eval(text)
        except Exception:
            parsed = None

        if isinstance(parsed, list):
            return [str(item) for item in parsed]

        text = text.replace("[", "").replace("]", "").strip()

        if not text:
            return []

        return [
            item.strip().strip("'").strip('"')
            for item in text.split(",")
            if item.strip()
        ]

    return []


def _safe_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def _safe_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value

    if isinstance(value, str):
        return value.lower() in ("true", "1", "yes", "on")

    return bool(value)


def _estimate_outdoor_temp(hour: float) -> float:
    return 10.0 + 6.0 * math.sin(2.0 * math.pi * (float(hour) - 8.0) / 24.0)


def _outside_light_fraction(hour: float) -> float:
    hour = float(hour)

    if hour < 6.0 or hour > 20.0:
        return 0.05

    angle = math.pi * (hour - 6.0) / 14.0

    return max(0.05, math.sin(angle))


def _make_html(payload: Dict[str, Any]) -> str:
    payload_json = json.dumps(payload, ensure_ascii=False)

    html = r"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>ABBEY Building Playback</title>
<style>
    body {
        margin: 0;
        font-family: Arial, sans-serif;
        background: #111827;
        color: #f9fafb;
    }

    #topbar {
        padding: 12px 16px;
        background: #020617;
        display: flex;
        gap: 12px;
        align-items: center;
        border-bottom: 1px solid #334155;
        flex-wrap: wrap;
    }

    button, select, input {
        font-size: 14px;
    }

    button {
        padding: 6px 12px;
        cursor: pointer;
    }

    select {
        padding: 6px;
    }

    #timeSlider {
        width: 380px;
    }

    #canvasWrap {
        display: flex;
        justify-content: center;
        padding: 16px;
    }

    canvas {
        background: #ffffff;
        border: 1px solid #334155;
        box-shadow: 0 8px 30px rgba(0,0,0,0.35);
    }

    .small {
        color: #cbd5e1;
        font-size: 13px;
    }
</style>
</head>
<body>

<div id="topbar">
    <button id="playButton">Play</button>

    <label class="small">Mode</label>
    <select id="modeSelect">
        <option value="temperature">Temperature</option>
        <option value="co2">CO₂ concentration</option>
        <option value="lighting">Lighting</option>
        <option value="people">People</option>
    </select>

    <label class="small">Frame</label>
    <input id="timeSlider" type="range" min="0" max="0" value="0">

    <label class="small">Speed</label>
    <select id="speedSelect">
        <option value="500">Slow</option>
        <option value="250">Normal</option>
        <option value="100" selected>Fast</option>
        <option value="50">Very fast</option>
    </select>

    <span id="timeLabel" class="small"></span>
</div>

<div id="canvasWrap">
    <canvas id="canvas" width="1100" height="760"></canvas>
</div>

<script>
const DATA = __DATA_JSON__;

const canvas = document.getElementById("canvas");
const ctx = canvas.getContext("2d");

const playButton = document.getElementById("playButton");
const modeSelect = document.getElementById("modeSelect");
const timeSlider = document.getElementById("timeSlider");
const speedSelect = document.getElementById("speedSelect");
const timeLabel = document.getElementById("timeLabel");

let frameIndex = 0;
let timer = null;
let playing = false;

timeSlider.max = Math.max(0, DATA.frames.length - 1);

playButton.onclick = function () {
    if (playing) {
        stopPlayback();
    } else {
        startPlayback();
    }
};

modeSelect.onchange = draw;
timeSlider.oninput = function () {
    frameIndex = parseInt(timeSlider.value);
    draw();
};

speedSelect.onchange = function () {
    if (playing) {
        stopPlayback();
        startPlayback();
    }
};

function startPlayback() {
    playing = true;
    playButton.textContent = "Pause";

    timer = setInterval(function () {
        frameIndex += 1;

        if (frameIndex >= DATA.frames.length) {
            frameIndex = 0;
        }

        timeSlider.value = frameIndex;
        draw();
    }, parseInt(speedSelect.value));
}

function stopPlayback() {
    playing = false;
    playButton.textContent = "Play";

    if (timer !== null) {
        clearInterval(timer);
        timer = null;
    }
}

function draw() {
    if (DATA.frames.length === 0) {
        return;
    }

    const frame = DATA.frames[frameIndex];
    const mode = modeSelect.value;

    drawBackground(frame, mode);
    drawRooms(frame, mode);
    drawLegend(frame, mode);
    drawHeader(frame, mode);

    timeLabel.textContent =
        "Day " + frame.day +
        " | " + pad2(frame.hour) +
        ":" + pad2(frame.minute) +
        " | frame " + (frameIndex + 1) + "/" + DATA.frames.length;
}

function drawBackground(frame, mode) {
    let color;

    if (mode === "temperature") {
        color = tempColor(frame.outside_temp_c);
    } else {
        color = outsideLightColor(frame.outside_light);
    }

    ctx.fillStyle = color;
    ctx.fillRect(0, 0, canvas.width, canvas.height);
}

function drawRooms(frame, mode) {
    const layout = DATA.room_layout;

    for (const roomKey in layout) {
        const room = layout[roomKey];
        const zone = frame.zones[roomKey];

        const x = room.x * canvas.width;
        const y = room.y * canvas.height;
        const w = room.w * canvas.width;
        const h = room.h * canvas.height;

        let face = "#f3f4f6";
        let metric = "";

        if (zone) {
            if (mode === "temperature") {
                face = tempColor(zone.indoor_temp_c);
                metric = zone.indoor_temp_c.toFixed(1) + " °C";
            }
            
            if (mode === "co2") {
                face = co2Color(zone.co2_ppm);
                metric = Math.round(zone.co2_ppm) + " ppm";
            }

            if (mode === "lighting") {
                if (zone.lights_on) {
                    face = "#fff2a8";
                    metric = "light on";
                } else {
                    face = daylightColor(zone.indoor_daylight);
                    metric = "light off";
                }
            }

            if (mode === "people") {
                if (zone.number_of_people > 0) {
                    face = "#d7ecff";
                } else {
                    face = "#f4f4f5";
                }

                metric = zone.number_of_people + " people";
            }
        }

        ctx.fillStyle = face;
        ctx.strokeStyle = "#111827";
        ctx.lineWidth = 2;

        roundRect(ctx, x, y, w, h, 6, true, true);

        ctx.fillStyle = "#111827";
        ctx.font = "bold 14px Arial";
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText(room.label, x + w / 2, y + h / 2 - 10);

        ctx.font = "12px Arial";
        ctx.fillText(metric, x + w / 2, y + h / 2 + 10);

        if (zone) {
            drawRoomIcons(zone, x, y, w, h);
            drawPeople(zone, frame, x, y, w, h);
        }
    }
}

function drawRoomIcons(zone, x, y, w, h) {
    const icons = [];

    if (zone.heating_on) icons.push("H");
    if (zone.cooling_on) icons.push("C");
    if (zone.lights_on) icons.push("L");
    if (zone.window_open) icons.push("W");

    ctx.font = "bold 11px Arial";
    ctx.textAlign = "left";
    ctx.textBaseline = "top";

    for (let i = 0; i < icons.length; i++) {
        ctx.fillStyle = "#111827";
        ctx.fillText(icons[i], x + 8 + i * 16, y + 8);
    }
}

function drawPeople(zone, frame, x, y, w, h) {
    const people = zone.people || [];
    const actions = frame.actions || {};

    for (let i = 0; i < people.length; i++) {
        const personId = people[i];
        const pos = personPosition(personId, frame.frame_index, x, y, w, h);

        ctx.beginPath();
        ctx.arc(pos.x, pos.y, 9, 0, 2 * Math.PI);
        ctx.fillStyle = personColor(personId);
        ctx.fill();
        ctx.lineWidth = 2;
        ctx.strokeStyle = "#ffffff";
        ctx.stroke();

        ctx.fillStyle = "#111827";
        ctx.font = "bold 10px Arial";
        ctx.textAlign = "center";
        ctx.textBaseline = "top";
        ctx.fillText(shortPersonLabel(personId), pos.x, pos.y + 11);

        if (actions[personId]) {
            ctx.font = "10px Arial";
            ctx.fillText(actions[personId], pos.x, pos.y + 25);
        }
    }
}

function drawHeader(frame, mode) {
    ctx.fillStyle = "rgba(255,255,255,0.88)";
    roundRect(ctx, 18, 18, 300, 72, 8, true, false);

    ctx.fillStyle = "#111827";
    ctx.textAlign = "left";
    ctx.textBaseline = "top";
    ctx.font = "bold 18px Arial";

    let title = "ABBEY playback";

    if (mode === "temperature") title = "Temperature";
    if (mode === "co2") title = "CO₂ concentration";
    if (mode === "lighting") title = "Lighting";
    if (mode === "people") title = "People movement";

    ctx.fillText(title, 32, 30);

    ctx.font = "14px Arial";
    ctx.fillText(
        "Day " + frame.day + " | " + pad2(frame.hour) + ":" + pad2(frame.minute),
        32,
        55
    );

    if (mode === "temperature") {
        ctx.fillText("Outside: " + frame.outside_temp_c.toFixed(1) + " °C", 32, 73);
    }

    if (mode === "lighting") {
        ctx.fillText("Outside light: " + Math.round(frame.outside_light * 100) + "%", 32, 73);
    }
}

function drawLegend(frame, mode) {
    const x = 870;
    const y = 24;

    ctx.fillStyle = "rgba(255,255,255,0.88)";
    roundRect(ctx, x, y, 205, 90, 8, true, false);

    ctx.fillStyle = "#111827";
    ctx.font = "bold 13px Arial";
    ctx.textAlign = "left";
    ctx.fillText("Legend", x + 14, y + 12);

    ctx.font = "12px Arial";

    if (mode === "temperature") {
        ctx.fillText("Blue = cold", x + 14, y + 36);
        ctx.fillText("White = neutral", x + 14, y + 54);
        ctx.fillText("Red = warm", x + 14, y + 72);
    } else if (mode === "co2") {
        ctx.fillText("Blue = fresh air", x + 14, y + 36);
        ctx.fillText("Yellow = moderate", x + 14, y + 54);
        ctx.fillText("Red = high CO₂", x + 14, y + 72);
    } else if (mode === "lighting") {
        ctx.fillText("Yellow = lights on", x + 14, y + 36);
        ctx.fillText("Dark/bright = daylight", x + 14, y + 54);
    } else {
        ctx.fillText("Dots = occupants", x + 14, y + 36);
        ctx.fillText("Text = current action", x + 14, y + 54);
    }
}

function personPosition(personId, frameIndex, x, y, w, h) {
    const seed = hashString(personId + "_" + frameIndex);
    const r1 = seededRandom(seed);
    const r2 = seededRandom(seed + 991);

    const marginX = 0.15 * w;
    const marginY = 0.18 * h;

    const px = x + marginX + r1 * (w - 2 * marginX);
    const py = y + marginY + r2 * (h - 2 * marginY);

    return {x: px, y: py};
}

function co2Color(co2) {
    const t = clamp((co2 - 400.0) / 1600.0, 0, 1);

    let r, g, b;

    if (t < 0.5) {
        const q = t / 0.5;
        r = 120 + q * (255 - 120);
        g = 190 + q * (230 - 190);
        b = 255 + q * (120 - 255);
    } else {
        const q = (t - 0.5) / 0.5;
        r = 255;
        g = 230 + q * (90 - 230);
        b = 120 + q * (80 - 120);
    }

    return rgb(r, g, b);
}

function tempColor(temp) {
    const t = clamp((temp - 5.0) / 27.0, 0, 1);

    let r, g, b;

    if (t < 0.5) {
        const q = t / 0.5;
        r = 80 + q * (245 - 80);
        g = 140 + q * (245 - 140);
        b = 255;
    } else {
        const q = (t - 0.5) / 0.5;
        r = 245 + q * (255 - 245);
        g = 245 + q * (110 - 245);
        b = 255 + q * (80 - 255);
    }

    return rgb(r, g, b);
}

function outsideLightColor(light) {
    light = clamp(light, 0, 1);

    const dark = [20, 26, 45];
    const bright = [205, 225, 255];

    return rgb(
        dark[0] + light * (bright[0] - dark[0]),
        dark[1] + light * (bright[1] - dark[1]),
        dark[2] + light * (bright[2] - dark[2])
    );
}

function daylightColor(light) {
    light = clamp(light, 0, 1);

    const dark = [55, 58, 65];
    const bright = [235, 235, 225];

    return rgb(
        dark[0] + light * (bright[0] - dark[0]),
        dark[1] + light * (bright[1] - dark[1]),
        dark[2] + light * (bright[2] - dark[2])
    );
}

function personColor(personId) {
    const colors = {
        "working_man": "#2563eb",
        "housewife": "#db2777",
        "schoolboy": "#16a34a",
        "infant": "#f97316",
        "person_1": "#2563eb"
    };

    return colors[personId] || "#7c3aed";
}

function shortPersonLabel(personId) {
    const labels = {
        "working_man": "M",
        "housewife": "W",
        "schoolboy": "S",
        "infant": "B",
        "person_1": "P1"
    };

    if (labels[personId]) return labels[personId];

    return personId.substring(0, 2);
}

function roundRect(ctx, x, y, w, h, r, fill, stroke) {
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.lineTo(x + w - r, y);
    ctx.quadraticCurveTo(x + w, y, x + w, y + r);
    ctx.lineTo(x + w, y + h - r);
    ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
    ctx.lineTo(x + r, y + h);
    ctx.quadraticCurveTo(x, y + h, x, y + h - r);
    ctx.lineTo(x, y + r);
    ctx.quadraticCurveTo(x, y, x + r, y);
    ctx.closePath();

    if (fill) ctx.fill();
    if (stroke) ctx.stroke();
}

function hashString(str) {
    let h = 2166136261;

    for (let i = 0; i < str.length; i++) {
        h ^= str.charCodeAt(i);
        h += (h << 1) + (h << 4) + (h << 7) + (h << 8) + (h << 24);
    }

    return Math.abs(h >>> 0);
}

function seededRandom(seed) {
    const x = Math.sin(seed) * 10000;
    return x - Math.floor(x);
}

function clamp(value, minValue, maxValue) {
    return Math.max(minValue, Math.min(maxValue, value));
}

function rgb(r, g, b) {
    return "rgb(" +
        Math.round(r) + "," +
        Math.round(g) + "," +
        Math.round(b) +
    ")";
}

function pad2(value) {
    value = String(value);

    if (value.length < 2) {
        return "0" + value;
    }

    return value;
}

draw();
</script>
</body>
</html>
"""

    return html.replace("__DATA_JSON__", payload_json)