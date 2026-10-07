"""Check translated documentation pairs, local links, and removed APIs."""

from pathlib import Path
import re
import sys


_LINK = re.compile(r"\]\(([^)]+)\)")
_REMOVED_API = re.compile(
    r"\b(?:getTouch|calibrateTouch|TFT_eSPI_Button|initDMA|pushImageDMA|pushPixelsDMA|dmaWait)\b"
)


def check(root: Path) -> list[str]:
    root = Path(root)
    errors = []
    en_dir = root / "docs/en"
    pt_dir = root / "docs/pt-BR"
    en_files = sorted(en_dir.glob("*.md"))
    pt_files = sorted(pt_dir.glob("*.md"))
    en_names = {path.name for path in en_files}
    pt_names = {path.name for path in pt_files}

    if not (root / "README.pt-BR.md").is_file():
        errors.append("README.pt-BR.md: missing")
    for path in en_files:
        if path.name not in pt_names:
            errors.append(f"{path.relative_to(root)}: missing pt-BR pair")
    for path in pt_files:
        if path.name not in en_names:
            errors.append(f"{path.relative_to(root)}: missing English pair")

    contributing_en = root / "CONTRIBUTING.md"
    contributing_pt = root / "CONTRIBUTING.pt-BR.md"
    if contributing_en.is_file() and not contributing_pt.is_file():
        errors.append("CONTRIBUTING.pt-BR.md: missing pair")
    if contributing_pt.is_file() and not contributing_en.is_file():
        errors.append("CONTRIBUTING.md: missing pair")

    documents = [
        root / "README.md",
        root / "README.pt-BR.md",
        contributing_en,
        contributing_pt,
        *en_files,
        *pt_files,
    ]
    for path in documents:
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        text = path.read_text(encoding="utf-8")
        if path.name != "limitations.md":
            match = _REMOVED_API.search(text)
            if match:
                errors.append(f"{relative}: removed API {match.group(0)}")

        for match in _LINK.finditer(text):
            target = match.group(1).strip().split("#", 1)[0]
            if not target or target.startswith(("http://", "https://", "mailto:")):
                continue
            if not (path.parent / target).exists():
                errors.append(f"{relative}: broken link {match.group(1).strip()}")

    return errors


def main() -> int:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent
    errors = check(root)
    if errors:
        print("\n".join(errors))
        return 1
    print("docs-check OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
