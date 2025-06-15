import subprocess
import sys
import pathlib

def test_songbird_cli_runs():
    exe = pathlib.Path(sys.executable).with_name("songbird")
    result = subprocess.run([exe, "chat"], capture_output=True, text=True, timeout=5)
    assert result.returncode == 0
    assert "Songbird" in result.stdout
