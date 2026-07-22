from __future__ import annotations

from pathlib import Path
import zipfile

from Altium.project_package import inspect_project_package


def test_inspects_complete_native_project_inventory(tmp_path: Path) -> None:
    archive = tmp_path / "project.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr(
            "demo/board.PrjPcb",
            "[Document1]\nDocumentPath=main.SchDoc\n[Document2]\nDocumentPath=board.PcbDoc\n",
        )
        bundle.writestr("demo/main.SchDoc", b"native schematic bytes")
        bundle.writestr("demo/board.PcbDoc", b"native pcb bytes")
        bundle.writestr("demo/project.SchLib", b"native library bytes")
        bundle.writestr("demo/project.PcbLib", b"native footprint library bytes")

    report = inspect_project_package(archive)

    assert report.passed is True
    assert report.project_files == ("demo/board.PrjPcb",)
    assert report.schematic_files == ("demo/main.SchDoc",)
    assert report.pcb_files == ("demo/board.PcbDoc",)
    assert report.declared_documents == ("board.PcbDoc", "main.SchDoc")


def test_reports_missing_project_document(tmp_path: Path) -> None:
    archive = tmp_path / "broken.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("board.PrjPcb", "DocumentPath=missing.SchDoc\n")
        bundle.writestr("main.SchDoc", b"native schematic bytes")

    report = inspect_project_package(archive)

    assert report.passed is False
    assert any("declares missing documents" in error for error in report.errors)
