"""
Unit tests for uninstall functionality in uvs.uvs module.

Tests cover:
- run_uv_uninstall() function
- verify_tool_uninstalled() function
- cleanup_registry_entry() function
- backup_registry() function
"""

import json
import os
import shutil
import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, call

from uvs.uvs import (
    run_uv_uninstall,
    verify_tool_uninstalled,
    cleanup_registry_entry,
    backup_registry,
    load_registry,
    save_registry,
    get_config_dir,
    get_registry_path,
)


@pytest.fixture
def isolated_temp_dir(tmp_path):
    """Provide an isolated temporary directory for each test."""
    original_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        yield tmp_path
    finally:
        os.chdir(original_cwd)


@pytest.fixture
def mock_registry_reset():
    """Reset registry state between tests."""
    # Clean up any existing registry
    registry_path = Path(".uvs-registry.json")
    if registry_path.exists():
        registry_path.unlink()

    yield

    # Clean up after test
    if registry_path.exists():
        registry_path.unlink()


@pytest.fixture
def mock_subprocess():
    """Mock subprocess calls with deterministic behavior."""
    with patch('subprocess.run') as mock_run:
        # Default successful return
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        yield mock_run


@pytest.fixture
def sample_registry():
    """Create a sample registry with test tools."""
    return {
        "version": "1.0",
        "created_at": "2023-01-01T00:00:00Z",
        "scripts": {
            "test-tool": {
                "tool_name": "test-tool",
                "source_path": "/path/to/test.py",
                "source_hash": "abc123",
                "installed_at": "2023-01-01T00:00:00Z",
                "version": "0.1.0",
            },
            "another-tool": {
                "tool_name": "another-tool",
                "source_path": "/path/to/another.py",
                "source_hash": "def456",
                "installed_at": "2023-01-01T00:00:00Z",
                "version": "0.2.0",
            }
        }
    }


class TestRunUvUninstall:
    """Test run_uv_uninstall function."""

    def test_successful_uninstall(self, mock_subprocess):
        """Test successful uv tool uninstall."""
        mock_subprocess.return_value = MagicMock(returncode=0, stdout="Uninstalled test-tool")
        
        result = run_uv_uninstall("test-tool")
        
        assert result == 0
        mock_subprocess.assert_called_once_with(["uv", "tool", "uninstall", "test-tool"])

    def test_failed_uninstall(self, mock_subprocess):
        """Test failed uv tool uninstall."""
        mock_subprocess.return_value = MagicMock(returncode=1, stderr="Tool not found")
        
        result = run_uv_uninstall("nonexistent-tool")
        
        assert result == 1
        mock_subprocess.assert_called_once_with(["uv", "tool", "uninstall", "nonexistent-tool"])

    def test_subprocess_exception(self, mock_subprocess):
        """Test handling of subprocess exceptions."""
        mock_subprocess.side_effect = Exception("Subprocess failed")
        
        with pytest.raises(Exception):
            run_uv_uninstall("test-tool")


