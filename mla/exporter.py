"""Utilities for exporting project data."""
from __future__ import annotations

import datetime
import os
from typing import Tuple

from .project import ProjectData


def save_project_output(
    project: ProjectData,
    project_index: int,
    output_dir: str,
    output_prefix: str = "",
) -> Tuple[bool, str, int, int, bool]:
    if not project:
        return False, "No project selected", 0, 0, False

    try:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        if output_prefix:
            folder_name = f"{output_prefix}_Project_{project_index + 1}_{timestamp}"
        else:
            folder_name = f"Project_{project_index + 1}_{timestamp}"

        project_folder = os.path.join(output_dir, folder_name)
        os.makedirs(project_folder, exist_ok=True)

        img_ok = 0
        img_err = 0
        for idx, proc_item in enumerate(project.processed_images):
            processed = proc_item.get("processed")
            if processed:
                try:
                    filename = f"processed_{idx + 1:03d}.png"
                    processed.save(os.path.join(project_folder, filename))
                    img_ok += 1
                except Exception:
                    img_err += 1

        desc_ok = False
        if project.generated_description:
            try:
                desc_path = os.path.join(project_folder, "description.txt")
                with open(desc_path, "w", encoding="utf-8") as handle:
                    handle.write(project.generated_description)
                desc_ok = True
            except Exception:
                desc_ok = False

        return True, folder_name, img_ok, img_err, desc_ok
    except Exception as exc:
        return False, str(exc), 0, 0, False
