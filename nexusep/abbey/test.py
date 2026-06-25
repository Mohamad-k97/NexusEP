from pathlib import Path
import tempfile
import json

from nexusep.abbey.simulation.runner import AbbeySimulation


def assert_true(value, message):
    if not value:
        raise AssertionError(message)


# def make_minimal_config(path):
#     """
#     Use your normal abbey_config.jsonc if this minimal config is not enough
#     for your current action/decision modules.
#     """

#     config = {
#         "actions": {
#             "do_nothing": {
#                 "category": "passive",
#                 "execution_type": "passive",
#                 "duration_minutes": 15,
#                 "power_w": 0,
#                 "activity_intensity": 0,
#                 "effort": 0,
#                 "requires_home": False,
#                 "requires_awake": False,
#                 "blocks_actor": False,
#                 "background_process": False,
#                 "can_continue_without_actor": True,
#                 "can_be_interrupted": True,
#                 "can_fill_remaining_time": True,
#                 "can_repeat": True,
#                 "target_zone_role": "current",
#                 "system_effects": {},
#                 "person_effects": {},
#                 "action_cooldowns_on_start": {}
#             }
#         },
#         "needs": {},
#         "health": {},
#         "decision": {},
#         "perception": {},
#         "schedule": {},
#         "idle_movement": {}
#     }

#     Path(path).write_text(json.dumps(config), encoding="utf-8")


def test_initialize_creates_default_physics_graph():
    with tempfile.TemporaryDirectory() as tmp:
        PROJECT_ROOT = Path(__file__).resolve().parents[2]
        config_path = (
            PROJECT_ROOT
            / "nexusep"
            / "data"
            / "abbey"
            / "config"
            / "abbey_config.jsonc"
        )
        print(config_path)

        # make_minimal_config(config_path)

        sim = AbbeySimulation.initialize(
            config_path=config_path,
            duration_hours=0.25,
            dt_minutes=15.0,
            use_building_performance=True,
        )

        assert_true(
            sim.building_model is not None,
            "Default simulation should create building_model.",
        )

        assert_true(
            sim.building_physics_graph is not None,
            "Default simulation should create building_physics_graph.",
        )

        assert_true(
            len(sim.building_physics_graph.zone_connections) > 0,
            "Default physics graph should contain room adjacency.",
        )

        assert_true(
            sim.building_performance_model is not None,
            "Default simulation should create building_performance_model.",
        )

        assert_true(
            getattr(sim.building_performance_model, "physics_graph", None)
            is sim.building_physics_graph,
            "Performance model should receive the default physics graph.",
        )

    print("PASS: test_initialize_creates_default_physics_graph")


def test_default_run_records_interzone_coupling():
    with tempfile.TemporaryDirectory() as tmp:
        PROJECT_ROOT = Path(__file__).resolve().parents[2]
        config_path = (
            PROJECT_ROOT
            / "nexusep"
            / "data"
            / "abbey"
            / "config"
            / "abbey_config.jsonc"
        )

        sim = AbbeySimulation.initialize(
            config_path=config_path,
            duration_hours=0.25,
            dt_minutes=15.0,
            use_building_performance=True,
        )

        # Force a visible temperature difference before the first timestep.
        living = "dwelling_1_living_room"
        bedroom = "dwelling_1_bedroom_1"

        living_state = sim.building_model.get_zone_state(living)
        bedroom_state = sim.building_model.get_zone_state(bedroom)

        sim.building_model.set_zone_state(
            living,
            living_state.copy(
                indoor_temp_c=30.0,
                indoor_mass_temp_c=30.0,
            ),
        )

        sim.building_model.set_zone_state(
            bedroom,
            bedroom_state.copy(
                indoor_temp_c=15.0,
                indoor_mass_temp_c=15.0,
            ),
        )

        sim.run()

        assert_true(
            len(sim.building_records) > 0,
            "Simulation should store building records.",
        )

        last_record = sim.building_records[-1]

        assert_true(
            last_record.get("physics_engine_active", False),
            "Default simulation should use physics engine.",
        )

        assert_true(
            last_record.get(
                "physics_engine_has_interzone_thermal_network",
                False,
            ),
            "Default simulation should use interzone thermal network.",
        )

        assert_true(
            last_record.get(
                "physics_engine_interzone_thermal_link_count",
                0,
            ) > 0,
            "Default simulation should record interzone thermal links.",
        )

        assert_true(
            len(sim.building_interzone_thermal_records) > 0,
            "Default simulation should store interzone thermal flow records.",
        )

    print("PASS: test_default_run_records_interzone_coupling")


