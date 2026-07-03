"""
ABBEY array ID registries and mappings.

Purpose:
    Convert human-readable names/IDs into stable integer IDs.

Important:
    - This module is outside the hot timestep loop.
    - Strings are allowed here.
    - Dicts are allowed here.
    - The array core should only see integer IDs.
"""

from dataclasses import dataclass
from typing import Dict, Optional

import numpy as np

from nexusep.abbey.arrays import schema


# =============================================================================
# Basic mapping helpers
# =============================================================================

def _as_list(values, name):
    if values is None:
        return []

    if isinstance(values, list):
        return values

    if isinstance(values, tuple):
        return list(values)

    raise TypeError("%s must be a list or tuple." % name)


def assert_unique_names(names, label):
    """
    Validate that names are unique.
    """
    seen = set()
    duplicates = []

    for name in names:
        if name in seen:
            duplicates.append(name)
        seen.add(name)

    if duplicates:
        raise ValueError(
            "%s contains duplicate names/IDs: %s"
            % (label, duplicates)
        )

    return True


def make_name_to_id(names, label):
    """
    Create a stable name -> integer ID mapping.

    IDs are assigned in list order.
    """
    names = _as_list(names, label)
    assert_unique_names(names, label)

    mapping = {}
    for i, name in enumerate(names):
        if not isinstance(name, str):
            raise TypeError(
                "%s entries must be strings. Got %s."
                % (label, type(name).__name__)
            )
        mapping[name] = i

    return mapping


def invert_mapping(mapping, label):
    """
    Create an integer ID -> name mapping.
    """
    inverse = {}

    for name, integer_id in mapping.items():
        integer_id = int(integer_id)

        if integer_id in inverse:
            raise ValueError(
                "%s has duplicate integer ID %s."
                % (label, integer_id)
            )

        inverse[integer_id] = name

    return inverse


def encode_name(name, mapping, label):
    """
    Convert one human-readable name to an integer ID.
    """
    if name not in mapping:
        raise KeyError(
            "Unknown %s name/ID: %s. Known values: %s"
            % (label, name, sorted(mapping.keys()))
        )

    return int(mapping[name])


def decode_id(integer_id, inverse_mapping, label):
    """
    Convert one integer ID back to a human-readable name.
    """
    integer_id = int(integer_id)

    if integer_id not in inverse_mapping:
        raise KeyError(
            "Unknown %s integer ID: %s. Known IDs: %s"
            % (label, integer_id, sorted(inverse_mapping.keys()))
        )

    return inverse_mapping[integer_id]


def encode_names(names, mapping, label, dtype=np.int64):
    """
    Convert a list of names to an integer numpy array.
    """
    encoded = np.zeros((len(names),), dtype=dtype)

    for i, name in enumerate(names):
        encoded[i] = encode_name(name, mapping, label)

    return encoded


def decode_ids(ids, inverse_mapping, label):
    """
    Convert a list/array of integer IDs back to names.
    """
    result = []

    for integer_id in ids:
        result.append(decode_id(integer_id, inverse_mapping, label))

    return result


# =============================================================================
# Default type-name mappings
# =============================================================================

def make_default_zone_type_name_to_id():
    return {
        "unknown": schema.ZONE_TYPE_UNKNOWN,
        "outside": schema.ZONE_TYPE_OUTSIDE,
        "main_room": schema.ZONE_TYPE_MAIN_ROOM,
        "bedroom": schema.ZONE_TYPE_BEDROOM,
        "kitchen": schema.ZONE_TYPE_KITCHEN,
        "bathroom": schema.ZONE_TYPE_BATHROOM,
        "living_room": schema.ZONE_TYPE_LIVING_ROOM,
        "corridor": schema.ZONE_TYPE_CORRIDOR,
        "storage": schema.ZONE_TYPE_STORAGE,
        "shared_space": schema.ZONE_TYPE_SHARED_SPACE,
    }


def make_default_hvac_mode_name_to_id():
    return {
        "off": schema.HVAC_MODE_OFF,
        "heating": schema.HVAC_MODE_HEATING,
        "cooling": schema.HVAC_MODE_COOLING,
        "auto": schema.HVAC_MODE_AUTO,
        "ventilation_only": schema.HVAC_MODE_VENTILATION_ONLY,
    }


def make_default_ventilation_mode_name_to_id():
    return {
        "off": schema.VENTILATION_MODE_OFF,
        "natural": schema.VENTILATION_MODE_NATURAL,
        "mechanical": schema.VENTILATION_MODE_MECHANICAL,
        "hybrid": schema.VENTILATION_MODE_HYBRID,
    }


