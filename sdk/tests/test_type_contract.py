"""Port return types stay resolvable in classes exposing a list() method."""

from typing import Any, get_type_hints

import pytest

from freesdn_sdk.context import DeviceSDK
from freesdn_sdk.testing import MockDeviceSDK


@pytest.mark.parametrize("interface", [DeviceSDK, MockDeviceSDK])
def test_ports_return_type_resolves_with_class_namespace(interface):
    hints = get_type_hints(interface.get_ports, localns=vars(interface))
    assert hints["return"] == list[dict[str, Any]]
