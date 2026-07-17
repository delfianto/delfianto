from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tomllib
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

_THIS = Path(__file__).resolve()
AGENTS_DIR = _THIS.parents[3]

sys.path.insert(0, str(AGENTS_DIR / "scripts"))
from ghrepo import ProjectType, detect_project_type

VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")


class ReleaseError(RuntimeError):
    pass


def bump(current_version: str, kind: str) -> str:
    if VERSION_RE.match(kind):
        return kind
    if not VERSION_RE.match(current_version):
        raise ReleaseError(
            f"cannot auto-bump non-semver version {current_version!r}; pass an explicit version"
        )
    major, minor, patch = (int(part) for part in current_version.split("."))
    if kind == "major":
        return f"{major + 1}.0.0"
    if kind == "minor":
        return f"{major}.{minor + 1}.0"
    if kind == "patch":
        return f"{major}.{minor}.{patch + 1}"
    raise ReleaseError(
        f"unknown bump kind {kind!r}, expected major/minor/patch or an explicit x.y.z"
    )


def _section_span(text: str, section: str) -> tuple[int, int] | None:
    pattern = re.compile(rf"(?ms)^\[{re.escape(section)}\].*?(?=^\[|\Z)")
    match = pattern.search(text)
    return (match.start(), match.end()) if match else None


def _patch_version_in_section(text: str, section: str, new_version: str) -> str:
    span = _section_span(text, section)
    if span is None:
        raise ReleaseError(f"section [{section}] not found")
    start, end = span
    body = text[start:end]
    new_body, n = re.subn(
        r'(?m)^(version\s*=\s*")[^"]+(")', rf"\g<1>{new_version}\g<2>", body, count=1
    )
    if n != 1:
        raise ReleaseError(f"no version field found in [{section}]")
    return text[:start] + new_body + text[end:]


@dataclass
class FileEdit:
    path: Path
    new_content: str
    description: str


@dataclass
class Plan:
    project_type: ProjectType
    current_version: str
    new_version: str
    tag: str
    edits: list[FileEdit] = field(default_factory=list)
    build_command: list[str] | None = None
    release_assets: list[Path] = field(default_factory=list)
    optional_release_assets: list[Path] = field(default_factory=list)
    zip_source_dir: Path | None = None


def _cargo_plan(path: Path, new_version_kind: str) -> Plan:
    cargo_toml = path / "Cargo.toml"
    data = tomllib.loads(cargo_toml.read_text())
    current = data.get("package", {}).get("version")
    if not isinstance(current, str):
        raise ReleaseError("Cargo.toml has no [package].version")
    new_version = bump(current, new_version_kind)
    new_text = _patch_version_in_section(cargo_toml.read_text(), "package", new_version)
    return Plan(
        project_type="rust",
        current_version=current,
        new_version=new_version,
        tag=f"v{new_version}",
        edits=[FileEdit(cargo_toml, new_text, "bump [package].version")],
    )


def _python_plan(path: Path, new_version_kind: str) -> Plan:
    pyproject = path / "pyproject.toml"
    text = pyproject.read_text()
    data = tomllib.loads(text)
    section = "project" if "version" in data.get("project", {}) else "tool.poetry"
    current = data.get("project", {}).get("version") or data.get("tool", {}).get("poetry", {}).get(
        "version"
    )
    if not isinstance(current, str):
        raise ReleaseError(
            "no static version found under [project] or [tool.poetry] "
            "(dynamically-sourced versions aren't supported by this script)"
        )
    new_version = bump(current, new_version_kind)
    new_text = _patch_version_in_section(text, section, new_version)
    return Plan(
        project_type="python",
        current_version=current,
        new_version=new_version,
        tag=f"v{new_version}",
        edits=[FileEdit(pyproject, new_text, f"bump [{section}].version")],
    )


def _sync_package_json(path: Path, new_version: str, edits: list[FileEdit]) -> None:
    package_json = path / "package.json"
    if not package_json.is_file():
        return
    data = json.loads(package_json.read_text())
    data["version"] = new_version
    edits.append(
        FileEdit(package_json, json.dumps(data, indent=2) + "\n", "sync package.json version")
    )


def _obsidian_plan(path: Path, new_version_kind: str) -> Plan:
    manifest_path = path / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    current = manifest["version"]
    new_version = bump(current, new_version_kind)
    manifest["version"] = new_version
    edits = [
        FileEdit(manifest_path, json.dumps(manifest, indent=2) + "\n", "bump manifest.json version")
    ]

    versions_path = path / "versions.json"
    if versions_path.is_file():
        versions = json.loads(versions_path.read_text())
        versions[new_version] = manifest.get("minAppVersion", "")
        edits.append(
            FileEdit(
                versions_path,
                json.dumps(versions, indent=2) + "\n",
                "add versions.json entry",
            )
        )

    _sync_package_json(path, new_version, edits)

    return Plan(
        project_type="obsidian-plugin",
        current_version=current,
        new_version=new_version,
        tag=new_version,
        edits=edits,
        build_command=["npm", "run", "build"],
        release_assets=[path / "main.js", manifest_path],
        optional_release_assets=[path / "styles.css"],
    )


def _browser_extension_plan(path: Path, new_version_kind: str) -> Plan:
    manifest_path = path / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    current = manifest["version"]
    new_version = bump(current, new_version_kind)
    manifest["version"] = new_version
    edits = [
        FileEdit(manifest_path, json.dumps(manifest, indent=2) + "\n", "bump manifest.json version")
    ]
    _sync_package_json(path, new_version, edits)

    zip_source = None
    for candidate in ("dist", "build", "extension"):
        if (path / candidate / "manifest.json").is_file():
            zip_source = path / candidate
            break

    return Plan(
        project_type="browser-extension",
        current_version=current,
        new_version=new_version,
        tag=f"v{new_version}",
        edits=edits,
        build_command=["npm", "run", "build"],
        zip_source_dir=zip_source,
    )