def make_default_action_type_name_to_id():
    return {
        "none": schema.ACTION_TYPE_NONE,

        "idle": schema.ACTION_TYPE_IDLE,
        "sleep": schema.ACTION_TYPE_SLEEP,
        "wake_up": schema.ACTION_TYPE_WAKE_UP,
        "leave_home": schema.ACTION_TYPE_LEAVE_HOME,
        "return_home": schema.ACTION_TYPE_RETURN_HOME,
        "move_zone": schema.ACTION_TYPE_MOVE_ZONE,

        "eat": schema.ACTION_TYPE_EAT,
        "cook": schema.ACTION_TYPE_COOK,
        "drink": schema.ACTION_TYPE_DRINK,
        "make_coffee": schema.ACTION_TYPE_MAKE_COFFEE,
        "do_laundry": schema.ACTION_TYPE_DO_LAUNDRY,
        "shower": schema.ACTION_TYPE_SHOWER,

        "open_window": schema.ACTION_TYPE_OPEN_WINDOW,
        "close_window": schema.ACTION_TYPE_CLOSE_WINDOW,
        "turn_light_on": schema.ACTION_TYPE_TURN_LIGHT_ON,
        "turn_light_off": schema.ACTION_TYPE_TURN_LIGHT_OFF,
        "turn_heating_on": schema.ACTION_TYPE_TURN_HEATING_ON,
        "turn_heating_off": schema.ACTION_TYPE_TURN_HEATING_OFF,
        "turn_cooling_on": schema.ACTION_TYPE_TURN_COOLING_ON,
        "turn_cooling_off": schema.ACTION_TYPE_TURN_COOLING_OFF,
        "adjust_thermostat": schema.ACTION_TYPE_ADJUST_THERMOSTAT,
        "open_blinds": schema.ACTION_TYPE_OPEN_BLINDS,
        "close_blinds": schema.ACTION_TYPE_CLOSE_BLINDS,
        "turn_ventilation_on": schema.ACTION_TYPE_TURN_VENTILATION_ON,
        "turn_ventilation_off": schema.ACTION_TYPE_TURN_VENTILATION_OFF,
    }


def make_default_appliance_type_name_to_id():
    return {
        "none": schema.APPLIANCE_TYPE_NONE,
        "lights": schema.APPLIANCE_TYPE_LIGHTS,
        "washing_machine": schema.APPLIANCE_TYPE_WASHING_MACHINE,
        "dishwasher": schema.APPLIANCE_TYPE_DISHWASHER,
        "oven": schema.APPLIANCE_TYPE_OVEN,
        "stove": schema.APPLIANCE_TYPE_STOVE,
        "fridge": schema.APPLIANCE_TYPE_FRIDGE,
        "coffee_machine": schema.APPLIANCE_TYPE_COFFEE_MACHINE,
        "computer": schema.APPLIANCE_TYPE_COMPUTER,
        "tv": schema.APPLIANCE_TYPE_TV,
        "shower": schema.APPLIANCE_TYPE_SHOWER,
    }


def make_default_process_type_name_to_id():
    return {
        "none": schema.PROCESS_TYPE_NONE,
        "washing_machine": schema.PROCESS_TYPE_WASHING_MACHINE,
        "dishwasher": schema.PROCESS_TYPE_DISHWASHER,
        "oven": schema.PROCESS_TYPE_OVEN,
        "stove": schema.PROCESS_TYPE_STOVE,
        "shower": schema.PROCESS_TYPE_SHOWER,
        "cooking": schema.PROCESS_TYPE_COOKING,
        "coffee_machine": schema.PROCESS_TYPE_COFFEE_MACHINE,
    }


def make_default_process_state_name_to_id():
    return {
        "inactive": schema.PROCESS_STATE_INACTIVE,
        "active": schema.PROCESS_STATE_ACTIVE,
        "paused": schema.PROCESS_STATE_PAUSED,
        "finished": schema.PROCESS_STATE_FINISHED,
    }


def make_default_occupancy_state_name_to_id():
    return {
        "unknown": schema.OCCUPANCY_UNKNOWN,
        "away": schema.OCCUPANCY_AWAY,
        "home_awake": schema.OCCUPANCY_HOME_AWAKE,
        "home_sleeping": schema.OCCUPANCY_HOME_SLEEPING,
        "transition": schema.OCCUPANCY_TRANSITION,
    }


# =============================================================================
# Registry dataclass
# =============================================================================

