from pathlib import Path
import json

_DEFAULTS = {"max_display_chars": 500, "max_shell_lines": 40}


def get_config() -> dict:
    cfg_path = Path.home() / ".songbird" / "config.json"
    if cfg_path.exists():
        try:
            with cfg_path.open() as fh:
                data = json.load(fh)
                return {**_DEFAULTS, **data}
        except Exception:
            pass
    return _DEFAULTS
