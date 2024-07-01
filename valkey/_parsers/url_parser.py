from types import MappingProxyType
from typing import Callable, Mapping, Optional
from urllib.parse import ParseResult, parse_qs, unquote, urlparse

from valkey.asyncio.connection import ConnectKwargs
from valkey.asyncio.connection import SSLConnection as SSLConnectionAsync
from valkey.asyncio.connection import (
    UnixDomainSocketConnection as UnixDomainSocketConnectionAsync,
)
from valkey.connection import SSLConnection, UnixDomainSocketConnection


def to_bool(value) -> Optional[bool]:
    if value is None or value == "":
        return None
    if isinstance(value, str) and value.upper() in FALSE_STRINGS:
        return False
    return bool(value)


FALSE_STRINGS = ("0", "F", "FALSE", "N", "NO")

URL_QUERY_ARGUMENT_PARSERS: Mapping[str, Callable[..., object]] = MappingProxyType(
    {
        "db": int,
        "socket_timeout": float,
        "socket_connect_timeout": float,
        "socket_keepalive": to_bool,
        "retry_on_timeout": to_bool,
        "max_connections": int,
        "health_check_interval": int,
        "ssl_check_hostname": to_bool,
        "timeout": float,
    }
)


def parse_url(url: str, async_connection: bool):
    url_prefixes = ["valkey://", "valkeys://", "unix://", "redis://", "rediss://"]
    supported_schemes = ["valkey", "valkeys", "redis", "rediss"]

    if not any(url.startswith(prefix) for prefix in url_prefixes):
        raise ValueError(
            f"Valkey URL must specify one of the following schemes {url_prefixes}"
        )

    parsed: ParseResult = urlparse(url)
    kwargs: ConnectKwargs = {}

    for name, value_list in parse_qs(parsed.query).items():
        if value_list and len(value_list) > 0:
            value = unquote(value_list[0])
            parser = URL_QUERY_ARGUMENT_PARSERS.get(name)
            if parser:
                try:
                    kwargs[name] = parser(value)
                except (TypeError, ValueError):
                    raise ValueError(f"Invalid value for `{name}` in connection URL.")
            else:
                kwargs[name] = value

    if parsed.username:
        kwargs["username"] = unquote(parsed.username)
    if parsed.password:
        kwargs["password"] = unquote(parsed.password)

    # We only support valkey://, valkeys://, redis://, rediss://, and unix:// schemes.
    if parsed.scheme == "unix":
        if parsed.path:
            kwargs["path"] = unquote(parsed.path)
        kwargs["connection_class"] = (
            UnixDomainSocketConnectionAsync
            if async_connection
            else UnixDomainSocketConnection
        )

    elif parsed.scheme in supported_schemes:
        if parsed.hostname:
            kwargs["host"] = unquote(parsed.hostname)
        if parsed.port:
            kwargs["port"] = int(parsed.port)

        # If there's a path argument, use it as the db argument if a
        # querystring value wasn't specified
        if parsed.path and "db" not in kwargs:
            try:
                kwargs["db"] = int(unquote(parsed.path).replace("/", ""))
            except (AttributeError, ValueError):
                pass

        if parsed.scheme in ("valkeys", "rediss"):
            kwargs["connection_class"] = (
                SSLConnectionAsync if async_connection else SSLConnection
            )
    else:
        raise ValueError(
            f"Valkey URL must specify one of the following schemes ({url_prefixes})"
        )

    return kwargs