@dataclass
class SimulationIDRegistry:
    """
    Human-readable ID registry for ABBEY arrays.

    This object is used by encoders and decoders.

    Do not use this object inside timestep kernels.
    """

    person_name_to_id: Dict[str, int]
    person_id_to_name: Dict[int, str]

    dwelling_name_to_id: Dict[str, int]
    dwelling_id_to_name: Dict[int, str]

    zone_name_to_id: Dict[str, int]
    zone_id_to_name: Dict[int, str]

    building_name_to_id: Dict[str, int]
    building_id_to_name: Dict[int, str]

    system_name_to_id: Dict[str, int]
    system_id_to_name: Dict[int, str]

    # Action row IDs, for rows in action_static.
    action_name_to_id: Dict[str, int]
    action_id_to_name: Dict[int, str]

    # Type mappings.
    action_type_name_to_id: Dict[str, int]
    action_type_id_to_name: Dict[int, str]

    appliance_type_name_to_id: Dict[str, int]
    appliance_type_id_to_name: Dict[int, str]

    zone_type_name_to_id: Dict[str, int]
    zone_type_id_to_name: Dict[int, str]

    hvac_mode_name_to_id: Dict[str, int]
    hvac_mode_id_to_name: Dict[int, str]

    ventilation_mode_name_to_id: Dict[str, int]
    ventilation_mode_id_to_name: Dict[int, str]

    process_type_name_to_id: Dict[str, int]
    process_type_id_to_name: Dict[int, str]

    process_state_name_to_id: Dict[str, int]
    process_state_id_to_name: Dict[int, str]

    occupancy_state_name_to_id: Dict[str, int]
    occupancy_state_id_to_name: Dict[int, str]

    @classmethod
    def from_names(
        cls,
        person_names=None,
        dwelling_names=None,
        zone_names=None,
        building_names=None,
        system_names=None,
        action_names=None,
    ):
        """
        Build a complete registry from readable entity names.
        """
        person_name_to_id = make_name_to_id(
            person_names or [],
            "person_names",
        )
        dwelling_name_to_id = make_name_to_id(
            dwelling_names or [],
            "dwelling_names",
        )
        zone_name_to_id = make_name_to_id(
            zone_names or [],
            "zone_names",
        )
        building_name_to_id = make_name_to_id(
            building_names or [],
            "building_names",
        )
        system_name_to_id = make_name_to_id(
            system_names or [],
            "system_names",
        )
        action_name_to_id = make_name_to_id(
            action_names or [],
            "action_names",
        )

        action_type_name_to_id = make_default_action_type_name_to_id()
        appliance_type_name_to_id = make_default_appliance_type_name_to_id()
        zone_type_name_to_id = make_default_zone_type_name_to_id()
        hvac_mode_name_to_id = make_default_hvac_mode_name_to_id()
        ventilation_mode_name_to_id = make_default_ventilation_mode_name_to_id()
        process_type_name_to_id = make_default_process_type_name_to_id()
        process_state_name_to_id = make_default_process_state_name_to_id()
        occupancy_state_name_to_id = make_default_occupancy_state_name_to_id()

        return cls(
            person_name_to_id=person_name_to_id,
            person_id_to_name=invert_mapping(person_name_to_id, "person"),

            dwelling_name_to_id=dwelling_name_to_id,
            dwelling_id_to_name=invert_mapping(dwelling_name_to_id, "dwelling"),

            zone_name_to_id=zone_name_to_id,
            zone_id_to_name=invert_mapping(zone_name_to_id, "zone"),

            building_name_to_id=building_name_to_id,
            building_id_to_name=invert_mapping(building_name_to_id, "building"),

            system_name_to_id=system_name_to_id,
            system_id_to_name=invert_mapping(system_name_to_id, "system"),

            action_name_to_id=action_name_to_id,
            action_id_to_name=invert_mapping(action_name_to_id, "action"),

            action_type_name_to_id=action_type_name_to_id,
            action_type_id_to_name=invert_mapping(
                action_type_name_to_id,
                "action_type",
            ),

            appliance_type_name_to_id=appliance_type_name_to_id,
            appliance_type_id_to_name=invert_mapping(
                appliance_type_name_to_id,
                "appliance_type",
            ),

            zone_type_name_to_id=zone_type_name_to_id,
            zone_type_id_to_name=invert_mapping(
                zone_type_name_to_id,
                "zone_type",
            ),

            hvac_mode_name_to_id=hvac_mode_name_to_id,
            hvac_mode_id_to_name=invert_mapping(
                hvac_mode_name_to_id,
                "hvac_mode",
            ),

            ventilation_mode_name_to_id=ventilation_mode_name_to_id,
            ventilation_mode_id_to_name=invert_mapping(
                ventilation_mode_name_to_id,
                "ventilation_mode",
            ),

            process_type_name_to_id=process_type_name_to_id,
            process_type_id_to_name=invert_mapping(
                process_type_name_to_id,
                "process_type",
            ),

            process_state_name_to_id=process_state_name_to_id,
            process_state_id_to_name=invert_mapping(
                process_state_name_to_id,
                "process_state",
            ),

            occupancy_state_name_to_id=occupancy_state_name_to_id,
            occupancy_state_id_to_name=invert_mapping(
                occupancy_state_name_to_id,
                "occupancy_state",
            ),
        )

    def validate(self):
        validate_registry(self)
        return True

    # -------------------------------------------------------------------------
    # Entity encode/decode helpers
    # -------------------------------------------------------------------------

    def person_id(self, name):
        return encode_name(name, self.person_name_to_id, "person")

    def person_name(self, integer_id):
        return decode_id(integer_id, self.person_id_to_name, "person")

    def dwelling_id(self, name):
        return encode_name(name, self.dwelling_name_to_id, "dwelling")

    def dwelling_name(self, integer_id):
        return decode_id(integer_id, self.dwelling_id_to_name, "dwelling")

    def zone_id(self, name):
        return encode_name(name, self.zone_name_to_id, "zone")

    def zone_name(self, integer_id):
        return decode_id(integer_id, self.zone_id_to_name, "zone")

    def building_id(self, name):
        return encode_name(name, self.building_name_to_id, "building")

    def building_name(self, integer_id):
        return decode_id(integer_id, self.building_id_to_name, "building")

    def system_id(self, name):
        return encode_name(name, self.system_name_to_id, "system")

    def system_name(self, integer_id):
        return decode_id(integer_id, self.system_id_to_name, "system")

    def action_id(self, name):
        return encode_name(name, self.action_name_to_id, "action")

    def action_name(self, integer_id):
        return decode_id(integer_id, self.action_id_to_name, "action")

    # -------------------------------------------------------------------------
    # Type encode/decode helpers
    # -------------------------------------------------------------------------

    def action_type_id(self, name):
        return encode_name(name, self.action_type_name_to_id, "action_type")

    def action_type_name(self, integer_id):
        return decode_id(integer_id, self.action_type_id_to_name, "action_type")

    def appliance_type_id(self, name):
        return encode_name(name, self.appliance_type_name_to_id, "appliance_type")

    def appliance_type_name(self, integer_id):
        return decode_id(integer_id, self.appliance_type_id_to_name, "appliance_type")

    def zone_type_id(self, name):
        return encode_name(name, self.zone_type_name_to_id, "zone_type")

    def zone_type_name(self, integer_id):
        return decode_id(integer_id, self.zone_type_id_to_name, "zone_type")

    def hvac_mode_id(self, name):
        return encode_name(name, self.hvac_mode_name_to_id, "hvac_mode")

    def hvac_mode_name(self, integer_id):
        return decode_id(integer_id, self.hvac_mode_id_to_name, "hvac_mode")

    def ventilation_mode_id(self, name):
        return encode_name(
            name,
            self.ventilation_mode_name_to_id,
            "ventilation_mode",
        )

    def ventilation_mode_name(self, integer_id):
        return decode_id(
            integer_id,
            self.ventilation_mode_id_to_name,
            "ventilation_mode",
        )

    def process_type_id(self, name):
        return encode_name(name, self.process_type_name_to_id, "process_type")

    def process_type_name(self, integer_id):
        return decode_id(integer_id, self.process_type_id_to_name, "process_type")

    def process_state_id(self, name):
        return encode_name(name, self.process_state_name_to_id, "process_state")

    def process_state_name(self, integer_id):
        return decode_id(integer_id, self.process_state_id_to_name, "process_state")

    def occupancy_state_id(self, name):
        return encode_name(name, self.occupancy_state_name_to_id, "occupancy_state")

    def occupancy_state_name(self, integer_id):
        return decode_id(
            integer_id,
            self.occupancy_state_id_to_name,
            "occupancy_state",
        )