if __name__ == "__main__":
    test_initialize_creates_default_physics_graph()
    test_default_run_records_interzone_coupling()

    print("Phase 11.8 default simulation physics-graph tests passed.")
    
    
import json
import math
import tempfile
from pathlib import Path
from dataclasses import replace
from types import SimpleNamespace

from nexusep.abbey.building.factory import (
    make_default_family_building,
    make_default_family_physics_graph,
)
from nexusep.abbey.building.physics.engine import (
    BuildingPhysicsStepInput,
    run_building_physics_step,
)
from nexusep.abbey.building.systems import (
    ZoneControlCommand,
    ZoneSystemSpec,
)
from nexusep.abbey.simulation.runner import AbbeySimulation


def assert_true(value, message):
    if not value:
        raise AssertionError(message)


def assert_greater(a, b, message):
    if not float(a) > float(b):
        raise AssertionError(message + " Got " + str(a) + " <= " + str(b))


def assert_less(a, b, message):
    if not float(a) < float(b):
        raise AssertionError(message + " Got " + str(a) + " >= " + str(b))


def assert_near(a, b, tolerance, message):
    if abs(float(a) - float(b)) > float(tolerance):
        raise AssertionError(
            message
            + " Got "
            + str(a)
            + " vs "
            + str(b)
            + " with tolerance "
            + str(tolerance)
        )


def zone_id(role):
    return "dwelling_1_" + role


def make_weather(outdoor_temp_c=20.0):
    return SimpleNamespace(
        datetime=None,
        outdoor_temperature_c=float(outdoor_temp_c),
        outdoor_co2_ppm=420.0,
        wind_speed_m_s=0.0,
        wind_direction_deg=0.0,
        global_horizontal_radiation_w_m2=0.0,
        direct_normal_radiation_w_m2=0.0,
        diffuse_horizontal_radiation_w_m2=0.0,
        outdoor_illuminance_lux=0.0,
        relative_humidity_percent=50.0,
        atmospheric_pressure_pa=101325.0,
    )


def set_zone_temp(building, zid, temp_c):
    old_state = building.get_zone_state(zid)

    building.set_zone_state(
        zid,
        old_state.copy(
            indoor_temp_c=float(temp_c),
            indoor_mass_temp_c=float(temp_c),
        ),
    )


def make_neutral_commands_and_specs(building):
    commands = {}
    specs = {}

    for zid, zone_model in building.all_zone_models().items():
        commands[zid] = ZoneControlCommand(
            zone_id=zid,
            dwelling_id=zone_model.dwelling_id,
            building_id=zone_model.building_id,
            heating_on=False,
            heating_power_fraction=0.0,
            cooling_on=False,
            cooling_power_fraction=0.0,
            ventilation_flow_m3_h=0.0,
            lights_on=False,
            lighting_power_w=0.0,
            window_open=False,
            window_opening_fraction=0.0,
            curtain_open=True,
        )

        specs[zid] = ZoneSystemSpec(
            zone_id=zid,
            dwelling_id=zone_model.dwelling_id,
            building_id=zone_model.building_id,
            has_heating=False,
            heating_capacity_w=0.0,
            has_cooling=False,
            cooling_capacity_w=0.0,
            has_ventilation=False,
            ventilation_flow_m3_h=0.0,
            has_lighting=False,
            lighting_power_w=0.0,
            has_operable_window=False,
            has_shading=False,
        )

    return commands, specs


def run_engine_case(
    living_temp_c,
    bedroom_temp_c,
    laundry_temp_c=None,
    door_open_fraction=0.0,
    dt_minutes=15.0,
    strong_coupling=False,
):
    building = make_default_family_building()
    graph = make_default_family_physics_graph(building)

    living = zone_id("living_room")
    bedroom = zone_id("bedroom_1")
    laundry = zone_id("laundry")

    graph.set_zone_connection_open_fraction(
        "door_living_room_bedroom_1",
        door_open_fraction,
    )

    if strong_coupling:
        door_id = "door_living_room_bedroom_1"
        old_connection = graph.zone_connections[door_id]

        graph.zone_connections[door_id] = replace(
            old_connection,
            open_fraction=1.0,
            area_m2=5.0,
            max_opening_area_m2=20.0,
            u_value_w_m2k=5.0,
        )

    set_zone_temp(building, living, living_temp_c)
    set_zone_temp(building, bedroom, bedroom_temp_c)

    if laundry_temp_c is not None:
        set_zone_temp(building, laundry, laundry_temp_c)

    old_living = building.get_zone_state(living).indoor_temp_c
    old_bedroom = building.get_zone_state(bedroom).indoor_temp_c

    commands, specs = make_neutral_commands_and_specs(building)

    result = run_building_physics_step(
        BuildingPhysicsStepInput(
            building_model=building,
            dt_minutes=float(dt_minutes),
            physics_graph=graph,
            weather_state=make_weather(outdoor_temp_c=20.0),
            zone_control_commands=commands,
            zone_system_specs=specs,
        ),
        require_physics_graph=True,
        write_back_to_building_model=True,
    )

    return {
        "building": building,
        "graph": graph,
        "result": result,
        "old_living": old_living,
        "old_bedroom": old_bedroom,
        "new_living": building.get_zone_state(living).indoor_temp_c,
        "new_bedroom": building.get_zone_state(bedroom).indoor_temp_c,
    }


