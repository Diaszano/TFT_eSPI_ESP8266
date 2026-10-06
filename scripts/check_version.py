import json
import pathlib
import re
import sys


def versions(root: pathlib.Path) -> dict[str, str]:
    root = pathlib.Path(root)
    result = {"library.json": json.loads((root / "library.json").read_text())["version"]}
    properties = (root / "library.properties").read_text()
    match = re.search(r"^version=(.+)$", properties, re.MULTILINE)
    if match is None:
        raise ValueError("library.properties: missing version")
    result["library.properties"] = match.group(1)
    manifest = root / ".release-please-manifest.json"
    if manifest.exists():
        result[manifest.name] = json.loads(manifest.read_text())["."]
    return result


def main() -> int:
    root = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else pathlib.Path(__file__).resolve().parent.parent
    found = versions(root)
    if len(set(found.values())) != 1:
        for path, version in found.items():
            print(f"{path}: {version}")
        return 1
    print(f"version OK {next(iter(found.values()))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
