from __future__ import annotations

import yaml
from pathlib import Path

from native.core.models import FilterConfig


def profile_to_config(profile: dict[str, object]) -> FilterConfig:
    config = FilterConfig()
    
    if "invertColor" in profile:
        config.invertColor = bool(profile["invertColor"])
    if "dilate" in profile:
        config.dilate = bool(profile["dilate"])
    if "blurImageRadius" in profile:
        config.blurImageRadius = int(profile["blurImageRadius"])
    
    if "binarizeThreshold" in profile:
        config.binarizeThreshold = int(profile["binarizeThreshold"])
    else:
        config.binarizeThreshold = None
        
    if "name" in profile:
        config.activeProfile = str(profile["name"])
        
    return config


def config_to_profile(config: FilterConfig) -> dict[str, object]:
    profile: dict[str, object] = {
        "invertColor": config.invertColor,
        "dilate": config.dilate,
        "blurImageRadius": config.blurImageRadius,
    }
    if config.is_binarize_enabled:
        profile["binarizeThreshold"] = config.binarizeThreshold
    return profile


def load_profiles(profile_dir: Path) -> list[dict[str, object]]:
    profiles: list[dict[str, object]] = []
    if not profile_dir.exists():
        return profiles
        
    for file_path in profile_dir.glob("*.yaml"):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                yam_file = yaml.safe_load(f)
                if not isinstance(yam_file, dict):
                    yam_file = {}
                yam_file["name"] = file_path.stem
                profiles.append(yam_file)
        except yaml.YAMLError:
            continue
             
    return profiles


def import_profile(path: Path) -> FilterConfig:
    with open(path, "r", encoding="utf-8") as f:
        yam_file = yaml.safe_load(f)
        if not isinstance(yam_file, dict):
            yam_file = {}
        yam_file["name"] = path.stem
        return profile_to_config(yam_file)


def export_profile(path: Path, config: FilterConfig) -> None:
    profile = config_to_profile(config)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(profile, f, sort_keys=False, default_flow_style=False)
