"""Create new standalone capture source files for pasting into platform editors.

This does not install, load, start or connect either trading platform.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


def package_sources(output_dir: Path) -> dict:
    root = Path(__file__).resolve().parent
    common = root / "market_data/BoundedCaptureWriter.cs"
    adapters = (
        root / "ninjatrader/AiTraderSixEDataCapture.cs",
        root / "ctrader/AiTraderEurUsdCapture.cs",
    )
    if output_dir.exists():
        raise ValueError("Refusing to overwrite a source package directory")
    products, sources = {}, {}
    for adapter in adapters:
        imports, bodies = set(), []
        for path in (common, adapter):
            raw = path.read_bytes()
            sources[path.relative_to(root).as_posix()] = hashlib.sha256(raw).hexdigest()
            source = raw.decode("utf-8").replace("\r\n", "\n")
            imports.update(re.findall(r"^using [^\n]+;\n", source, re.MULTILINE))
            bodies.append(re.sub(r"^using [^\n]+;\n", "", source, flags=re.MULTILINE))
        products[adapter.name] = (
            "// Generated capture-only source. Disabled by default.\n"
            + "".join(sorted(imports))
            + "\n"
            + "\n".join(bodies)
        ).encode()
    manifest = {
        "artifact_type": "platform_capture_source_package_v1",
        "source_sha256": sources,
        "files": {name: hashlib.sha256(raw).hexdigest() for name, raw in products.items()},
        "installed": False,
        "started": False,
        "trading_enabled": False,
    }
    output_dir.mkdir(parents=True, exist_ok=False)
    for name, raw in products.items():
        with (output_dir / name).open("xb") as target:
            target.write(raw)
    with (output_dir / "manifest.json").open("x", encoding="utf-8") as target:
        json.dump(manifest, target, indent=2, sort_keys=True)
        target.write("\n")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    print(json.dumps(package_sources(parser.parse_args().output_dir)))