# =============================================================================
# Registry validation
# =============================================================================

def _validate_forward_reverse_mapping(forward, reverse, label):
    """
    Validate one mapping pair.
    """
    for name, integer_id in forward.items():
        integer_id = int(integer_id)

        if integer_id not in reverse:
            raise ValueError(
                "%s reverse mapping is missing integer ID %s."
                % (label, integer_id)
            )

        if reverse[integer_id] != name:
            raise ValueError(
                "%s mapping mismatch for %s -> %s."
                % (label, name, integer_id)
            )

    for integer_id, name in reverse.items():
        integer_id = int(integer_id)

        if name not in forward:
            raise ValueError(
                "%s forward mapping is missing name %s."
                % (label, name)
            )

        if int(forward[name]) != integer_id:
            raise ValueError(
                "%s reverse mismatch for %s -> %s."
                % (label, integer_id, name)
            )

    return True


def _validate_contiguous_zero_based_entity_mapping(forward, label):
    """
    Entity row IDs should be 0, 1, 2, ..., n-1.

    This is for things that correspond directly to array rows:
        persons, zones, dwellings, buildings, systems, actions.

    Type mappings do not need this because schema action IDs can have gaps.
    """
    ids = sorted([int(v) for v in forward.values()])

    expected = list(range(len(ids)))

    if ids != expected:
        raise ValueError(
            "%s IDs must be contiguous and zero-based. Expected %s, got %s."
            % (label, expected, ids)
        )

    return True


