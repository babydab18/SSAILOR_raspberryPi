"""Build a source-only Pi package, without credentials, logs, archives, or binaries."""
from pathlib import Path
import hashlib
import tarfile

ROOT = Path(__file__).resolve().parents[1]
FILES = ["Cargo.toml", "Cargo.lock", "pyproject.toml", "uv.lock", ".python-version", ".gitignore", "LICENSE", "README.md", "examples/plot_gps_log.py"]
DIRECTORIES = ["src", "tools", "docs", "scripts", "tests"]

def package(root=ROOT):
    root = Path(root)
    paths = [root / name for name in FILES]
    for directory in DIRECTORIES:
        paths.extend(path for path in (root / directory).rglob("*")
                     if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc")
    for path in paths:
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"Missing file or unexpected symlink: {path}")
        path.resolve().relative_to(root.resolve())
    output = root / "dist" / "ssailor-gps-pi.tar.gz"
    output.parent.mkdir(exist_ok=True)
    with tarfile.open(output, "w:gz") as archive:
        for path in sorted(paths):
            archive.add(path, arcname="SSAILOR_gps/" + path.relative_to(root).as_posix(), recursive=False)
    checksum = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_name(output.name + ".sha256").write_text(f"{checksum}  {output.name}\n", encoding="ascii")
    return output, checksum

if __name__ == "__main__":
    output, checksum = package()
    print(output)
    print(f"SHA256: {checksum}")