class TestVerifyToolUninstalled:
    """Test verify_tool_uninstalled function."""

    @patch('subprocess.run')
    def test_tool_successfully_uninstalled_via_list(self, mock_run):
        """Test verification when tool is not in uv tool list."""
        # Mock uv tool list to return empty list
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='[]',
            stderr=""
        )
        
        result = verify_tool_uninstalled("test-tool")
        
        assert result is True
        mock_run.assert_called_once_with(
            ["uv", "tool", "list", "--format=json"],
            capture_output=True,
            text=True,
            check=True
        )

    @patch('subprocess.run')
    def test_tool_still_installed_via_list(self, mock_run):
        """Test verification when tool is still in uv tool list."""
        # Mock uv tool list to return tool still installed
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='[{"name": "test-tool", "version": "0.1.0"}]',
            stderr=""
        )
        
        result = verify_tool_uninstalled("test-tool")
        
        assert result is False

    @patch('subprocess.run')
    def test_verification_fallback_to_direct_command(self, mock_run):
        """Test fallback to direct command when JSON list fails."""
        # First call fails (JSON list)
        mock_run.side_effect = [
            MagicMock(returncode=1, stderr="Command failed")  # uv tool list fails
        ]
        
        # Mock the second call separately
        with patch('subprocess.run') as mock_run2:
            mock_run2.return_value = MagicMock(returncode=0, stdout="Help text")
            
            result = verify_tool_uninstalled("test-tool")
            
            assert result is False  # Tool still exists since --help worked

    def test_verification_fallback_command_not_found(self):
        """Test fallback when direct command fails with FileNotFoundError."""
        from unittest.mock import call
        from subprocess import CalledProcessError
        
        with patch('subprocess.run') as mock_run:
            # First call fails with CalledProcessError (check=True causes this)
            # Second call fails with FileNotFoundError
            mock_run.side_effect = [
                CalledProcessError(1, ["uv", "tool", "list"], stderr="Command failed"),  # uv tool list fails
                FileNotFoundError("Command not found")                                     # tool --help fails
            ]
            
            result = verify_tool_uninstalled("test-tool")
            
            assert result is True  # Tool is uninstalled
            assert mock_run.call_count == 2

    def test_verification_with_timeout(self):
        """Test verification with timeout on direct command."""
        from subprocess import TimeoutExpired, CalledProcessError
        
        with patch('subprocess.run') as mock_run:
            # First call fails with CalledProcessError (check=True causes this)
            # Second call times out
            mock_run.side_effect = [
                CalledProcessError(1, ["uv", "tool", "list"], stderr="Command failed"),  # uv tool list fails
                TimeoutExpired("test-tool", 5)                                          # tool --help times out
            ]
            
            result = verify_tool_uninstalled("test-tool")
            
            assert result is True  # Tool is uninstalled
            assert mock_run.call_count == 2

    def test_verification_with_invalid_json(self):
        """Test verification with invalid JSON output."""
        with patch('subprocess.run') as mock_run:
            # First call returns invalid JSON, second fails with FileNotFoundError
            mock_run.side_effect = [
                MagicMock(returncode=0, stdout='invalid json output', stderr=""),  # Invalid JSON
                FileNotFoundError("Command not found")                             # tool --help fails
            ]
            
            result = verify_tool_uninstalled("test-tool")
            
            assert result is True  # Falls back to direct command
            assert mock_run.call_count == 2


class TestCleanupRegistryEntry:
    """Test cleanup_registry_entry function."""

    def test_cleanup_existing_entry(self, isolated_temp_dir, sample_registry):
        """Test removing an existing tool from registry."""
        # Setup registry
        save_registry(sample_registry)
        
        # Remove tool
        result = cleanup_registry_entry("test-tool")
        
        assert result is True
        
        # Verify tool is removed
        registry = load_registry()
        assert "test-tool" not in registry["scripts"]
        assert "another-tool" in registry["scripts"]

    def test_cleanup_nonexistent_entry(self, isolated_temp_dir, sample_registry):
        """Test removing a non-existent tool from registry."""
        # Setup registry
        save_registry(sample_registry)
        
        # Try to remove non-existent tool
        result = cleanup_registry_entry("nonexistent-tool")
        
        assert result is False
        
        # Verify registry is unchanged
        registry = load_registry()
        assert len(registry["scripts"]) == 2

    def test_cleanup_empty_registry(self, isolated_temp_dir):
        """Test removing from empty registry."""
        # Setup empty registry
        empty_registry = {"version": "1.0", "created_at": "2023-01-01T00:00:00Z", "scripts": {}}
        save_registry(empty_registry)
        
        # Try to remove tool
        result = cleanup_registry_entry("test-tool")
        
        assert result is False

    def test_cleanup_with_registry_exception(self, isolated_temp_dir):
        """Test handling of registry exceptions."""
        # Mock load_registry to raise exception
        with patch('uvs.uvs.load_registry', side_effect=Exception("Registry error")):
            result = cleanup_registry_entry("test-tool")
            
            assert result is False

    def test_cleanup_with_save_exception(self, isolated_temp_dir, sample_registry):
        """Test handling of save registry exceptions."""
        # Setup registry
        save_registry(sample_registry)
        
        # Mock save_registry to raise exception
        with patch('uvs.uvs.save_registry', side_effect=Exception("Save error")):
            result = cleanup_registry_entry("test-tool")
            
            assert result is False


