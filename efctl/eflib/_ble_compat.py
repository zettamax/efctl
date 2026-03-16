"""Compatibility shim for bleak_retry_connector.

On Linux, uses the real bleak_retry_connector (retry logic, adapter management).
On macOS/Windows (or if not installed), falls back to plain BleakClient.connect().
"""

try:
    from bleak_retry_connector import (
        MAX_CONNECT_ATTEMPTS,
        BleakNotFoundError,
        establish_connection,
    )
except ImportError:
    from bleak import BleakClient
    from bleak.exc import BleakError

    MAX_CONNECT_ATTEMPTS = 4

    class BleakNotFoundError(BleakError):
        pass

    async def establish_connection(
        client_class, device, name,
        disconnected_callback=None, max_attempts=4,
        cached_services=None, ble_device_callback=None,
        use_services_cache=True, pair=False, **kwargs
    ):
        client = client_class(
            device,
            disconnected_callback=disconnected_callback,
            **kwargs,
        )
        await client.connect()
        return client
