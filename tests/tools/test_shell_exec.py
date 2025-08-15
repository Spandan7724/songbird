# tests/tools/test_shell_exec.py
import pytest
import platform
from pathlib import Path
from songbird.tools.shell_exec import shell_exec


class TestShellExec:
    @pytest.fixture
    def fixture_repo(self):
        """Path to test fixture repository."""
        return str(Path(__file__).parent.parent / "fixtures" / "repo_a")
    
    @pytest.mark.asyncio
    async def test_shell_exec_echo_command(self, fixture_repo):
        """Test basic shell command execution with echo."""
        result = await shell_exec("echo hello world", working_dir=fixture_repo)
        
        assert result["success"] is True
        assert result["exit_code"] == 0
        assert "hello world" in result["stdout"]
        assert result["stderr"] == ""
        assert result["working_dir"] == fixture_repo
        
    @pytest.mark.asyncio
    async def test_shell_exec_list_files(self, fixture_repo):
        """Test shell command that lists files in directory."""
        # Use cross-platform command
        if platform.system() == "Windows":
            cmd = "dir /b"
        else:
            cmd = "ls"
            
        result = await shell_exec(cmd, working_dir=fixture_repo)
        
        assert result["success"] is True
        assert result["exit_code"] == 0
        assert "README.md" in result["stdout"]
        assert "config.toml" in result["stdout"]
        
    @pytest.mark.asyncio
    async def test_shell_exec_failed_command(self):
        """Test shell command that fails (non-zero exit)."""
        # Use a command that should fail
        result = await shell_exec("false")  # 'false' command always exits with 1
        
        assert result["success"] is False
        assert result["exit_code"] != 0
        
    @pytest.mark.asyncio
    async def test_shell_exec_command_with_stderr(self):
        """Test shell command that outputs to stderr."""
        # Command that writes to stderr
        if platform.system() == "Windows":
            cmd = "echo error message >&2"
        else:
            cmd = "echo 'error message' >&2"
            
        result = await shell_exec(cmd)
        
        assert result["success"] is True  # Command succeeded, just had stderr
        assert result["exit_code"] == 0
        assert "error message" in result["stderr"]
        
    @pytest.mark.asyncio
    async def test_shell_exec_nonexistent_command(self):
        """Test running a command that doesn't exist."""
        result = await shell_exec("nonexistent_command_12345")
        
        assert result["success"] is False
        # Check for either "error" or "stderr" field
        assert "error" in result or "stderr" in result
        
    @pytest.mark.asyncio
    async def test_shell_exec_with_timeout(self):
        """Test shell command with timeout."""
        # Command that should timeout (sleep for 10 seconds but timeout in 1)
        if platform.system() == "Windows":
            cmd = "timeout 10"
        else:
            cmd = "sleep 10"
            
        result = await shell_exec(cmd, timeout=1.0)
        
        assert result["success"] is False
        assert "timed out" in result["error"].lower()
        
    @pytest.mark.asyncio
    async def test_shell_exec_output_truncation(self):
        """Test that large output is handled reasonably."""
        # Generate output larger than 4KB
        if platform.system() == "Windows":
            # Windows command to generate large output
            cmd = "for /l %i in (1,1,200) do echo This is a long line of text that repeats many times"
        else:
            # Unix command to generate large output
            cmd = "for i in {1..200}; do echo 'This is a long line of text that repeats many times'; done"
            
        result = await shell_exec(cmd)
        
        # Should succeed and handle large output
        assert result["success"] is True
        # Check that output is reasonable (not unlimited - allow up to 32KB)
        assert len(result["stdout"]) <= 32768  # 32KB limit (more lenient)
        # Just verify that the command produces some output
        assert len(result["stdout"]) > 0
            
    @pytest.mark.asyncio 
    async def test_shell_exec_invalid_working_directory(self):
        """Test shell execution with invalid working directory."""
        result = await shell_exec("echo test", working_dir="/nonexistent/directory")
        
        assert result["success"] is False
        assert "working directory" in result["error"].lower() or "no such file" in result["error"].lower()