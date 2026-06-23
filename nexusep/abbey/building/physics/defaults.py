"""
ABBEY building physics defaults.

Phase 2.10:
- default assumptions by zone_use
- future-compatible with footprint/height/use inference

No physics solver here.
"""

import copy

from nexusep.abbey.building.model import normalize_zone_use


DEFAULT_ZONE_USE_ASSUMPTIONS = {
    "generic": {
        "is_conditioned": True,
        "is_occupied_space": True,
        "height_m": 2.7,
        "thermal_mass_class": "medium",
        "default_infiltration_ach": 0.3,
        "daylight_utilization_factor": 0.5,
        "visual_comfort_target_lux": 300.0,
        "background_noise_db": 30.0,
        "room_absorption_factor": 0.3,
    },
    "living_room": {
        "is_conditioned": True,
        "is_occupied_space": True,
        "visual_comfort_target_lux": 200.0,
        "background_noise_db": 30.0,
    },
    "bedroom": {
        "is_conditioned": True,
        "is_occupied_space": True,
        "visual_comfort_target_lux": 100.0,
        "background_noise_db": 25.0,
    },
    "kitchen": {
        "is_conditioned": True,
        "is_occupied_space": True,
        "visual_comfort_target_lux": 300.0,
        "default_infiltration_ach": 0.5,
        "background_noise_db": 35.0,
    },
    "bathroom": {
        "is_conditioned": True,
        "is_occupied_space": True,
        "visual_comfort_target_lux": 200.0,
        "default_infiltration_ach": 0.7,
        "background_noise_db": 35.0,
    },
    "office": {
        "is_conditioned": True,
        "is_occupied_space": True,
        "visual_comfort_target_lux": 500.0,
        "background_noise_db": 30.0,
    },
    "laundry": {
        "is_conditioned": False,
        "is_occupied_space": False,
        "visual_comfort_target_lux": 200.0,
        "background_noise_db": 40.0,
    },
    "corridor": {
        "is_conditioned": True,
        "is_occupied_space": False,
        "visual_comfort_target_lux": 100.0,
        "background_noise_db": 30.0,
    },
    "entrance": {
        "is_conditioned": True,
        "is_occupied_space": False,
        "visual_comfort_target_lux": 100.0,
        "background_noise_db": 30.0,
    },
    "shared_corridor": {
        "is_conditioned": True,
        "is_occupied_space": False,
        "visual_comfort_target_lux": 100.0,
        "background_noise_db": 35.0,
    },
    "technical_room": {
        "is_conditioned": False,
        "is_occupied_space": False,
        "visual_comfort_target_lux": 200.0,
        "background_noise_db": 45.0,
    },
}


def defaults_for_zone_use(zone_use):
    zone_use = normalize_zone_use(zone_use)

    defaults = copy.deepcopy(DEFAULT_ZONE_USE_ASSUMPTIONS["generic"])

    if zone_use in DEFAULT_ZONE_USE_ASSUMPTIONS:
        defaults.update(copy.deepcopy(DEFAULT_ZONE_USE_ASSUMPTIONS[zone_use]))

    return defaults