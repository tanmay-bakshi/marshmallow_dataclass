import os
import sysconfig


def pytest_configure() -> None:
    """Ensure the current environment's console scripts are on ``PATH``.

    pytest-mypy-plugins shells out to ``mypy`` via :func:`shutil.which`, so
    running tests via ``python -m pytest`` (without activating a virtualenv)
    still needs the environment's scripts directory available on ``PATH``.
    """
    scripts_dir: str | None = sysconfig.get_path("scripts")
    if scripts_dir is None:
        return

    current_path: str | None = os.environ.get("PATH")
    if current_path is None:
        os.environ["PATH"] = scripts_dir
        return

    path_parts: list[str] = current_path.split(os.pathsep)
    if scripts_dir in path_parts:
        return

    os.environ["PATH"] = scripts_dir + os.pathsep + current_path

