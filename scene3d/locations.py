"""The exotic battlefields."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Location3D:
    key: str
    name: str
    description: str
    light_sq: str
    dark_sq: str
    frame: str            # board frame stone
    rune: tuple           # glowing rune rgb
    sky: dict = field(default_factory=dict)
    fog: str = "#000000"
    fog_density: float = 0.0
    sun_color: str = "#ffffff"
    sun_brightness: float = 1.0
    sun_rotation: tuple = (-50.0, -35.0, 0.0)
    probe_exposure: float = 1.0
    ambient: str = "embers"          # embers | void | snow | clouds
    rock: str = "#3a3330"            # terrain colour
    rock_emissive: str = "#000000"
    accent: str = "#d9e3ee"          # snow / marble
    glow: str = "#ff6a1a"            # lava / crystals
    glow_strength: float = 3.0
    orbit: str = "#3a3330"           # floating debris / clouds
    orbit_opacity: float = 1.0
    orbit_speed: float = 1.5


LOCATIONS: dict[str, Location3D] = {loc.key: loc for loc in [
    Location3D(
        "volcano", "Volcanic Summit",
        "A basalt peak in a ring of erupting volcanoes, high above a lake of fire.",
        "#cdbba1", "#4a3b35", "#2b2220", (255, 120, 40),
        sky=dict(top="#0c0505", mid="#3a140c", horizon="#b84a1c", bottom="#1a0805", sun=(0.62, 0.42),
                 sun_color="#ffb070", sun_size=0.05, stars=40, smoke=True, glow_color="#ff5010"),
        fog="#2a0e08", fog_density=0.32, sun_color="#ffb28a", sun_brightness=1.7,
        sun_rotation=(-38.0, -40.0, 0.0), probe_exposure=0.55, ambient="embers", rock="#1e1a19",
        rock_emissive="#000000", glow="#ff5a14", glow_strength=4.0),
    Location3D(
        "void", "Edge of the Void",
        "A shard of land drifting over the endless abyss between the stars.",
        "#d7d2ea", "#3a3158", "#1e1830", (180, 110, 255),
        sky=dict(top="#020108", mid="#120a2a", horizon="#2a1450", bottom="#000000", sun=(0.3, 0.55),
                 sun_color="#c9a6ff", sun_size=0.02, stars=1400, nebula=True, glow_color="#7a3cff"),
        fog="#140a26", fog_density=0.25, sun_color="#d8c8ff", sun_brightness=1.3,
        sun_rotation=(-55.0, 30.0, 0.0), probe_exposure=1.4, ambient="void", rock="#2b2735",
        rock_emissive="#05000c", glow="#b46bff", glow_strength=3.5, orbit="#3b3548", orbit_speed=2.0),
    Location3D(
        "frozen", "Frozen Peak",
        "The roof of the world, where the aurora dances over eternal ice.",
        "#eef4fb", "#5f7a96", "#3c4c60", (120, 220, 255),
        sky=dict(top="#03122a", mid="#123a66", horizon="#8fb7d8", bottom="#d8e6f2", sun=(0.7, 0.47),
                 sun_color="#fff6e0", sun_size=0.03, stars=500, aurora=True, glow_color="#5cffc4"),
        fog="#9db8d4", fog_density=0.45, sun_color="#fff3e2", sun_brightness=1.5,
        sun_rotation=(-30.0, 60.0, 0.0), probe_exposure=1.0, ambient="snow", rock="#6a7684",
        accent="#e9f1fa", glow="#8fe3ff", glow_strength=2.0),
    Location3D(
        "sky", "Sky Temple",
        "An ancient marble sanctum floating above a golden sea of clouds.",
        "#f5efe2", "#4c6a98", "#c9bfa8", (255, 210, 120),
        sky=dict(top="#2a4f8f", mid="#e08a50", horizon="#ffd28a", bottom="#fff0d0", sun=(0.5, 0.49),
                 sun_color="#fff2c0", sun_size=0.06, stars=0, clouds=True, glow_color="#ffb050"),
        fog="#f2c890", fog_density=0.16, sun_color="#ffe2b0", sun_brightness=1.8,
        sun_rotation=(-22.0, 0.0, 0.0), probe_exposure=1.1, ambient="clouds", rock="#6e5f52",
        accent="#efe6d6", glow="#ffb347", glow_strength=4.0, orbit="#fff3e2", orbit_opacity=0.92,
        orbit_speed=0.6),
]}

DEFAULT_LOCATION = "volcano"


# 3D army styles: colours for each material part.
ARMIES_3D = {
    "light_shadow": {
        "name": "Kingdom of Light vs Shadow Legion",
        "white": {"army": "Kingdom of Light", "body": "#efe6d2", "bodyMetal": 0.0, "bodyRough": 0.32,
                  "metal": "#e0ac3e", "cloth": "#2a4fb0", "glow": "#7fdcff", "dark": "#2a2230"},
        "black": {"army": "Shadow Legion", "body": "#2a2531", "bodyMetal": 0.35, "bodyRough": 0.22,
                  "metal": "#b4643c", "cloth": "#8a1224", "glow": "#ff3b5c", "dark": "#0e0a10"},
    },
    "gold_iron": {
        "name": "Golden Crown vs Iron Horde",
        "white": {"army": "Golden Crown", "body": "#f3d27a", "bodyMetal": 1.0, "bodyRough": 0.25,
                  "metal": "#fff1c4", "cloth": "#7a1424", "glow": "#ffe08a", "dark": "#3a2410"},
        "black": {"army": "Iron Horde", "body": "#4c5058", "bodyMetal": 1.0, "bodyRough": 0.35,
                  "metal": "#1e2024", "cloth": "#1c3a2a", "glow": "#5cff8a", "dark": "#0a0a0c"},
    },
    "frost_flame": {
        "name": "Frost Legion vs Ember Horde",
        "white": {"army": "Frost Legion", "body": "#dff2ff", "bodyMetal": 0.1, "bodyRough": 0.15,
                  "metal": "#9fc8e8", "cloth": "#2a6aa8", "glow": "#9ff0ff", "dark": "#1a3048"},
        "black": {"army": "Ember Horde", "body": "#3a1410", "bodyMetal": 0.2, "bodyRough": 0.4,
                  "metal": "#d08a3a", "cloth": "#c2410c", "glow": "#ff8a1a", "dark": "#120604"},
    },
}

DEFAULT_ARMY = "light_shadow"
