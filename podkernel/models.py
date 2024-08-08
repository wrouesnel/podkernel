import enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class JupyterInterruptMode(enum.Enum):
    """Jupyter Kernel Interrupt Modes"""

    Signal = "signal"
    Message = "message"


class JupyterKernelSpec(BaseModel):
    """Jupyter Kernel Spec"""

    argv: List[str]
    display_name: str
    language: str
    interrupt_mode: Optional[JupyterInterruptMode]
    env: Optional[Dict[str, str]] = None
    metadata: Optional[Dict[str, Any]]

class PodKernelMetadata(BaseModel):
    """Namespaced metadata we store in the kernelspec"""
    image_name: str
    build: bool
    build_args: List[str] = []
    run_args: List[str] = []
    cmd_args: List[str] = []
