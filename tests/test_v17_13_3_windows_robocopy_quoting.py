from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "installer" / "windows" / "build-exe.ps1"
ISS = ROOT / "installer" / "windows" / "TVManager.iss"


def test_robocopy_uses_call_operator_argument_array_not_start_process():
    text = SCRIPT.read_text(encoding="utf-8")
    assert "& robocopy.exe @RoboArgs" in text
    assert 'Start-Process -FilePath "robocopy.exe"' not in text
    assert "$LASTEXITCODE" in text


def test_robocopy_source_and_target_are_separate_array_arguments():
    text = SCRIPT.read_text(encoding="utf-8")
    assert "$RoboArgs = @(" in text
    assert "$Root," in text
    assert "$StageApp," in text
    assert 'Write-Host "robocopy source : $Root"' in text
    assert 'Write-Host "robocopy target : $StageApp"' in text


def test_build_script_keeps_safe_external_staging_and_exclusions():
    text = SCRIPT.read_text(encoding="utf-8")
    assert 'Join-Path $env:TEMP "TVManagerBuild"' in text
    assert "release\\windows" in text
    for token in ['"dist"', '"build"', '"release"', '".venv"', '".git"', '"imports"', '"tvmanager.db"', '".env"']:
        assert token in text
    assert '"/MIR"' not in text


def test_inno_version_matches_patch_release():
    text = ISS.read_text(encoding="utf-8")
    assert "17.14.0" in text
    assert "release\\windows\\TVManager\\*" in text