class TestBackupRegistry:
    """Test backup_registry function."""

    def test_backup_existing_registry(self, isolated_temp_dir, sample_registry):
        """Test creating backup of existing registry."""
        # Setup registry
        save_registry(sample_registry)
        
        # Create backup
        backup_path = backup_registry()
        
        # Verify backup was created
        assert backup_path.exists()
        assert backup_path.name.startswith("registry_")
        assert backup_path.name.endswith(".json")
        
        # Verify backup content
        backup_content = json.loads(backup_path.read_text())
        assert backup_content == sample_registry

    def test_backup_nonexistent_registry(self, isolated_temp_dir):
        """Test creating backup when registry doesn't exist."""
        # Ensure registry doesn't exist
        registry_path = get_registry_path()
        if registry_path.exists():
            registry_path.unlink()
        
        # Create backup
        backup_path = backup_registry()
        
        # Verify backup path is returned
        assert backup_path.name.startswith("registry_")
        # Note: The backup function creates the file even if registry doesn't exist

    def test_backup_creates_backups_directory(self, isolated_temp_dir, sample_registry):
        """Test that backup creates backups directory if needed."""
        # Setup registry
        save_registry(sample_registry)
        
        # Ensure backups directory doesn't exist
        config_dir = get_config_dir()
        backups_dir = config_dir / "backups"
        if backups_dir.exists():
            shutil.rmtree(backups_dir)
        
        # Create backup
        backup_path = backup_registry()
        
        # Verify backups directory was created
        assert backups_dir.exists()
        assert backup_path.parent == backups_dir

    def test_backup_timestamp_format(self, isolated_temp_dir, sample_registry):
        """Test that backup filename includes timestamp."""
        # Setup registry
        save_registry(sample_registry)
        
        # Create backup
        backup_path = backup_registry()
        
        # Verify timestamp format (YYYYMMDD_HHMMSS)
        filename = backup_path.name
        assert filename.startswith("registry_")
        assert filename.endswith(".json")
        
        # Extract timestamp part
        timestamp_part = filename[9:-5]  # Remove "registry_" prefix and ".json" suffix
        assert len(timestamp_part) == 15  # YYYYMMDD_HHMMSS
        assert timestamp_part[8] == "_"  # Separator between date and time

    def test_multiple_backups(self, isolated_temp_dir, sample_registry):
        """Test creating multiple backups."""
        # Setup registry
        save_registry(sample_registry)
        
        # Create multiple backups with a small delay to ensure different timestamps
        import time
        backup1 = backup_registry()
        time.sleep(0.01)  # Small delay to ensure different timestamp
        backup2 = backup_registry()
        
        # Verify both backups exist
        assert backup1.exists()
        assert backup2.exists()
        # Note: Timestamps might be the same if the system is fast, so we just check both exist

    def test_backup_with_shutil_copy(self, isolated_temp_dir, sample_registry):
        """Test that backup uses shutil.copy2 for metadata preservation."""
        # Setup registry
        save_registry(sample_registry)
        
        # Create backup
        with patch('shutil.copy2') as mock_copy:
            backup_path = backup_registry()
            
            # Verify shutil.copy2 was called
            mock_copy.assert_called_once()
            args, kwargs = mock_copy.call_args
            assert len(args) == 2  # Source and destination paths