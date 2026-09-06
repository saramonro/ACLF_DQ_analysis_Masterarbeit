"""Translator between config.yaml and the check scripts.

This module loads the project configuration once (from config.yaml or a file
pointed to by the SARA_CONFIG environment variable) and exposes the values the
scripts need as plain Python constants, plus helpers for the runner to decide
which scripts are enabled.

Import it from anywhere in the project with ``import config`` (or
``from config import NAMESPACE, REGISTRY_NAME, ...``).
"""

import os
from pathlib import Path


class ConfigError(Exception):
    """Raised when the configuration file is missing or invalid."""


PROJECT_ROOT = Path(__file__).resolve().parent

# Allow overriding the config location via environment variable so alternate
# configs can be used without editing code (e.g. SARA_CONFIG=other.yaml).
_env_config = os.environ.get("SARA_CONFIG")
CONFIG_PATH = (
    Path(_env_config).expanduser().resolve()
    if _env_config
    else PROJECT_ROOT / "config.yaml"
)


def _load_yaml(path):
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - depends on environment
        raise ConfigError(
            "PyYAML is required to read the configuration file. "
            "Install it with 'pip install pyyaml' (or 'pip install -r requirements.txt')."
        ) from exc

    if not path.exists():
        raise ConfigError(f"Configuration file not found: {path}")

    with open(path, "r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)

    if not isinstance(data, dict):
        raise ConfigError(
            f"Configuration file {path} must contain a top-level mapping."
        )
    return data


def _require(mapping, section, key):
    if section not in mapping or not isinstance(mapping[section], dict):
        raise ConfigError(
            f"Missing or invalid '{section}' section in {CONFIG_PATH}."
        )
    if key not in mapping[section] or mapping[section][key] in (None, ""):
        raise ConfigError(
            f"Missing required field '{section}.{key}' in {CONFIG_PATH}."
        )
    return mapping[section][key]


_config = _load_yaml(CONFIG_PATH)

# Registry settings (the THIS-marked values).
NAMESPACE = str(_require(_config, "registry", "namespace"))
REGISTRY_NAME = str(_require(_config, "registry", "name"))
# Date of Birth Source_ID -> if present as MDAT, for Temporal Plausibility checks
DATE_OF_BIRTH_SOURCE_ID = str(_require(_config, "registry", "dob_source_id"))

# Full registry base URL, e.g. "https://test.aclf.register.imi-frankfurt.de".
# Trailing slashes are stripped so callers can safely append paths.
URL = str(_require(_config, "registry", "url")).rstrip("/")
# MDR api base URL. Normalized to end with a single "/" so callers can
# concatenate paths directly (e.g. f"{MDR_BASE}namespaces/...").
MDR_BASE = str(_require(_config, "registry", "mdr_base")).rstrip("/") + "/"


# Raw export path. Relative paths are resolved against the project root.
_raw_export = str(_require(_config, "paths", "raw_export"))
_raw_export_path = Path(_raw_export).expanduser()
if not _raw_export_path.is_absolute():
    _raw_export_path = (PROJECT_ROOT / _raw_export_path).resolve()
RAW_EXPORT_PATH = _raw_export_path

# Script enable/disable map.
_scripts = _config.get("scripts", {})
if not isinstance(_scripts, dict):
    raise ConfigError(f"'scripts' section in {CONFIG_PATH} must be a mapping.")
SCRIPTS = {str(name): bool(enabled) for name, enabled in _scripts.items()}


def is_enabled(script_id):
    """Return True if the given script id is enabled in the config.

    Unknown script ids default to enabled so a script that was added to the
    project but not yet listed in config.yaml still runs.
    """
    return SCRIPTS.get(str(script_id), True)
