import json
import shutil
import sys
from pathlib import Path


def copy_if_exists(src, dst):
    if src.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def main():
    target_root = Path(__file__).resolve().parents[1]
    project_root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else target_root.parent
    data_dir = target_root / "data"
    files_dir = data_dir / "files"
    static_img = target_root / "app" / "static" / "img"
    data_dir.mkdir(parents=True, exist_ok=True)
    files_dir.mkdir(parents=True, exist_ok=True)
    static_img.mkdir(parents=True, exist_ok=True)

    for name in ["contacts.json", "customer_data.json", "customer_settings.json", "bond_data_cache.csv"]:
        copy_if_exists(project_root / name, data_dir / name)

    config_src = project_root / "config.json"
    config_dst = data_dir / "config.json"
    copy_if_exists(config_src, config_dst)
    if config_dst.exists():
        with config_dst.open("r", encoding="utf-8") as f:
            config = json.load(f)
        config["excel_path"] = "data/bond_data_cache.csv"
        config["ui_original_path"] = "data/bond_data_cache.csv"
        with config_dst.open("w", encoding="utf-8") as f:
            json.dump(config, f, indent=4, ensure_ascii=False)

    source_files = project_root / "files"
    if source_files.exists():
        for child in source_files.iterdir():
            if child.is_file() and not child.name.startswith("~$"):
                copy_if_exists(child, files_dir / child.name)

    for name in ["icon.png", "splash.png"]:
        copy_if_exists(project_root / name, static_img / name)

    for folder in ["uploads", "outputs", "logs"]:
        (target_root / folder).mkdir(parents=True, exist_ok=True)
        gitkeep = target_root / folder / ".gitkeep"
        if not gitkeep.exists():
            gitkeep.write_text("", encoding="utf-8")

    print(f"Migrated data from {project_root} to {target_root}")


if __name__ == "__main__":
    main()
