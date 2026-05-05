from pathlib import Path
import tomllib


ROOT = Path(__file__).resolve().parents[1]


def load_pyproject() -> dict:
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def test_pyproject_has_open_source_package_metadata():
    project = load_pyproject()["project"]

    assert project["readme"] == "README.md"
    assert project["license"] == {"file": "LICENSE"}
    assert project["authors"] == [{"name": "Personal AI OS contributors"}]
    assert "personal-ai" in project["keywords"]
    assert "rag" in project["keywords"]
    assert "open-webui" in project["keywords"]
    assert "local-first" in project["keywords"]
    assert "License :: OSI Approved :: Apache Software License" in project["classifiers"]
    assert "Framework :: FastAPI" in project["classifiers"]
    assert project["urls"] == {
        "Homepage": "https://github.com/julesChu12/personal-ai-os",
        "Repository": "https://github.com/julesChu12/personal-ai-os.git",
        "Issues": "https://github.com/julesChu12/personal-ai-os/issues",
    }


def test_license_file_is_apache_2_0():
    license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")

    assert "Apache License" in license_text
    assert "Version 2.0, January 2004" in license_text
    assert "http://www.apache.org/licenses/" in license_text


def test_build_backend_and_package_discovery_are_declared():
    pyproject = load_pyproject()

    assert pyproject["build-system"]["build-backend"] == "setuptools.build_meta"
    assert "setuptools>=61" in pyproject["build-system"]["requires"]
    assert pyproject["tool"]["setuptools"]["packages"]["find"]["include"] == ["app*"]


def test_pytest_markers_are_documented():
    pytest_options = load_pyproject()["tool"]["pytest"]["ini_options"]

    assert "integration: tests that require Docker services" in pytest_options["markers"]
