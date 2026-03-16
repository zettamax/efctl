"""Entry point for efctl: python -m efctl"""

import argparse
import asyncio
import logging
import os
import sys

from .config import load_config, save_config


def main():
    parser = argparse.ArgumentParser(
        prog="efctl",
        description="EcoFlow BLE CLI monitor and control tool",
    )
    parser.add_argument(
        "--user-id", "-u",
        help="EcoFlow User ID (saved to config on first use)",
    )
    parser.add_argument(
        "--scan", "-s",
        action="store_true",
        help="Quick scan: print found devices and exit",
    )
    parser.add_argument(
        "--scan-duration",
        type=float,
        default=5.0,
        help="BLE scan duration in seconds (default: 5)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )
    parser.add_argument(
        "--log-file",
        default=None,
        help="Log to file instead of stderr",
    )

    args = parser.parse_args()

    # Setup logging
    log_level = logging.DEBUG if args.debug else logging.WARNING
    log_kwargs = {"level": log_level, "format": "%(asctime)s %(name)s %(levelname)s: %(message)s"}
    if args.log_file:
        log_kwargs["filename"] = args.log_file
    else:
        # In TUI mode, suppress logging to stderr (would mess up display)
        if not args.scan:
            log_kwargs["filename"] = os.devnull
    logging.basicConfig(**log_kwargs)

    # Load config
    config = load_config()

    # Handle --user-id
    if args.user_id:
        config.user_id = args.user_id
        save_config(config)
        print(f"User ID saved: {args.user_id}")

    # Prompt for user_id if not set
    if not config.user_id and not args.scan:
        print("=" * 50)
        print("  efctl - EcoFlow BLE CLI")
        print("=" * 50)
        print()
        print("User ID is required for device authentication.")
        print("You can find it in the EcoFlow app or at:")
        print("  https://gnox.github.io/user_id")
        print()
        uid = input("Enter your EcoFlow User ID: ").strip()
        if not uid:
            print("Error: User ID is required.")
            sys.exit(1)
        config.user_id = uid
        save_config(config)
        print(f"Saved to config. You won't need to enter this again.")
        print()

    # Quick scan mode
    if args.scan:
        asyncio.run(_quick_scan(args.scan_duration))
        return

    # TUI mode
    from .app import run_app_textual as run_app
    run_app(config)


async def _quick_scan(duration: float):
    """Non-interactive scan: print devices and exit."""
    from .ble import scan_devices

    print(f"Scanning for EcoFlow devices ({duration}s)...")
    print()

    def on_found(sd):
        print(f"  ● {sd.display}")

    try:
        results = await scan_devices(duration=duration, callback=on_found)
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    if not results:
        print("  No EcoFlow devices found.")
    else:
        print(f"\n{len(results)} device(s) found.")


if __name__ == "__main__":
    main()
