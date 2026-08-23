"""Dev-time stand-in for ``PluginCoordinator``.

Six of the plugins in the FreeSDN registry import this from ``freesdn_sdk``, so
until now the published SDK could not type-check the shipping examples it tells
authors to copy.

Like everything else in this package, the body is a stand-in: inside FreeSDN,
``app.plugins.sdk.PluginCoordinator`` is substituted in ``sys.modules`` before a
plugin is executed. What has to be right here is the NAME and the SIGNATURE.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from freesdn_sdk.context import PluginContext

__all__ = ["PluginCoordinator"]


class PluginCoordinator:
    """One fetch, shared by everything in a plugin that needs it.

    Modelled on Home Assistant's ``DataUpdateCoordinator``. Without it every
    consumer polls independently, which in FreeSDN meant four shipped sync
    plugins each hand-rolling the same retry loop and the same
    transient-vs-permanent classification.

    Usage::

        self.coordinator = PluginCoordinator(
            self.ctx, "netbox", self._fetch, update_interval=300.0
        )
        devices = await self.coordinator.async_get()
    """

    def __init__(
        self,
        ctx: PluginContext,
        name: str,
        update_method: Callable[[], Awaitable[Any]],
        *,
        update_interval: float = 300.0,
    ) -> None:
        self._ctx = ctx
        self.name = name
        self._update = update_method
        self.update_interval = float(update_interval)

        self.data: Any = None
        self.last_update_success: bool = False
        self.last_exception: BaseException | None = None
        self.last_updated: float | None = None
        self.consecutive_failures: int = 0

    @property
    def age(self) -> float | None:
        """Seconds since the last SUCCESSFUL fetch, or None if there has been none."""
        return None

    @property
    def is_stale(self) -> bool:
        """Whether the cached data is older than ``update_interval``."""
        return True

    def snapshot(self) -> dict[str, Any]:
        """Coordinator state, for a diagnostics endpoint."""
        return {
            "name": self.name,
            "last_update_success": self.last_update_success,
            "consecutive_failures": self.consecutive_failures,
        }

    async def async_get(self) -> Any:
        """Cached data, refreshing first if it is stale."""
        raise NotImplementedError("PluginCoordinator is provided by the FreeSDN runtime")

    async def async_refresh(self, *, force: bool = False) -> bool:
        """Fetch now. Returns whether the fetch succeeded."""
        raise NotImplementedError("PluginCoordinator is provided by the FreeSDN runtime")
