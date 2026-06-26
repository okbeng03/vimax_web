"""Config bidirectional sync: YAML + config.py read/write between Web and working_dir."""

import re
import shutil
from pathlib import Path
import yaml


class ConfigSyncService:
    """Sync project config files between Web editor and working_dir."""

    # ------------------------------------------------------------------
    # Basic read / write
    # ------------------------------------------------------------------

    @staticmethod
    def read_yaml(working_dir: str) -> str | None:
        """Read idea2video.yaml content from working_dir."""
        yaml_path = Path(working_dir) / "idea2video.yaml"
        if not yaml_path.exists():
            return None
        return yaml_path.read_text(encoding="utf-8")

    @staticmethod
    def read_config_py(working_dir: str) -> str | None:
        """Read config.py content from working_dir."""
        config_path = Path(working_dir) / "config.py"
        if not config_path.exists():
            return None
        return config_path.read_text(encoding="utf-8")

    @staticmethod
    def write_yaml(working_dir: str, content: str) -> None:
        """Write idea2video.yaml content to working_dir."""
        yaml_path = Path(working_dir) / "idea2video.yaml"
        yaml_path.parent.mkdir(parents=True, exist_ok=True)
        yaml_path.write_text(content, encoding="utf-8")

    @staticmethod
    def write_config_py(working_dir: str, content: str) -> None:
        """Write config.py content to working_dir."""
        config_path = Path(working_dir) / "config.py"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(content, encoding="utf-8")

    # ------------------------------------------------------------------
    # YAML interrupt_step helpers
    # ------------------------------------------------------------------

    @staticmethod
    def read_interrupt_step(working_dir: str) -> str | None:
        """Read interrupt_step value from YAML config."""
        content = ConfigSyncService.read_yaml(working_dir)
        if not content:
            return None
        data = yaml.safe_load(content)
        return data.get("interrupt_step") if data else None

    @staticmethod
    def write_interrupt_step(working_dir: str, step_name: str) -> None:
        """Update interrupt_step in YAML config in place."""
        content = ConfigSyncService.read_yaml(working_dir) or ""
        data = yaml.safe_load(content) or {}
        data["interrupt_step"] = step_name
        new_content = yaml.dump(data, allow_unicode=True, default_flow_style=False)
        ConfigSyncService.write_yaml(working_dir, new_content)

    # ------------------------------------------------------------------
    # Template copy + variable replacement
    # ------------------------------------------------------------------

    @staticmethod
    def copy_template(template_dir: str, target_dir: str) -> None:
        """Copy template YAML and config.py to target working_dir."""
        src = Path(template_dir)
        dst = Path(target_dir)
        dst.mkdir(parents=True, exist_ok=True)

        # Copy idea2video.yaml
        yaml_src = src / "idea2video.yaml"
        if yaml_src.exists():
            shutil.copy2(yaml_src, dst / "idea2video.yaml")

        # Copy config.py
        config_src = src / "config.py"
        if config_src.exists():
            shutil.copy2(config_src, dst / "config.py")

        # Create workflows/ subdir
        (dst / "workflows").mkdir(exist_ok=True)

    @staticmethod
    def replace_variables(working_dir: str, *, idea: str, working_dir_value: str) -> None:
        r"""Replace template variables in config.py and idea2video.yaml.

        - config.py:  ``idea = \"\"\"...\"\"\"``  ->  ``idea = \"\"\"{idea}\"\"\"``
        - config.py:  ``working_dir = "..."``   ->  ``working_dir = "{wd}"``
        - idea2video.yaml:  ``working_dir: /old`` -> ``working_dir: {wd}``
        """
        # --- config.py ---
        config_content = ConfigSyncService.read_config_py(working_dir)
        if config_content:
            # Replace idea variable (triple-quoted string)
            config_content = re.sub(
                r'^idea\s*=\s*"""[\s\S]*?"""',
                f'idea = """\n{idea}\n"""',
                config_content,
                count=1,
                flags=re.MULTILINE,
            )
            # Replace working_dir variable (single/double-quoted string)
            config_content = re.sub(
                r'^working_dir\s*=\s*["\'][^"\']*["\']',
                f'working_dir = "{working_dir_value}"',
                config_content,
                count=1,
                flags=re.MULTILINE,
            )
            ConfigSyncService.write_config_py(working_dir, config_content)

        # --- idea2video.yaml ---
        yaml_content = ConfigSyncService.read_yaml(working_dir)
        if yaml_content:
            yaml_content = re.sub(
                r'^working_dir:\s*.+$',
                f'working_dir: {working_dir_value}',
                yaml_content,
                count=1,
                flags=re.MULTILINE,
            )
            ConfigSyncService.write_yaml(working_dir, yaml_content)

    # ------------------------------------------------------------------
    # Sync from VIMAX_ROOT/configs/
    # ------------------------------------------------------------------

    @staticmethod
    def sync_vimax_configs(vimax_root: str) -> str | None:
        """Check VIMAX_ROOT/configs/ for config.py + idea2video.yaml.

        If found, parse config.py's ``working_dir``.  If that directory
        exists, copy both files there.  Returns the working_dir found in
        VIMAX_ROOT/configs/config.py (or None if not applicable).
        """
        configs_dir = Path(vimax_root) / "configs"
        if not configs_dir.is_dir():
            return None

        src_config_py = configs_dir / "config.py"
        src_yaml = configs_dir / "idea2video.yaml"
        if not src_config_py.exists() or not src_yaml.exists():
            return None

        # Extract working_dir from VIMAX_ROOT configs/config.py
        content = src_config_py.read_text(encoding="utf-8")
        m = re.search(r'^working_dir\s*=\s*["\']([^"\']+)["\']', content, re.MULTILINE)
        if not m:
            return None

        target_dir = m.group(1)
        if not Path(target_dir).exists():
            return target_dir  # dir doesn't exist, nothing to sync

        # Sync the two config files to target directory
        shutil.copy2(src_config_py, Path(target_dir) / "config.py")
        shutil.copy2(src_yaml, Path(target_dir) / "idea2video.yaml")

        return target_dir

    # ------------------------------------------------------------------
    # Reverse sync: project working_dir → VIMAX_ROOT/configs/
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Gacha mode helpers
    # ------------------------------------------------------------------

    @staticmethod
    def write_gacha_config(working_dir: str, gacha_type: str, scene: int, shot: int) -> None:
        """Set mode=gacha and gacha_config in YAML, preserving other fields."""
        content = ConfigSyncService.read_yaml(working_dir) or ""
        data = yaml.safe_load(content) or {}
        data["mode"] = "gacha"
        data["gacha_config"] = {
            "type": gacha_type,
            "scene": scene,
            "shot": shot,
        }
        new_content = yaml.dump(data, allow_unicode=True, default_flow_style=False)
        ConfigSyncService.write_yaml(working_dir, new_content)

    # ------------------------------------------------------------------
    # Reverse sync: project working_dir → VIMAX_ROOT/configs/
    # ------------------------------------------------------------------

    @staticmethod
    def sync_project_to_vimax(working_dir: str, vimax_root: str) -> None:
        """Copy the project's idea2video.yaml + config.py into
        VIMAX_ROOT/configs/ so ViMax picks them up on next run.
        """
        configs_dir = Path(vimax_root) / "configs"
        configs_dir.mkdir(parents=True, exist_ok=True)

        src_yaml = Path(working_dir) / "idea2video.yaml"
        src_config_py = Path(working_dir) / "config.py"

        if src_yaml.exists():
            shutil.copy2(src_yaml, configs_dir / "idea2video.yaml")
        if src_config_py.exists():
            shutil.copy2(src_config_py, configs_dir / "config.py")
