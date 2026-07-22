import subprocess
import sys
from pathlib import Path


def test_email_worker_registers_all_referenced_model_tables() -> None:
    backend_root = Path(__file__).resolve().parents[1]
    code = """
from codrut.core.database import Base
from codrut.workers import main as worker_main  # noqa: F401

Base.metadata.sorted_tables
"""

    result = subprocess.run(  # noqa: S603 - fixed interpreter and repository-owned code
        [sys.executable, "-c", code],
        cwd=backend_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
