"""YAML configuration loading and Pydantic validation helpers."""

from __future__ import annotations

from pathlib import Path
from typing import TypeVar

import yaml
from pydantic import BaseModel

from har.config.models import AppConfig, ProtocolConfig

ModelT = TypeVar("ModelT", bound=BaseModel)


def load_yaml(path: str | Path, model: type[ModelT]) -> ModelT:
    """Load and validate one YAML configuration file."""

    with Path(path).open("r", encoding="utf-8") as handle:
        contents = yaml.safe_load(handle) or {}
    return model.model_validate(contents)


def load_protocol(path: str | Path) -> ProtocolConfig:
    """Load the ordered experiment protocol."""

    return load_yaml(path, ProtocolConfig)


def load_app(path: str | Path) -> AppConfig:
    """Load top-level application settings."""

    return load_yaml(path, AppConfig)
