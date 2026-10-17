"""Setuptools build hook: включить расположенный в репозитории курс в wheel."""

from __future__ import annotations

from pathlib import Path
from shutil import copytree, rmtree

from setuptools import setup
from setuptools.command.build_py import build_py


class BuildPyWithCourseContent(build_py):
    """Копирует единственный исходный каталог content внутрь пакета в build-lib."""

    def run(self) -> None:
        super().run()
        source = Path(__file__).resolve().parent / "content"
        target = Path(self.build_lib) / "devops_academy" / "content"
        if target.exists():
            rmtree(target)
        copytree(source, target)
        self._course_content_outputs = [str(path) for path in target.rglob("*") if path.is_file()]

    def get_outputs(self, include_bytecode: int = 1) -> list[str]:
        outputs = super().get_outputs(include_bytecode)
        return [*outputs, *getattr(self, "_course_content_outputs", [])]


setup(cmdclass={"build_py": BuildPyWithCourseContent})