def find_link_records(result, zone_a, zone_b):
    out = []

    wanted = set([zone_a, zone_b])

    for record in result.interzone_thermal_flow_records:
        pair = set([record.zone_a_id, record.zone_b_id])

        if pair == wanted:
            out.append(record)

    return out


def assert_temperatures_finite_and_plausible(building, lower_c=-50.0, upper_c=80.0):
    for zid, state in building.all_zone_states().items():
        air_t = float(state.indoor_temp_c)
        mass_t = float(getattr(state, "indoor_mass_temp_c", air_t))

        assert_true(
            math.isfinite(air_t),
            "Air temperature should be finite for " + zid,
        )

        assert_true(
            math.isfinite(mass_t),
            "Mass temperature should be finite for " + zid,
        )

        assert_true(
            lower_c <= air_t <= upper_c,
            "Air temperature outside plausible range for "
            + zid
            + ": "
            + str(air_t),
        )

        assert_true(
            lower_c <= mass_t <= upper_c,
            "Mass temperature outside plausible range for "
            + zid
            + ": "
            + str(mass_t),
        )


# ============================================================
# ENGINE-LOOP SCENARIOS
# ============================================================

def test_closed_door_adjacent_bedroom_warms_slowly():
    case = run_engine_case(
        living_temp_c=30.0,
        bedroom_temp_c=15.0,
        door_open_fraction=0.0,
        dt_minutes=15.0,
    )

    assert_less(
        case["new_living"],
        case["old_living"],
        "Hot living room should cool through interzone coupling.",
    )

    assert_greater(
        case["new_bedroom"],
        case["old_bedroom"],
        "Cold bedroom should warm through interzone coupling.",
    )

    assert_true(
        case["result"].building_record.get(
            "has_interzone_thermal_network",
            False,
        ),
        "Engine building record should show interzone network.",
    )

    print("PASS: test_closed_door_adjacent_bedroom_warms_slowly")


def test_open_door_warms_bedroom_faster_than_closed_door():
    closed_case = run_engine_case(
        living_temp_c=30.0,
        bedroom_temp_c=15.0,
        door_open_fraction=0.0,
        dt_minutes=15.0,
    )

    open_case = run_engine_case(
        living_temp_c=30.0,
        bedroom_temp_c=15.0,
        door_open_fraction=1.0,
        dt_minutes=15.0,
    )

    assert_greater(
        open_case["new_bedroom"],
        closed_case["new_bedroom"],
        "Open door should warm the cold bedroom faster than closed door.",
    )

    assert_less(
        open_case["new_living"],
        closed_case["new_living"],
        "Open door should cool the hot living room faster than closed door.",
    )

    print("PASS: test_open_door_warms_bedroom_faster_than_closed_door")


def test_unrelated_room_has_no_direct_heat_link():
    case = run_engine_case(
        living_temp_c=30.0,
        bedroom_temp_c=15.0,
        laundry_temp_c=5.0,
        door_open_fraction=1.0,
        dt_minutes=15.0,
    )

    living = zone_id("living_room")
    laundry = zone_id("laundry")

    direct_records = find_link_records(
        result=case["result"],
        zone_a=living,
        zone_b=laundry,
    )

    assert_true(
        len(direct_records) == 0,
        "Living room and laundry should not have a direct interzone heat link.",
    )

    print("PASS: test_unrelated_room_has_no_direct_heat_link")