def build_plan(path: Path, new_version_kind: str) -> Plan:
    project_type = detect_project_type(path)
    if project_type == "rust":
        return _cargo_plan(path, new_version_kind)
    if project_type == "python":
        return _python_plan(path, new_version_kind)
    if project_type == "obsidian-plugin":
        return _obsidian_plan(path, new_version_kind)
    if project_type == "browser-extension":
        return _browser_extension_plan(path, new_version_kind)
    raise ReleaseError(
        f"couldn't detect a known project type at {path} "
        "(looked for Cargo.toml, pyproject.toml, manifest.json)"
    )


def print_plan(plan: Plan, path: Path) -> None:
    print(f"Project type : {plan.project_type}")
    print(f"Path         : {path}")
    print(f"Version      : {plan.current_version} -> {plan.new_version}")
    print(f"Tag          : {plan.tag}")
    print("Edits:")
    for edit in plan.edits:
        print(f"  - {edit.description}: {edit.path.relative_to(path)}")
    if plan.build_command:
        print(f"Build        : {' '.join(plan.build_command)}")
    if plan.release_assets:
        print("Release assets:")
        for asset in plan.release_assets:
            print(f"  - {asset.relative_to(path)}")
    for asset in plan.optional_release_assets:
        print(f"  - {asset.relative_to(path)} (included only if present after build)")
    if plan.zip_source_dir:
        print(f"Zip source   : {plan.zip_source_dir.relative_to(path)}")


def git(args: list[str], *, cwd: Path, execute: bool) -> None:
    print(f"$ git {' '.join(args)}")
    if execute:
        subprocess.run(["git", *args], cwd=cwd, check=True)


def working_tree_clean(path: Path) -> bool:
    result = subprocess.run(
        ["git", "status", "--porcelain"], cwd=path, capture_output=True, text=True, check=True
    )
    return result.stdout.strip() == ""


def apply_plan(plan: Plan, path: Path, *, execute: bool, push: bool, allow_dirty: bool) -> None:
    if not allow_dirty and not working_tree_clean(path):
        raise ReleaseError("working tree is not clean; commit/stash first or pass --allow-dirty")

    for edit in plan.edits:
        print(f"writing {edit.path.relative_to(path)} ({edit.description})")
        if execute:
            edit.path.write_text(edit.new_content)

    if plan.build_command:
        print(f"$ {' '.join(plan.build_command)}  (in {path})")
        if execute:
            subprocess.run(plan.build_command, cwd=path, check=True)

    if execute:
        for asset in plan.release_assets:
            if not asset.is_file():
                raise ReleaseError(f"expected release asset missing after build: {asset}")

    zip_asset: Path | None = None
    if plan.zip_source_dir is not None:
        zip_asset = path / f"{plan.project_type}-{plan.new_version}.zip"
        print(f"zipping {plan.zip_source_dir.relative_to(path)} -> {zip_asset.name}")
        if execute:
            with zipfile.ZipFile(zip_asset, "w", zipfile.ZIP_DEFLATED) as zf:
                for file_path in plan.zip_source_dir.rglob("*"):
                    if file_path.is_file():
                        zf.write(file_path, file_path.relative_to(plan.zip_source_dir))

    changed_files = [str(edit.path.relative_to(path)) for edit in plan.edits]
    git(["add", *changed_files], cwd=path, execute=execute)
    git(["commit", "-m", f"chore(release): {plan.tag}"], cwd=path, execute=execute)
    git(["tag", "-a", plan.tag, "-m", plan.tag], cwd=path, execute=execute)

    if push:
        git(["push"], cwd=path, execute=execute)
        git(["push", "origin", plan.tag], cwd=path, execute=execute)

    assets = list(plan.release_assets)
    if zip_asset is not None:
        assets.append(zip_asset)
    for optional in plan.optional_release_assets:
        if not execute or optional.is_file():
            assets.append(optional)

    gh_cmd = ["release", "create", plan.tag, "--title", plan.tag, "--generate-notes"]
    gh_cmd += [str(a) for a in assets]
    print(f"$ gh {' '.join(gh_cmd)}  (in {path})")
    if execute and push:
        subprocess.run(["gh", *gh_cmd], cwd=path, check=True)
    elif execute and not push:
        print("skipping `gh release create` because --no-push was set (tag not on origin yet)")


def main() -> int:
    parser = argparse.ArgumentParser(description="Cut a release based on detected project type")
    parser.add_argument("path", type=Path, help="Path to the repo checkout")
    parser.add_argument("bump", help="major | minor | patch | an explicit x.y.z version")
    parser.add_argument(
        "--execute", action="store_true", help="Actually perform the actions (default: dry run)"
    )
    parser.add_argument(
        "--no-push", action="store_true", help="Commit and tag locally but don't push or release"
    )
    parser.add_argument(
        "--allow-dirty", action="store_true", help="Skip the clean-working-tree check"
    )
    args = parser.parse_args()

    path = args.path.resolve()
    try:
        plan = build_plan(path, args.bump)
        print_plan(plan, path)
        if not args.execute:
            print("\n(dry run — pass --execute to actually make these changes)")
        apply_plan(
            plan, path, execute=args.execute, push=not args.no_push, allow_dirty=args.allow_dirty
        )
    except ReleaseError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as exc:
        print(f"error: command failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
