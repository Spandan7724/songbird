import subprocess
import sys
import pathlib

def test_songbird_version_runs():
    """Test that songbird version command works."""
    exe = pathlib.Path(sys.executable).with_name("songbird")
    result = subprocess.run([exe, "version"], capture_output=True, text=True, timeout=5)
    assert result.returncode == 0
    assert "Songbird" in result.stdout

def test_songbird_help_runs():
    """Test that songbird help command works."""
    exe = pathlib.Path(sys.executable).with_name("songbird")
    result = subprocess.run([exe, "--help"], capture_output=True, text=True, timeout=5)
    assert result.returncode == 0
    assert "Songbird" in result.stdout
