"""Fixtures for the EnBW charge stations tests."""

from pathlib import Path

import custom_components
import pytest

pytest_plugins = "pytest_homeassistant_custom_component"

# pytest-homeassistant-custom-component ships its own `custom_components`
# package for Home Assistant's own test integrations. Being a regular package,
# it shadows the namespace package in this repo, so the loader never sees our
# integration. Adding our directory to its search path makes both visible.
_REPO_COMPONENTS = str(Path(__file__).parent.parent / "custom_components")
if _REPO_COMPONENTS not in custom_components.__path__:
    custom_components.__path__.append(_REPO_COMPONENTS)


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Make the custom integration loadable in every test."""
    return
