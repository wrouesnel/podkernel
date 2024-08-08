"""Kernelspec installation facilities

Where term "kernelspec dir" is used, it references the directory in which
kernel.json file is present.

Where term "kernelspec store" is used, it references the directory where
jupyter will look for kernelspec dirs.
"""

import os
from pathlib import Path
import string

from podkernel.logging import get_logger
from podkernel.models import JupyterKernelSpec

logger = get_logger()

KERNELSPEC_FILENAME = "kernel.json"
KERNELSPEC_STORE_DIRNAME = "kernels"
KERNELSPEC_KERNELID_ALLOWED_CHARACTERS = set(string.ascii_letters + string.digits + "_.-")

def make_kernel_id(name: str) -> str:
    """
    Generate a valid kernel ID from a given name. This is not guaranteed to be unique.

    Parameters
    ----------
    name

    Returns
    -------
    valid kernel ID name
    """
    return "".join(c if c in KERNELSPEC_KERNELID_ALLOWED_CHARACTERS else "_" for c in name)

def validate_kernel_id(kernel_id: str):
    if not set(kernel_id) <= KERNELSPEC_KERNELID_ALLOWED_CHARACTERS:
        disallowed_chars = set(kernel_id) - KERNELSPEC_KERNELID_ALLOWED_CHARACTERS
        raise ValueError(f"kernel_id contains forbidden characters: {kernel_id} ({''.join(disallowed_chars)})")

# TODO: make sure windows path is expanded properly
def user_kernelspec_store(system_type: str) -> Path:
    """Return path to the place where users kernelspecs are stored on given OS.
    Parameters
    ----------
    system_type
        Output of the builtin ``platform.system()``.

    Raises
    ------
    ValueError
        If `system_type` is not one of the supported types.

    Returns
    -------
    Path
        Path object to the per-user directory where kernelspec dirs are stored.
    """

    if system_type == "Linux":
        kernelspec_dir_path = "~/.local/share/jupyter/kernels"
    elif system_type == "Windows":
        kernelspec_dir_path = os.getenv("APPDATA") + r"\jupyter\kernels"
    elif system_type == "Darwin":
        kernelspec_dir_path = "~/Library/Jupyter/kernels"
    else:
        raise ValueError(f"unknown system type: {system_type}")

    return Path(kernelspec_dir_path).expanduser()

def install_kernelspec(kernelspec_store: Path, kernelspec: JupyterKernelSpec, kernel_id: str) -> str:
    """
    Install the given kernelspec to the kernelspec_store and increment the kernel_id

    Parameters
    ----------
    kernelspec_store
    kernelspec
    kernel_id

    Returns
    -------

    """
    validate_kernel_id(kernel_id)
    real_kernel_id = kernel_id
    idx = 0

    while True:
        kernel_dir = (kernelspec_store / real_kernel_id)
        logger.debug("Checking if kernel already exists", kernel_id=real_kernel_id)
        if kernel_dir.exists():
            logger.debug("Kernel with same ID already exists - incrementing ID")
            real_kernel_id = f"{kernel_id}_{idx}"
            idx += 1
        else:
            kernel_dir.mkdir()
            break

    logger.info("Installed new kernel", kernel_id=real_kernel_id)
    (kernel_dir / KERNELSPEC_FILENAME).write_text(kernelspec.model_dump_json(indent=True))

    return real_kernel_id
