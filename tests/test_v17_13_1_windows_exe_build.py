from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "installer" / "windows" / "build-exe.ps1"
ISS = ROOT / "installer" / "windows" / "TVManager.iss"


def test_windows_exe_build_stages_outside_project_dist():
    text = SCRIPT.read_text(encoding="utf-8")
    assert 'Join-Path $env:TEMP "TVManagerBuild"' in text
    assert 'Join-Path $Root "dist\\TVManager"' not in text
    assert 'release\\windows' in text
    assert '--workpath $WorkPath' in text
    assert '--distpath $DistPath' in text
    assert '--specpath $SpecPath' in text


def test_windows_exe_build_excludes_recursive_and_runtime_folders():
    text = SCRIPT.read_text(encoding="utf-8")
    for forbidden in [
        '"dist"', '"build"', '"release"', '".venv"', '".git"',
        '"__pycache__"', '"diagnostics"', '"logs"', '"backups"',
        '"managed_trash"', '"imports"', '"tvmanager.db"', '".env"'
    ]:
        assert forbidden in text


def test_windows_exe_build_uses_project_python_module_invocation():
    text = SCRIPT.read_text(encoding="utf-8")
    assert '.venv\\Scripts\\python.exe' in text
    assert '-m PyInstaller' in text
    assert 'pip install pyinstaller' in text
    assert '\npyinstaller ' not in text.lower()


def test_inno_setup_uses_release_windows_payload_and_current_version():
    text = ISS.read_text(encoding="utf-8")
    assert '17.14.0' in text
    assert 'release\\windows\\TVManager\\*' in text
    assert 'dist\\TVManager\\*' not in text
