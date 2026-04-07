"""Channel deserialisation registry.

To add a new channel type, import its class and add it to _REGISTRY.
No other file needs to change.
"""
from elements.channels.i_channel import IChannel
from elements.channels.l_channel import LChannel
from elements.channels.t_channel import TChannel

from elements.channels.base import Channel

_REGISTRY: dict[str, type[Channel]] = {
    "I": IChannel,
    "L": LChannel,
    "T": TChannel,
}


def channel_from_dict(d: dict) -> Channel:
    """Deserialise a channel dict to the appropriate Channel subclass."""
    type_key = d.get("type", "I")
    cls = _REGISTRY.get(type_key)
    if cls is None:
        raise ValueError(f"Unknown channel type: {type_key!r}")
    return cls.from_dict(d)
