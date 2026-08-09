"""
params_loader.py
================
Shared parameter loader for all quote-form automation scripts.

Every script reads its fill values from an external JSON file (per person), so a
different user can apply their own parameters without editing code. The default
input file is `quote_params.json` in this directory; override with `--input <file>`.

The companion `field_registry.json` documents every field as FIXED (a bounded set
of options) vs VARIABLE (free text), so we never guess option values. This loader
can validate that FIXED fields receive a value from the registry's options.

Usage (in a script):
    from params_loader import load_params, get_param, validate_fixed
    params = load_params("quote_params.json")   # or the --input path
    email  = get_param(params, "person.email")
"""

import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_PARAMS = os.path.join(BASE_DIR, "quote_params.json")
DEFAULT_REGISTRY = os.path.join(BASE_DIR, "field_registry.json")


def load_params(path: str | None = None) -> dict:
    """Load the per-person parameter JSON. Missing file -> empty dict."""
    p = path or DEFAULT_PARAMS
    if not os.path.exists(p):
        print(f"[params_loader] WARNING: params file not found: {p}", flush=True)
        return {}
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def load_registry(path: str | None = None) -> dict:
    """Load the field registry (fixed/variable documentation + options)."""
    p = path or DEFAULT_REGISTRY
    if not os.path.exists(p):
        return {}
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def get_param(params: dict, dotted: str, default=None):
    """Resolve a 'section.key' path in the params dict, e.g. 'person.email'."""
    cur = params
    for part in dotted.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return default
    return cur


def validate_fixed(params: dict, registry: dict, form_key: str,
                   field_name: str, value) -> bool:
    """Check that a FIXED field's value is one of the registry's options.

    Returns True if OK (or the field isn't registered as fixed); prints a warning
    and returns False if the value is not in the allowed options.
    """
    form = registry.get("forms", {}).get(form_key)
    if not form:
        return True
    spec = form.get("fields", {}).get(field_name)
    if not spec or spec.get("type") != "fixed":
        return True
    options = spec.get("options", [])
    if value not in options:
        print(
            f"[params_loader] WARNING: {form_key}.{field_name}={value!r} not in "
            f"fixed options {options}",
            flush=True,
        )
        return False
    return True


def add_input_arg(parser):
    """Add a standard --input <params.json> argument to an argparse parser."""
    parser.add_argument(
        "--input",
        default=None,
        help="Path to a per-person parameters JSON (default: quote_params.json).",
    )
    return parser