def test_equal_adjacent_temperatures_have_zero_interzone_flow():
    case = run_engine_case(
        living_temp_c=20.0,
        bedroom_temp_c=20.0,
        door_open_fraction=1.0,
        dt_minutes=15.0,
    )

    living = zone_id("living_room")
    bedroom = zone_id("bedroom_1")

    records = find_link_records(
        result=case["result"],
        zone_a=living,
        zone_b=bedroom,
    )

    assert_true(
        len(records) > 0,
        "Living-bedroom adjacent links should exist.",
    )

    for record in records:
        assert_near(
            record.q_to_zone_a_w,
            0.0,
            1e-9,
            "Equal adjacent temperatures should produce zero q_to_zone_a_w.",
        )

        assert_near(
            record.q_to_zone_b_w,
            0.0,
            1e-9,
            "Equal adjacent temperatures should produce zero q_to_zone_b_w.",
        )

    print("PASS: test_equal_adjacent_temperatures_have_zero_interzone_flow")


def test_strong_coupling_60_min_timestep_is_stable():
    case = run_engine_case(
        living_temp_c=35.0,
        bedroom_temp_c=5.0,
        door_open_fraction=1.0,
        dt_minutes=60.0,
        strong_coupling=True,
    )

    assert_temperatures_finite_and_plausible(case["building"])

    old_spread = abs(case["old_living"] - case["old_bedroom"])
    new_spread = abs(case["new_living"] - case["new_bedroom"])

    assert_less(
        new_spread,
        old_spread,
        "Strong coupling with 60 min timestep should reduce temperature spread.",
    )

    assert_true(
        5.0 <= case["new_living"] <= 35.0,
        "Strong coupling should not make living room overshoot pair bounds.",
    )

    assert_true(
        5.0 <= case["new_bedroom"] <= 35.0,
        "Strong coupling should not make bedroom overshoot pair bounds.",
    )

    print("PASS: test_strong_coupling_60_min_timestep_is_stable")


# ============================================================
# DEFAULT SIMULATION + OUTPUTS
# ============================================================




def test_default_simulation_run_and_outputs_do_not_break():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        config_path = tmp_path / "abbey_config.jsonc"
        output_path = tmp_path / "outputs"

        PROJECT_ROOT = Path(__file__).resolve().parents[2]
        config_path = (
            PROJECT_ROOT
            / "nexusep"
            / "data"
            / "abbey"
            / "config"
            / "abbey_config.jsonc"
        )
        sim = AbbeySimulation.initialize(
            config_path=config_path,
            duration_hours=0.25,
            dt_minutes=15.0,
            use_building_performance=True,
        )

        assert_true(
            getattr(sim, "building_physics_graph", None) is not None,
            "Default simulation should have building_physics_graph after Phase 11.8.",
        )

        living = zone_id("living_room")
        bedroom = zone_id("bedroom_1")

        set_zone_temp(sim.building_model, living, 30.0)
        set_zone_temp(sim.building_model, bedroom, 15.0)

        sim.run()

        assert_true(
            len(sim.building_records) > 0,
            "Default simulation should produce building records.",
        )

        assert_true(
            len(sim.building_zone_records) > 0,
            "Default simulation should produce building zone records.",
        )

        assert_true(
            len(sim.building_interzone_thermal_records) > 0,
            "Default simulation should store interzone thermal records.",
        )

        last_record = sim.building_records[-1]

        assert_true(
            last_record.get("physics_engine_active", False),
            "Default simulation should use active physics engine.",
        )

        assert_true(
            last_record.get(
                "physics_engine_has_interzone_thermal_network",
                False,
            ),
            "Default simulation should use interzone thermal network.",
        )

        debug_paths = sim.save_building_debug_outputs(output_path / "debug")
        yearly_paths = sim.save_building_yearly_outputs(output_path / "yearly")

        assert_true(
            isinstance(debug_paths, dict),
            "Debug output function should return path dictionary.",
        )

        assert_true(
            isinstance(yearly_paths, dict),
            "Yearly output function should return path dictionary.",
        )

        assert_true(
            len(debug_paths) > 0,
            "Debug outputs should not be empty.",
        )

        assert_true(
            len(yearly_paths) > 0,
            "Yearly outputs should not be empty.",
        )

    print("PASS: test_default_simulation_run_and_outputs_do_not_break")


if __name__ == "__main__":
    test_closed_door_adjacent_bedroom_warms_slowly()
    test_open_door_warms_bedroom_faster_than_closed_door()
    test_unrelated_room_has_no_direct_heat_link()
    test_equal_adjacent_temperatures_have_zero_interzone_flow()
    test_strong_coupling_60_min_timestep_is_stable()
    test_default_simulation_run_and_outputs_do_not_break()

    print("Phase 11.9 full Phase 11 integration tests passed.")