def validate_registry(registry):
    """
    Validate all registry mappings.
    """
    _validate_forward_reverse_mapping(
        registry.person_name_to_id,
        registry.person_id_to_name,
        "person",
    )
    _validate_forward_reverse_mapping(
        registry.dwelling_name_to_id,
        registry.dwelling_id_to_name,
        "dwelling",
    )
    _validate_forward_reverse_mapping(
        registry.zone_name_to_id,
        registry.zone_id_to_name,
        "zone",
    )
    _validate_forward_reverse_mapping(
        registry.building_name_to_id,
        registry.building_id_to_name,
        "building",
    )
    _validate_forward_reverse_mapping(
        registry.system_name_to_id,
        registry.system_id_to_name,
        "system",
    )
    _validate_forward_reverse_mapping(
        registry.action_name_to_id,
        registry.action_id_to_name,
        "action",
    )

    _validate_forward_reverse_mapping(
        registry.action_type_name_to_id,
        registry.action_type_id_to_name,
        "action_type",
    )
    _validate_forward_reverse_mapping(
        registry.appliance_type_name_to_id,
        registry.appliance_type_id_to_name,
        "appliance_type",
    )
    _validate_forward_reverse_mapping(
        registry.zone_type_name_to_id,
        registry.zone_type_id_to_name,
        "zone_type",
    )
    _validate_forward_reverse_mapping(
        registry.hvac_mode_name_to_id,
        registry.hvac_mode_id_to_name,
        "hvac_mode",
    )
    _validate_forward_reverse_mapping(
        registry.ventilation_mode_name_to_id,
        registry.ventilation_mode_id_to_name,
        "ventilation_mode",
    )
    _validate_forward_reverse_mapping(
        registry.process_type_name_to_id,
        registry.process_type_id_to_name,
        "process_type",
    )
    _validate_forward_reverse_mapping(
        registry.process_state_name_to_id,
        registry.process_state_id_to_name,
        "process_state",
    )
    _validate_forward_reverse_mapping(
        registry.occupancy_state_name_to_id,
        registry.occupancy_state_id_to_name,
        "occupancy_state",
    )

    _validate_contiguous_zero_based_entity_mapping(
        registry.person_name_to_id,
        "person",
    )
    _validate_contiguous_zero_based_entity_mapping(
        registry.dwelling_name_to_id,
        "dwelling",
    )
    _validate_contiguous_zero_based_entity_mapping(
        registry.zone_name_to_id,
        "zone",
    )
    _validate_contiguous_zero_based_entity_mapping(
        registry.building_name_to_id,
        "building",
    )
    _validate_contiguous_zero_based_entity_mapping(
        registry.system_name_to_id,
        "system",
    )
    _validate_contiguous_zero_based_entity_mapping(
        registry.action_name_to_id,
        "action",
    )

    return True


# =============================================================================
# Array reference validation helpers
# =============================================================================

def _as_int_array(values, label):
    """
    Convert numeric values to int array for validation.
    """
    array = np.asarray(values)

    if array.size == 0:
        return array.astype(np.int64)

    rounded = np.round(array)

    if not np.allclose(array, rounded):
        raise ValueError("%s contains non-integer ID values." % label)

    return rounded.astype(np.int64)


def _validate_ids_in_range(values, valid_min, valid_max_exclusive, label, allow_missing=True):
    """
    Validate that all IDs are inside [valid_min, valid_max_exclusive).

    MISSING_ID is allowed when allow_missing=True.
    """
    ids = _as_int_array(values, label)

    for integer_id in ids.flatten():
        if allow_missing and integer_id == schema.MISSING_ID:
            continue

        if integer_id < valid_min or integer_id >= valid_max_exclusive:
            raise ValueError(
                "%s contains invalid ID %s. Valid range is [%s, %s)."
                % (label, integer_id, valid_min, valid_max_exclusive)
            )

    return True


def _validate_ids_in_set(values, valid_ids, label, allow_missing=True):
    """
    Validate that all IDs are members of a known set.
    """
    ids = _as_int_array(values, label)
    valid_ids = set([int(v) for v in valid_ids])

    for integer_id in ids.flatten():
        if allow_missing and integer_id == schema.MISSING_ID:
            continue

        if integer_id not in valid_ids:
            raise ValueError(
                "%s contains invalid ID %s. Valid IDs are %s."
                % (label, integer_id, sorted(valid_ids))
            )

    return True


def validate_state_references(state):
    """
    Validate references between arrays in a SimulationArrayState.

    This is outside the timestep core.

    Checks:
        - every person belongs to a valid dwelling
        - every person is in a valid zone or MISSING_ID
        - every zone belongs to a valid dwelling/building
        - every dwelling belongs to a valid building
        - every system references valid dwelling/zone
        - every action references valid target zone/system/appliance/type
        - every process references valid person/dwelling/zone/system/type/state
    """
    dynamic = state.dynamic
    static = state.static

    n_persons = dynamic.person_state.shape[0]
    n_zones = dynamic.zone_state.shape[0]
    n_dwellings = dynamic.dwelling_state.shape[0]
    n_buildings = dynamic.building_state.shape[0]
    n_systems = dynamic.system_state.shape[0]

    valid_action_types = make_default_action_type_name_to_id().values()
    valid_appliance_types = make_default_appliance_type_name_to_id().values()
    valid_process_types = make_default_process_type_name_to_id().values()
    valid_process_states = make_default_process_state_name_to_id().values()
    valid_zone_types = make_default_zone_type_name_to_id().values()
    valid_hvac_modes = make_default_hvac_mode_name_to_id().values()
    valid_ventilation_modes = make_default_ventilation_mode_name_to_id().values()
    valid_occupancy_states = make_default_occupancy_state_name_to_id().values()

    # -------------------------------------------------------------------------
    # person_state references
    # -------------------------------------------------------------------------

    _validate_ids_in_range(
        dynamic.person_state[:, schema.PERSON_ID],
        0,
        n_persons,
        "person_state PERSON_ID",
        allow_missing=False,
    )
    _validate_ids_in_range(
        dynamic.person_state[:, schema.PERSON_DWELLING_ID],
        0,
        n_dwellings,
        "person_state PERSON_DWELLING_ID",
        allow_missing=False,
    )
    _validate_ids_in_range(
        dynamic.person_state[:, schema.PERSON_CURRENT_ZONE_ID],
        0,
        n_zones,
        "person_state PERSON_CURRENT_ZONE_ID",
        allow_missing=True,
    )
    _validate_ids_in_range(
        dynamic.person_state[:, schema.PERSON_PREVIOUS_ZONE_ID],
        0,
        n_zones,
        "person_state PERSON_PREVIOUS_ZONE_ID",
        allow_missing=True,
    )
    _validate_ids_in_set(
        dynamic.person_state[:, schema.PERSON_OCCUPANCY_STATE],
        valid_occupancy_states,
        "person_state PERSON_OCCUPANCY_STATE",
        allow_missing=False,
    )
    _validate_ids_in_set(
        dynamic.person_state[:, schema.PERSON_CURRENT_ACTION_TYPE],
        valid_action_types,
        "person_state PERSON_CURRENT_ACTION_TYPE",
        allow_missing=False,
    )
    _validate_ids_in_range(
        dynamic.person_state[:, schema.PERSON_ACTION_TARGET_ZONE_ID],
        0,
        n_zones,
        "person_state PERSON_ACTION_TARGET_ZONE_ID",
        allow_missing=True,
    )
    _validate_ids_in_range(
        dynamic.person_state[:, schema.PERSON_ACTION_TARGET_SYSTEM_ID],
        0,
        n_systems,
        "person_state PERSON_ACTION_TARGET_SYSTEM_ID",
        allow_missing=True,
    )

    # -------------------------------------------------------------------------
    # person_static references
    # -------------------------------------------------------------------------

    _validate_ids_in_range(
        static.person_static[:, schema.PERSON_STATIC_ID],
        0,
        n_persons,
        "person_static PERSON_STATIC_ID",
        allow_missing=False,
    )
    _validate_ids_in_range(
        static.person_static[:, schema.PERSON_STATIC_DWELLING_ID],
        0,
        n_dwellings,
        "person_static PERSON_STATIC_DWELLING_ID",
        allow_missing=False,
    )
    _validate_ids_in_range(
        static.person_static[:, schema.PERSON_STATIC_HOME_ZONE_ID],
        0,
        n_zones,
        "person_static PERSON_STATIC_HOME_ZONE_ID",
        allow_missing=True,
    )
    _validate_ids_in_range(
        static.person_static[:, schema.PERSON_STATIC_SLEEP_ZONE_ID],
        0,
        n_zones,
        "person_static PERSON_STATIC_SLEEP_ZONE_ID",
        allow_missing=True,
    )
    _validate_ids_in_range(
        static.person_static[:, schema.PERSON_STATIC_WORK_ZONE_ID],
        0,
        n_zones,
        "person_static PERSON_STATIC_WORK_ZONE_ID",
        allow_missing=True,
    )

    # -------------------------------------------------------------------------
    # zone references
    # -------------------------------------------------------------------------

    _validate_ids_in_range(
        dynamic.zone_state[:, schema.ZONE_ID],
        0,
        n_zones,
        "zone_state ZONE_ID",
        allow_missing=False,
    )
    _validate_ids_in_range(
        dynamic.zone_state[:, schema.ZONE_DWELLING_ID],
        0,
        n_dwellings,
        "zone_state ZONE_DWELLING_ID",
        allow_missing=True,
    )
    _validate_ids_in_range(
        dynamic.zone_state[:, schema.ZONE_BUILDING_ID],
        0,
        n_buildings,
        "zone_state ZONE_BUILDING_ID",
        allow_missing=True,
    )
    _validate_ids_in_set(
        dynamic.zone_state[:, schema.ZONE_TYPE],
        valid_zone_types,
        "zone_state ZONE_TYPE",
        allow_missing=False,
    )

    _validate_ids_in_range(
        static.zone_static[:, schema.ZONE_STATIC_ID],
        0,
        n_zones,
        "zone_static ZONE_STATIC_ID",
        allow_missing=False,
    )
    _validate_ids_in_range(
        static.zone_static[:, schema.ZONE_STATIC_DWELLING_ID],
        0,
        n_dwellings,
        "zone_static ZONE_STATIC_DWELLING_ID",
        allow_missing=True,
    )
    _validate_ids_in_range(
        static.zone_static[:, schema.ZONE_STATIC_BUILDING_ID],
        0,
        n_buildings,
        "zone_static ZONE_STATIC_BUILDING_ID",
        allow_missing=True,
    )
    _validate_ids_in_set(
        static.zone_static[:, schema.ZONE_STATIC_TYPE],
        valid_zone_types,
        "zone_static ZONE_STATIC_TYPE",
        allow_missing=False,
    )

    # -------------------------------------------------------------------------
    # dwelling references
    # -------------------------------------------------------------------------

    _validate_ids_in_range(
        dynamic.dwelling_state[:, schema.DWELLING_ID],
        0,
        n_dwellings,
        "dwelling_state DWELLING_ID",
        allow_missing=False,
    )
    _validate_ids_in_range(
        dynamic.dwelling_state[:, schema.DWELLING_BUILDING_ID],
        0,
        n_buildings,
        "dwelling_state DWELLING_BUILDING_ID",
        allow_missing=False,
    )

    _validate_ids_in_range(
        static.dwelling_static[:, schema.DWELLING_STATIC_ID],
        0,
        n_dwellings,
        "dwelling_static DWELLING_STATIC_ID",
        allow_missing=False,
    )
    _validate_ids_in_range(
        static.dwelling_static[:, schema.DWELLING_STATIC_BUILDING_ID],
        0,
        n_buildings,
        "dwelling_static DWELLING_STATIC_BUILDING_ID",
        allow_missing=False,
    )

    # -------------------------------------------------------------------------
    # building references
    # -------------------------------------------------------------------------

    _validate_ids_in_range(
        dynamic.building_state[:, schema.BUILDING_ID],
        0,
        n_buildings,
        "building_state BUILDING_ID",
        allow_missing=False,
    )

    _validate_ids_in_range(
        static.building_static[:, schema.BUILDING_STATIC_ID],
        0,
        n_buildings,
        "building_static BUILDING_STATIC_ID",
        allow_missing=False,
    )

    # -------------------------------------------------------------------------
    # system references
    # -------------------------------------------------------------------------

    _validate_ids_in_range(
        dynamic.system_state[:, schema.SYSTEM_ID],
        0,
        n_systems,
        "system_state SYSTEM_ID",
        allow_missing=False,
    )
    _validate_ids_in_range(
        dynamic.system_state[:, schema.SYSTEM_DWELLING_ID],
        0,
        n_dwellings,
        "system_state SYSTEM_DWELLING_ID",
        allow_missing=False,
    )
    _validate_ids_in_range(
        dynamic.system_state[:, schema.SYSTEM_ZONE_ID],
        0,
        n_zones,
        "system_state SYSTEM_ZONE_ID",
        allow_missing=False,
    )
    _validate_ids_in_set(
        dynamic.system_state[:, schema.SYSTEM_HVAC_MODE],
        valid_hvac_modes,
        "system_state SYSTEM_HVAC_MODE",
        allow_missing=False,
    )
    _validate_ids_in_set(
        dynamic.system_state[:, schema.SYSTEM_VENTILATION_MODE],
        valid_ventilation_modes,
        "system_state SYSTEM_VENTILATION_MODE",
        allow_missing=False,
    )

    _validate_ids_in_range(
        static.system_static[:, schema.SYSTEM_STATIC_ID],
        0,
        n_systems,
        "system_static SYSTEM_STATIC_ID",
        allow_missing=False,
    )
    _validate_ids_in_range(
        static.system_static[:, schema.SYSTEM_STATIC_DWELLING_ID],
        0,
        n_dwellings,
        "system_static SYSTEM_STATIC_DWELLING_ID",
        allow_missing=False,
    )
    _validate_ids_in_range(
        static.system_static[:, schema.SYSTEM_STATIC_ZONE_ID],
        0,
        n_zones,
        "system_static SYSTEM_STATIC_ZONE_ID",
        allow_missing=False,
    )

    # -------------------------------------------------------------------------
    # action_static references
    # -------------------------------------------------------------------------

    _validate_ids_in_set(
        static.action_static[:, schema.ACTION_TYPE],
        valid_action_types,
        "action_static ACTION_TYPE",
        allow_missing=False,
    )
    _validate_ids_in_range(
        static.action_static[:, schema.ACTION_DEFAULT_TARGET_ZONE_ID],
        0,
        n_zones,
        "action_static ACTION_DEFAULT_TARGET_ZONE_ID",
        allow_missing=True,
    )
    _validate_ids_in_range(
        static.action_static[:, schema.ACTION_DEFAULT_TARGET_SYSTEM_ID],
        0,
        n_systems,
        "action_static ACTION_DEFAULT_TARGET_SYSTEM_ID",
        allow_missing=True,
    )
    _validate_ids_in_set(
        static.action_static[:, schema.ACTION_DEFAULT_APPLIANCE_TYPE],
        valid_appliance_types,
        "action_static ACTION_DEFAULT_APPLIANCE_TYPE",
        allow_missing=False,
    )

    # -------------------------------------------------------------------------
    # process_state references
    # -------------------------------------------------------------------------

    if dynamic.process_state.shape[0] > 0:
        _validate_ids_in_set(
            dynamic.process_state[:, schema.PROCESS_TYPE],
            valid_process_types,
            "process_state PROCESS_TYPE",
            allow_missing=False,
        )
        _validate_ids_in_set(
            dynamic.process_state[:, schema.PROCESS_STATE],
            valid_process_states,
            "process_state PROCESS_STATE",
            allow_missing=False,
        )
        _validate_ids_in_range(
            dynamic.process_state[:, schema.PROCESS_PERSON_ID],
            0,
            n_persons,
            "process_state PROCESS_PERSON_ID",
            allow_missing=True,
        )
        _validate_ids_in_range(
            dynamic.process_state[:, schema.PROCESS_DWELLING_ID],
            0,
            n_dwellings,
            "process_state PROCESS_DWELLING_ID",
            allow_missing=True,
        )
        _validate_ids_in_range(
            dynamic.process_state[:, schema.PROCESS_ZONE_ID],
            0,
            n_zones,
            "process_state PROCESS_ZONE_ID",
            allow_missing=True,
        )
        _validate_ids_in_range(
            dynamic.process_state[:, schema.PROCESS_SYSTEM_ID],
            0,
            n_systems,
            "process_state PROCESS_SYSTEM_ID",
            allow_missing=True,
        )

    return True


# =============================================================================
# Convenience constructor
# =============================================================================

def make_basic_registry(
    n_persons=1,
    n_zones=1,
    n_dwellings=1,
    n_buildings=1,
    n_systems=1,
    action_names=None,
):
    """
    Create a simple registry for tests.

    Names are generated as:
        person_0, person_1, ...
        zone_0, zone_1, ...
    """
    if action_names is None:
        action_names = [
            "idle",
            "sleep",
            "eat",
            "open_window",
            "close_window",
            "turn_light_on",
            "turn_light_off",
        ]

    person_names = []
    for i in range(n_persons):
        person_names.append("person_%s" % i)

    zone_names = []
    for i in range(n_zones):
        zone_names.append("zone_%s" % i)

    dwelling_names = []
    for i in range(n_dwellings):
        dwelling_names.append("dwelling_%s" % i)

    building_names = []
    for i in range(n_buildings):
        building_names.append("building_%s" % i)

    system_names = []
    for i in range(n_systems):
        system_names.append("system_%s" % i)

    return SimulationIDRegistry.from_names(
        person_names=person_names,
        dwelling_names=dwelling_names,
        zone_names=zone_names,
        building_names=building_names,
        system_names=system_names,
        action_names=action_names,
    )