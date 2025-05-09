"""Tests for the GitHub Actions integration module."""

from typing import Dict, List, Any, Optional, Type, Generator, TYPE_CHECKING
import json
import os
import sys
import uuid
from pathlib import Path
from io import StringIO
from unittest.mock import patch, mock_open

import pytest

from github_actions import (
    AnnotationProperties,
    EnvOptions,
    ExitCode,
    GitHubAction,
    InputOptions,
    Summary,
)

if TYPE_CHECKING:
    from _pytest.capture import CaptureFixture
    from _pytest.monkeypatch import MonkeyPatch
    from pytest_mock.plugin import MockerFixture


class TestAnnotationProperties:
    """Tests for the AnnotationProperties class."""

    def test_initialization(self) -> None:
        """Test initializing with various properties."""
        # Initialize with no properties
        props_empty = AnnotationProperties()
        assert props_empty.title is None
        assert props_empty.file is None
        assert props_empty.start_line is None
        assert props_empty.end_line is None
        assert props_empty.start_column is None
        assert props_empty.end_column is None

        # Initialize with all properties
        props_full = AnnotationProperties(
            title="Test Title", file="file.py", start_line="10", end_line="20", start_column="5", end_column="15"
        )
        assert props_full.title == "Test Title"
        assert props_full.file == "file.py"
        assert props_full.start_line == "10"
        assert props_full.end_line == "20"
        assert props_full.start_column == "5"
        assert props_full.end_column == "15"

        # Initialize with subset of properties
        props_partial = AnnotationProperties(title="Error", file="main.py")
        assert props_partial.title == "Error"
        assert props_partial.file == "main.py"
        assert props_partial.start_line is None
        assert props_partial.end_line is None


class TestInputOptions:
    """Tests for the InputOptions class."""

    def test_initialization(self) -> None:
        """Test initializing with different options."""
        # Default values
        opts_default = InputOptions()
        assert opts_default.required is False
        assert opts_default.trim_whitespace is True

        # Custom values
        opts_custom = InputOptions(required=True, trim_whitespace=False)
        assert opts_custom.required is True
        assert opts_custom.trim_whitespace is False


class TestEnvOptions:
    """Tests for the EnvOptions class."""

    def test_initialization(self) -> None:
        """Test initializing with different options."""
        # Default values
        opts_default = EnvOptions()
        assert opts_default.required is False
        assert opts_default.trim_whitespace is True
        assert opts_default.default is None

        # Custom values
        opts_custom = EnvOptions(required=True, trim_whitespace=False, default="default_value")
        assert opts_custom.required is True
        assert opts_custom.trim_whitespace is False
        assert opts_custom.default == "default_value"


class TestExitCode:
    """Tests for the ExitCode class."""

    def test_constants(self) -> None:
        """Test exit code constants."""
        assert ExitCode.SUCCESS == 0
        assert ExitCode.FAILURE == 1


@pytest.fixture
def github_env_file(tmp_path: Path) -> Path:
    """
    Create a mock GitHub environment file.

    Args:
        tmp_path: Pytest fixture for temporary directory

    Returns:
        Path to the created environment file
    """
    env_file = tmp_path / "github_env"
    env_file.touch()
    return env_file


@pytest.fixture
def github_output_file(tmp_path: Path) -> Path:
    """
    Create a mock GitHub output file.

    Args:
        tmp_path: Pytest fixture for temporary directory

    Returns:
        Path to the created output file
    """
    output_file = tmp_path / "github_output"
    output_file.touch()
    return output_file


@pytest.fixture
def github_step_summary_file(tmp_path: Path) -> Path:
    """
    Create a mock GitHub step summary file.

    Args:
        tmp_path: Pytest fixture for temporary directory

    Returns:
        Path to the created summary file
    """
    summary_file = tmp_path / "step_summary"
    summary_file.touch()
    return summary_file


@pytest.fixture
def mock_github_files(
    github_env_file: Path, github_output_file: Path, github_step_summary_file: Path, monkeypatch: "MonkeyPatch"
) -> None:
    """
    Set up GitHub environment with mock files.

    Args:
        github_env_file: Path to mocked env file
        github_output_file: Path to mocked output file
        github_step_summary_file: Path to mocked summary file
        monkeypatch: Pytest monkeypatch fixture
    """
    monkeypatch.setenv("GITHUB_ENV", str(github_env_file))
    monkeypatch.setenv("GITHUB_OUTPUT", str(github_output_file))
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(github_step_summary_file))


class TestGitHubAction:
    """Test suite for the GitHubAction class."""

    def test_get_env_success(self, monkeypatch: "MonkeyPatch") -> None:
        """
        Test successful retrieval of environment variables.

        Args:
            monkeypatch: Pytest monkeypatch fixture
        """
        # Set a test environment variable
        monkeypatch.setenv("TEST_ENV_VAR", "test_value")

        action = GitHubAction()

        # Test with default options
        value = action.get_env("TEST_ENV_VAR")
        assert value == "test_value"

        # Test with custom options
        value = action.get_env("TEST_ENV_VAR", EnvOptions(required=True))
        assert value == "test_value"

    def test_get_env_not_set(self, monkeypatch: "MonkeyPatch") -> None:
        """
        Test getting non-existent environment variable.

        Args:
            monkeypatch: Pytest monkeypatch fixture
        """
        # Ensure the environment variable doesn't exist
        monkeypatch.delenv("TEST_ENV_VAR", raising=False)

        action = GitHubAction()

        # Test with default options (not required)
        value = action.get_env("TEST_ENV_VAR")
        assert value == ""

        # Test with default value
        value = action.get_env("TEST_ENV_VAR", EnvOptions(default="default_value"))
        assert value == "default_value"

        # Test with required option
        with pytest.raises(ValueError, match="Environment variable required and not supplied"):
            action.get_env("TEST_ENV_VAR", EnvOptions(required=True))

    def test_get_env_trim_whitespace(self, monkeypatch: "MonkeyPatch") -> None:
        """
        Test whitespace trimming in environment variables.

        Args:
            monkeypatch: Pytest monkeypatch fixture
        """
        # Set environment variable with whitespace
        monkeypatch.setenv("TEST_ENV_VAR", "  value_with_whitespace  ")

        action = GitHubAction()

        # Test with default options (trim enabled)
        value = action.get_env("TEST_ENV_VAR")
        assert value == "value_with_whitespace"

        # Test with trim disabled
        value = action.get_env("TEST_ENV_VAR", EnvOptions(trim_whitespace=False))
        assert value == "  value_with_whitespace  "

    def test_get_input_success(self, monkeypatch: "MonkeyPatch") -> None:
        """
        Test getting action inputs.

        Args:
            monkeypatch: Pytest monkeypatch fixture
        """
        # Set an input environment variable
        monkeypatch.setenv("INPUT_TEST_INPUT", "input_value")

        action = GitHubAction()
        value = action.get_input("test_input")

        assert value == "input_value"

        # Test with variations in input name casing and format
        monkeypatch.setenv("INPUT_TEST_DASH_INPUT", "dash_value")
        value = action.get_input("test-dash-input")
        assert value == "dash_value"

        monkeypatch.setenv("INPUT_TEST_SPACE_INPUT", "space_value")
        value = action.get_input("test space input")
        assert value == "space_value"

    def test_get_input_required(self, monkeypatch: "MonkeyPatch") -> None:
        """
        Test getting required action inputs.

        Args:
            monkeypatch: Pytest monkeypatch fixture
        """
        # Ensure input doesn't exist
        monkeypatch.delenv("INPUT_REQUIRED_INPUT", raising=False)

        action = GitHubAction()

        # Should raise error if required and not set
        with pytest.raises(ValueError, match="Input required and not supplied"):
            action.get_input("required_input", InputOptions(required=True))

        # Should return empty string if not required
        value = action.get_input("required_input")
        assert value == ""

    def test_get_input_whitespace(self, monkeypatch: "MonkeyPatch") -> None:
        """
        Test trimming whitespace in inputs.

        Args:
            monkeypatch: Pytest monkeypatch fixture
        """
        monkeypatch.setenv("INPUT_WHITESPACE_INPUT", "  input with whitespace  ")

        action = GitHubAction()

        # Test with default options (trim enabled)
        value = action.get_input("whitespace_input")
        assert value == "input with whitespace"

        # Test with trim disabled
        value = action.get_input("whitespace_input", InputOptions(trim_whitespace=False))
        assert value == "  input with whitespace  "

    def test_get_multiline_input(self, monkeypatch: "MonkeyPatch") -> None:
        """
        Test getting multiline inputs.

        Args:
            monkeypatch: Pytest monkeypatch fixture
        """
        # Set a multiline input
        monkeypatch.setenv("INPUT_MULTILINE_INPUT", "line1\nline2\n\nline3")

        action = GitHubAction()
        values = action.get_multiline_input("multiline_input")

        assert values == ["line1", "line2", "line3"]

        # Test with empty lines preserved (no trim)
        values = action.get_multiline_input("multiline_input", InputOptions(trim_whitespace=False))
        assert values == ["line1", "line2", "line3"]  # Empty lines are still filtered

    def test_get_multiline_input_empty(self, monkeypatch: "MonkeyPatch") -> None:
        """
        Test getting empty multiline inputs.

        Args:
            monkeypatch: Pytest monkeypatch fixture
        """
        # Set an empty input
        monkeypatch.setenv("INPUT_EMPTY_MULTILINE", "")

        action = GitHubAction()
        values = action.get_multiline_input("empty_multiline")

        assert values == []

    def test_get_boolean_input_true_variations(self, monkeypatch: "MonkeyPatch") -> None:
        """
        Test getting boolean inputs with various true values.

        Args:
            monkeypatch: Pytest monkeypatch fixture
        """
        action = GitHubAction()

        # Test different true values
        for true_value in ["true", "True", "TRUE"]:
            monkeypatch.setenv("INPUT_BOOL_INPUT", true_value)
            result = action.get_boolean_input("bool_input")
            assert result is True

    def test_get_boolean_input_false_variations(self, monkeypatch: "MonkeyPatch") -> None:
        """
        Test getting boolean inputs with various false values.

        Args:
            monkeypatch: Pytest monkeypatch fixture
        """
        action = GitHubAction()

        # Test different false values
        for false_value in ["false", "False", "FALSE"]:
            monkeypatch.setenv("INPUT_BOOL_INPUT", false_value)
            result = action.get_boolean_input("bool_input")
            assert result is False

    def test_get_boolean_input_invalid(self, monkeypatch: "MonkeyPatch") -> None:
        """
        Test error handling with invalid boolean inputs.

        Args:
            monkeypatch: Pytest monkeypatch fixture
        """
        monkeypatch.setenv("INPUT_BOOL_INPUT", "not_a_boolean")

        action = GitHubAction()

        with pytest.raises(TypeError, match="Input does not meet YAML 1.2 'Core Schema' specification"):
            action.get_boolean_input("bool_input")

    def test_export_variable_file_command(self, mock_github_files: None) -> None:
        """
        Test exporting environment variables using file commands.

        Args:
            mock_github_files: Fixture for GitHub files
        """
        action = GitHubAction()
        action.export_variable("TEST_VAR", "test_value")

        # Verify environment variable was set
        assert os.environ.get("TEST_VAR") == "test_value"

        # Verify file command was issued
        env_file = os.environ.get("GITHUB_ENV")
        with open(env_file, "r") as f:
            content = f.read()
            assert "TEST_VAR<<" in content
            assert "test_value" in content

    def test_export_variable_complex_value(self, mock_github_files: None) -> None:
        """
        Test exporting complex values (non-strings) as environment variables.

        Args:
            mock_github_files: Fixture for GitHub files
        """
        action = GitHubAction()
        complex_value = {"key": "value", "nested": {"data": [1, 2, 3]}}

        action.export_variable("COMPLEX_VAR", complex_value)

        # Verify environment variable was JSON encoded
        assert os.environ.get("COMPLEX_VAR") == json.dumps(complex_value)

        # Verify file command was issued with JSON value
        env_file = os.environ.get("GITHUB_ENV")
        with open(env_file, "r") as f:
            content = f.read()
            assert "COMPLEX_VAR<<" in content
            assert json.dumps(complex_value) in content

    def test_set_secret(self, capsys: "CaptureFixture[str]") -> None:
        """
        Test registering a secret.

        Args:
            capsys: Pytest capture fixture
        """
        action = GitHubAction()
        action.set_secret("super_secret_value")

        # Verify command was issued
        captured = capsys.readouterr()
        assert "::add-mask::super_secret_value" in captured.out

    def test_add_path(self, mock_github_files: None, monkeypatch: "MonkeyPatch") -> None:
        """
        Test adding a path to PATH environment variable.

        Args:
            mock_github_files: Fixture for GitHub files
            monkeypatch: Pytest monkeypatch fixture
        """
        # Set initial PATH
        monkeypatch.setenv("PATH", "/existing/path")

        action = GitHubAction()
        action.add_path("/new/path")

        # Verify PATH was updated
        assert os.environ.get("PATH") == "/new/path:/existing/path"

        # Verify file command was issued
        path_file = os.environ.get("GITHUB_PATH")
        with open(path_file, "r") as f:
            content = f.read()
            assert "/new/path" in content

    def test_set_output_file_command(self, mock_github_files: None) -> None:
        """
        Test setting action outputs using file commands.

        Args:
            mock_github_files: Fixture for GitHub files
        """
        action = GitHubAction()
        action.set_output("test-output", "output_value")

        # Verify file command was issued
        output_file = os.environ.get("GITHUB_OUTPUT")
        with open(output_file, "r") as f:
            content = f.read()
            assert "test-output<<" in content
            assert "output_value" in content

    def test_set_output_complex_value(self, mock_github_files: None) -> None:
        """
        Test setting complex values (non-strings) as outputs.

        Args:
            mock_github_files: Fixture for GitHub files
        """
        action = GitHubAction()
        complex_value = {"result": True, "data": [1, 2, 3]}

        action.set_output("complex-output", complex_value)

        # Verify file command was issued with JSON value
        output_file = os.environ.get("GITHUB_OUTPUT")
        with open(output_file, "r") as f:
            content = f.read()
            assert "complex-output<<" in content
            assert json.dumps(complex_value) in content

    def test_set_command_echo(self, capsys: "CaptureFixture[str]") -> None:
        """
        Test setting command echo.

        Args:
            capsys: Pytest capture fixture
        """
        action = GitHubAction()

        # Enable echo
        action.set_command_echo(True)
        captured = capsys.readouterr()
        assert "::echo::on" in captured.out

        # Disable echo
        action.set_command_echo(False)
        captured = capsys.readouterr()
        assert "::echo::off" in captured.out

    def test_set_failed(self, capsys: "CaptureFixture[str]", mocker: "MockerFixture") -> None:
        """
        Test setting action as failed.

        Args:
            capsys: Pytest capture fixture
            mocker: Pytest mocker fixture
        """
        # Mock sys.exit to prevent actual exit
        mock_exit = mocker.patch("sys.exit")

        action = GitHubAction()

        # Test with string message
        action.set_failed("Failure message")

        # Verify error command was issued
        captured = capsys.readouterr()
        assert "::error::Failure message" in captured.out

        # Verify exit was called with failure code
        mock_exit.assert_called_with(ExitCode.FAILURE)

        # Test with exception
        mock_exit.reset_mock()
        exception = RuntimeError("Exception message")
        action.set_failed(exception)

        # Verify error command includes exception message
        captured = capsys.readouterr()
        assert "::error::Exception message" in captured.out

        # Verify exit was called with failure code
        mock_exit.assert_called_with(ExitCode.FAILURE)

    def test_is_debug(self, monkeypatch: "MonkeyPatch") -> None:
        """
        Test checking debug mode.

        Args:
            monkeypatch: Pytest monkeypatch fixture
        """
        action = GitHubAction()

        # Test when debug is enabled
        monkeypatch.setenv("RUNNER_DEBUG", "1")
        assert action.is_debug() is True

        # Test when debug is disabled
        monkeypatch.setenv("RUNNER_DEBUG", "0")
        assert action.is_debug() is False

        # Test when debug is not set
        monkeypatch.delenv("RUNNER_DEBUG", raising=False)
        assert action.is_debug() is False

    def test_debug(self, capsys: "CaptureFixture[str]") -> None:
        """
        Test sending debug messages.

        Args:
            capsys: Pytest capture fixture
        """
        action = GitHubAction()
        action.debug("Debug message")

        # Verify debug command was issued
        captured = capsys.readouterr()
        assert "::debug::Debug message" in captured.out

    def test_error(self, capsys: "CaptureFixture[str]") -> None:
        """
        Test sending error messages.

        Args:
            capsys: Pytest capture fixture
        """
        action = GitHubAction()

        # Test with string message
        action.error("Error message")

        # Verify error command was issued
        captured = capsys.readouterr()
        assert "::error::Error message" in captured.out

        # Test with exception
        exception = ValueError("Exception error")
        action.error(exception)

        # Verify error command includes exception message
        captured = capsys.readouterr()
        assert "::error::Exception error" in captured.out

    def test_error_with_properties(self, capsys: "CaptureFixture[str]") -> None:
        """
        Test sending error with annotation properties.

        Args:
            capsys: Pytest capture fixture
        """
        action = GitHubAction()

        # Create properties
        props = AnnotationProperties(
            title="Error Title", file="file.py", start_line="10", end_line="20", start_column="5", end_column="15"
        )

        action.error("Error with properties", props)

        # Verify error command includes all properties
        captured = capsys.readouterr()
        cmd = captured.out.strip()
        assert "::error" in cmd
        assert "title=Error Title" in cmd
        assert "file=file.py" in cmd
        assert "line=10" in cmd
        assert "endLine=20" in cmd
        assert "col=5" in cmd
        assert "endColumn=15" in cmd
        assert "::Error with properties" in cmd

    def test_warning(self, capsys: "CaptureFixture[str]") -> None:
        """
        Test sending warning messages.

        Args:
            capsys: Pytest capture fixture
        """
        action = GitHubAction()

        # Test with string message
        action.warning("Warning message")

        # Verify warning command was issued
        captured = capsys.readouterr()
        assert "::warning::Warning message" in captured.out

        # Test with exception
        exception = RuntimeError("Warning exception")
        action.warning(exception)

        # Verify warning command includes exception message
        captured = capsys.readouterr()
        assert "::warning::Warning exception" in captured.out

    def test_warning_with_properties(self, capsys: "CaptureFixture[str]") -> None:
        """
        Test sending warning with annotation properties.

        Args:
            capsys: Pytest capture fixture
        """
        action = GitHubAction()

        # Create properties with only some fields
        props = AnnotationProperties(title="Warning", file="script.js")

        action.warning("Warning with properties", props)

        # Verify warning command includes provided properties
        captured = capsys.readouterr()
        cmd = captured.out.strip()
        assert "::warning" in cmd
        assert "title=Warning" in cmd
        assert "file=script.js" in cmd
        assert "::Warning with properties" in cmd

    def test_notice(self, capsys: "CaptureFixture[str]") -> None:
        """
        Test sending notice messages.

        Args:
            capsys: Pytest capture fixture
        """
        action = GitHubAction()

        # Test with string message
        action.notice("Notice message")

        # Verify notice command was issued
        captured = capsys.readouterr()
        assert "::notice::Notice message" in captured.out

        # Test with exception
        exception = RuntimeError("Notice exception")
        action.notice(exception)

        # Verify notice command includes exception message
        captured = capsys.readouterr()
        assert "::notice::Notice exception" in captured.out

    def test_info(self, capsys: "CaptureFixture[str]") -> None:
        """
        Test sending info messages.

        Args:
            capsys: Pytest capture fixture
        """
        action = GitHubAction()
        action.info("Info message")

        # Verify message was printed
        captured = capsys.readouterr()
        assert "Info message" in captured.out

    def test_group(self, capsys: "CaptureFixture[str]") -> None:
        """
        Test grouping output.

        Args:
            capsys: Pytest capture fixture
        """
        action = GitHubAction()

        # Define a function to execute within the group
        def test_fn() -> str:
            action.info("Message within group")
            return "result"

        # Execute the function within a group
        result = action.group("Group Title", test_fn)

        # Verify group commands were issued
        captured = capsys.readouterr()
        assert "::group::Group Title" in captured.out
        assert "Message within group" in captured.out
        assert "::endgroup::" in captured.out

        # Verify function result was returned
        assert result == "result"

    def test_group_with_exception(self, capsys: "CaptureFixture[str]") -> None:
        """
        Test group handling when function raises exception.

        Args:
            capsys: Pytest capture fixture
        """
        action = GitHubAction()

        # Define a function that raises an exception
        def failing_fn() -> None:
            action.info("Before exception")
            raise ValueError("Test exception")

        # Execute the function within a group - should propagate exception
        with pytest.raises(ValueError, match="Test exception"):
            action.group("Error Group", failing_fn)

        # Verify group commands were issued and endgroup was called
        captured = capsys.readouterr()
        assert "::group::Error Group" in captured.out
        assert "Before exception" in captured.out
        assert "::endgroup::" in captured.out

    def test_save_state(self, mock_github_files: None) -> None:
        """
        Test saving state for current action.

        Args:
            mock_github_files: Fixture for GitHub files
        """
        action = GitHubAction()
        action.save_state("test-state", "state_value")

        # Verify file command was issued
        state_file = os.environ.get("GITHUB_STATE")
        with open(state_file, "r") as f:
            content = f.read()
            assert "test-state<<" in content
            assert "state_value" in content

    def test_get_state(self, monkeypatch: "MonkeyPatch") -> None:
        """
        Test getting state from environment.

        Args:
            monkeypatch: Pytest monkeypatch fixture
        """
        monkeypatch.setenv("STATE_TEST_STATE", "saved_value")

        action = GitHubAction()
        value = action.get_state("TEST_STATE")

        assert value == "saved_value"

    def test_command_value_conversion(self) -> None:
        """Test _to_command_value method for different input types."""
        action = GitHubAction()

        # Test with string
        assert action._to_command_value("string") == "string"

        # Test with empty string
        assert action._to_command_value("") == ""

        # Test with None
        assert action._to_command_value(None) == ""

        # Test with integer
        assert action._to_command_value(42) == "42"

        # Test with boolean
        assert action._to_command_value(True) == "true"

        # Test with dictionary
        assert action._to_command_value({"key": "value"}) == '{"key": "value"}'

        # Test with list
        assert action._to_command_value([1, 2, 3]) == "[1, 2, 3]"

    def test_command_properties_conversion(self) -> None:
        """Test _to_command_properties method for annotation properties."""
        action = GitHubAction()

        # Create properties with all fields
        props = AnnotationProperties(
            title="Title", file="file.py", start_line="10", end_line="20", start_column="5", end_column="15"
        )

        command_props = action._to_command_properties(props)

        # Verify property mapping
        assert command_props["title"] == "Title"
        assert command_props["file"] == "file.py"
        assert command_props["line"] == "10"
        assert command_props["endLine"] == "20"
        assert command_props["col"] == "5"
        assert command_props["endColumn"] == "15"

        # Create properties with only some fields
        props_partial = AnnotationProperties(title="Title", file="file.py")

        command_props = action._to_command_properties(props_partial)

        # Verify only provided properties are included
        assert command_props["title"] == "Title"
        assert command_props["file"] == "file.py"
        assert "line" not in command_props
        assert "endLine" not in command_props
        assert "col" not in command_props
        assert "endColumn" not in command_props

    def test_escape_data(self) -> None:
        """Test _escape_data method for command values."""
        action = GitHubAction()

        # Test escaping % character
        assert action._escape_data("50%") == "50%25"

        # Test escaping newlines
        assert action._escape_data("line1\nline2") == "line1%0Aline2"

        # Test escaping carriage returns
        assert action._escape_data("value\rreturn") == "value%0Dreturn"

        # Test escaping complex string
        assert action._escape_data("complex\r\n%value") == "complex%0D%0A%25value"

    def test_escape_property(self) -> None:
        """Test _escape_property method for command properties."""
        action = GitHubAction()

        # Test escaping % character
        assert action._escape_property("50%") == "50%25"

        # Test escaping newlines
        assert action._escape_property("line1\nline2") == "line1%0Aline2"

        # Test escaping carriage returns
        assert action._escape_property("value\rreturn") == "value%0Dreturn"

        # Test escaping colons and commas (specific to properties)
        assert action._escape_property("key:value,item") == "key%3Avalue%2Citem"

        # Test escaping complex string
        assert action._escape_property("complex\r\n%:,value") == "complex%0D%0A%25%3A%2Cvalue"

    def test_prepare_key_value_message(self) -> None:
        """Test _prepare_key_value_message method for file commands."""
        action = GitHubAction()

        # Test with string value
        message = action._prepare_key_value_message("key", "value")

        # Verify format is correct
        assert message.startswith("key<<ghadelimiter_")
        assert "value" in message
        assert message.endswith("ghadelimiter_" + message.split("_")[1].split("\n")[0])

        # Test with complex value
        data = {"nested": {"array": [1, 2, 3]}}
        message = action._prepare_key_value_message("complex_key", data)

        assert message.startswith("complex_key<<ghadelimiter_")
        assert json.dumps(data) in message

    def test_prepare_key_value_message_with_delimiter_in_key(self) -> None:
        """Test error when delimiter appears in key."""
        action = GitHubAction()

        # Get a delimiter by calling the method and extracting it
        temp_message = action._prepare_key_value_message("temp", "value")
        delimiter = temp_message.split("<<")[1].split("\n")[0]

        # Test with delimiter in key
        with pytest.raises(ValueError, match="name should not contain the delimiter"):
            action._prepare_key_value_message(f"bad{delimiter}key", "value")

    def test_prepare_key_value_message_with_delimiter_in_value(self) -> None:
        """Test error when delimiter appears in value."""
        action = GitHubAction()

        # Get a delimiter by calling the method and extracting it
        temp_message = action._prepare_key_value_message("temp", "value")
        delimiter = temp_message.split("<<")[1].split("\n")[0]

        # Test with delimiter in value
        with pytest.raises(ValueError, match="value should not contain the delimiter"):
            action._prepare_key_value_message("key", f"bad{delimiter}value")

    def test_issue_file_command(self, mock_github_files: None) -> None:
        """
        Test issuing a file command.

        Args:
            mock_github_files: Fixture for GitHub files
        """
        action = GitHubAction()
        action._issue_file_command("OUTPUT", "test-output=test-value")

        # Verify file was written to
        output_file = os.environ.get("GITHUB_OUTPUT")
        with open(output_file, "r") as f:
            content = f.read()
            assert "test-output=test-value" in content

    def test_issue_file_command_missing_env(self, monkeypatch: "MonkeyPatch") -> None:
        """
        Test error when file command environment variable is missing.

        Args:
            monkeypatch: Pytest monkeypatch fixture
        """
        # Remove the environment variable
        monkeypatch.delenv("GITHUB_OUTPUT", raising=False)

        action = GitHubAction()

        with pytest.raises(ValueError, match="Unable to find environment variable"):
            action._issue_file_command("OUTPUT", "test-output=test-value")

    def test_issue_file_command_missing_file(self, monkeypatch: "MonkeyPatch") -> None:
        """
        Test error when file doesn't exist.

        Args:
            monkeypatch: Pytest monkeypatch fixture
        """
        # Set environment variable to non-existent file
        monkeypatch.setenv("GITHUB_OUTPUT", "/non/existent/file")

        action = GitHubAction()

        with pytest.raises(FileNotFoundError, match="Missing file at path"):
            action._issue_file_command("OUTPUT", "test-output=test-value")


class TestSummary:
    """Test suite for the Summary class."""

    def test_initialization(self) -> None:
        """Test initializing Summary class."""
        action = GitHubAction()
        summary = action.summary

        assert summary._buffer == ""
        assert summary._file_path is None
        assert summary._gh is action

    def test_file_path(self, mock_github_files: None) -> None:
        """
        Test getting summary file path.

        Args:
            mock_github_files: Fixture for GitHub files
        """
        action = GitHubAction()
        summary = action.summary

        path = summary.file_path()

        assert path == os.environ.get("GITHUB_STEP_SUMMARY")

        # Should cache the path
        assert summary._file_path == path

        # Second call should use cached path
        path2 = summary.file_path()
        assert path2 == path

    def test_file_path_missing_env(self, monkeypatch: "MonkeyPatch") -> None:
        """
        Test error when summary path is missing.

        Args:
            monkeypatch: Pytest monkeypatch fixture
        """
        monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)

        action = GitHubAction()
        summary = action.summary

        with pytest.raises(ValueError, match="Unable to find environment variable"):
            summary.file_path()

    def test_file_path_no_permissions(self, mock_github_files: None, mocker: "MockerFixture") -> None:
        """
        Test error when summary file is not writable.

        Args:
            mock_github_files: Fixture for GitHub files
            mocker: Pytest mocker fixture
        """
        # Mock open to raise IOError
        mock_open = mocker.patch("builtins.open", side_effect=IOError("Permission denied"))

        action = GitHubAction()
        summary = action.summary

        with pytest.raises(IOError, match="Unable to access summary file"):
            summary.file_path()

    def test_wrap(self) -> None:
        """Test _wrap method for creating HTML elements."""
        action = GitHubAction()
        summary = action.summary

        # Test simple tag with content
        html = summary._wrap("div", "content")
        assert html == "<div>content</div>"

        # Test tag with attributes
        html = summary._wrap("a", "link", {"href": "https://example.com", "target": "_blank"})
        assert html == '<a href="https://example.com" target="_blank">link</a>'

        # Test self-closing tag (no content)
        html = summary._wrap("br", None)
        assert html == "<br>"

        # Test self-closing tag with attributes
        html = summary._wrap("img", None, {"src": "image.png", "alt": "Alt text"})
        assert html == '<img src="image.png" alt="Alt text">'

    def test_write(self, mock_github_files: None) -> None:
        """
        Test writing summary to file.

        Args:
            mock_github_files: Fixture for GitHub files
        """
        action = GitHubAction()
        summary = action.summary

        # Add content to buffer
        summary.add_raw("Test content")

        # Write to file
        result = summary.write()

        # Verify file was written to
        summary_file = os.environ.get("GITHUB_STEP_SUMMARY")
        with open(summary_file, "r") as f:
            content = f.read()
            assert "Test content" in content

        # Verify buffer was emptied
        assert summary._buffer == ""

        # Verify method returns summary instance for chaining
        assert result is summary

    def test_write_overwrite(self, mock_github_files: None) -> None:
        """
        Test overwriting summary file.

        Args:
            mock_github_files: Fixture for GitHub files
        """
        summary_file = os.environ.get("GITHUB_STEP_SUMMARY")

        # Write initial content to file
        with open(summary_file, "w") as f:
            f.write("Initial content")

        action = GitHubAction()
        summary = action.summary

        # Add new content and overwrite
        summary.add_raw("New content")
        summary.write({"overwrite": True})

        # Verify file was overwritten
        with open(summary_file, "r") as f:
            content = f.read()
            assert "Initial content" not in content
            assert "New content" in content

    def test_clear(self, mock_github_files: None) -> None:
        """
        Test clearing summary file.

        Args:
            mock_github_files: Fixture for GitHub files
        """
        summary_file = os.environ.get("GITHUB_STEP_SUMMARY")

        # Write initial content to file
        with open(summary_file, "w") as f:
            f.write("Initial content")

        action = GitHubAction()
        summary = action.summary

        # Clear summary
        result = summary.clear()

        # Verify file was cleared
        with open(summary_file, "r") as f:
            content = f.read()
            assert content == ""

        # Verify method returns summary instance for chaining
        assert result is summary

    def test_stringify(self) -> None:
        """Test stringify method for getting buffer contents."""
        action = GitHubAction()
        summary = action.summary

        # Initially buffer should be empty
        assert summary.stringify() == ""

        # Add content
        summary.add_raw("Buffer content")
        assert summary.stringify() == "Buffer content"

    def test_is_empty_buffer(self) -> None:
        """Test is_empty_buffer method for checking buffer state."""
        action = GitHubAction()
        summary = action.summary

        # Initially buffer should be empty
        assert summary.is_empty_buffer() is True

        # Add content
        summary.add_raw("Content")
        assert summary.is_empty_buffer() is False

        # Empty buffer
        summary.empty_buffer()
        assert summary.is_empty_buffer() is True

    def test_empty_buffer(self) -> None:
        """Test empty_buffer method for clearing buffer."""
        action = GitHubAction()
        summary = action.summary

        # Add content
        summary.add_raw("Test content")
        assert summary._buffer == "Test content"

        # Empty buffer
        result = summary.empty_buffer()

        # Verify buffer was emptied
        assert summary._buffer == ""

        # Verify method returns summary instance for chaining
        assert result is summary

    def test_add_raw(self) -> None:
        """Test add_raw method for adding content to buffer."""
        action = GitHubAction()
        summary = action.summary

        # Add content
        result = summary.add_raw("Test content")

        # Verify content was added
        assert summary._buffer == "Test content"

        # Add more content without EOL
        summary.add_raw(" and more")
        assert summary._buffer == "Test content and more"

        # Add content with EOL
        summary.add_raw(" with EOL", True)
        assert summary._buffer == f"Test content and more with EOL{os.linesep}"

        # Verify method returns summary instance for chaining
        assert result is summary

    def test_add_eol(self) -> None:
        """Test add_eol method for adding line breaks."""
        action = GitHubAction()
        summary = action.summary

        # Add EOL
        result = summary.add_eol()

        # Verify EOL was added
        assert summary._buffer == os.linesep

        # Add content and EOL
        summary.add_raw("Line 1").add_eol().add_raw("Line 2")
        assert summary._buffer == f"{os.linesep}Line 1{os.linesep}Line 2"

        # Verify method returns summary instance for chaining
        assert result is summary

    def test_add_code_block(self) -> None:
        """Test add_code_block method for adding code blocks."""
        action = GitHubAction()
        summary = action.summary

        # Add code block without language
        result = summary.add_code_block("const x = 5;")

        # Verify HTML was added
        assert "<pre><code>const x = 5;</code></pre>" in summary._buffer
        assert f"{os.linesep}" in summary._buffer

        # Clear buffer
        summary.empty_buffer()

        # Add code block with language
        summary.add_code_block("def hello():\n    print('Hello')", "python")

        # Verify HTML with language attribute was added
        assert '<pre lang="python"><code>def hello():' in summary._buffer

        # Verify method returns summary instance for chaining
        assert result is summary

    def test_add_list(self) -> None:
        """Test add_list method for adding HTML lists."""
        action = GitHubAction()
        summary = action.summary

        # Add unordered list
        result = summary.add_list(["Item 1", "Item 2", "Item 3"])

        # Verify HTML was added
        html = summary._buffer
        assert "<ul>" in html
        assert "<li>Item 1</li>" in html
        assert "<li>Item 2</li>" in html
        assert "<li>Item 3</li>" in html
        assert "</ul>" in html

        # Clear buffer
        summary.empty_buffer()

        # Add ordered list
        summary.add_list(["First", "Second", "Third"], ordered=True)

        # Verify HTML was added
        html = summary._buffer
        assert "<ol>" in html
        assert "<li>First</li>" in html
        assert "<li>Second</li>" in html
        assert "<li>Third</li>" in html
        assert "</ol>" in html

        # Verify method returns summary instance for chaining
        assert result is summary

    def test_add_table(self) -> None:
        """Test add_table method for adding HTML tables."""
        action = GitHubAction()
        summary = action.summary

        # Create table with header row and data rows
        rows = [
            [{"data": "Name", "header": True}, {"data": "Language", "header": True}],
            ["Python", "High-level"],
            ["C++", "Systems"],
        ]

        # Add table
        result = summary.add_table(rows)

        # Verify HTML was added
        html = summary._buffer
        assert "<table>" in html
        assert "<tr>" in html
        assert "<th>Name</th>" in html
        assert "<th>Language</th>" in html
        assert "<td>Python</td>" in html
        assert "<td>High-level</td>" in html
        assert "<td>C++</td>" in html
        assert "<td>Systems</td>" in html
        assert "</table>" in html

        # Verify method returns summary instance for chaining
        assert result is summary

    def test_add_table_with_colspan_rowspan(self) -> None:
        """Test add_table method with colspan and rowspan attributes."""
        action = GitHubAction()
        summary = action.summary

        # Create table with merged cells
        rows = [
            [{"data": "Header", "colspan": "2", "header": True}],
            [{"data": "Row 1, Col 1"}, {"data": "Row 1, Col 2"}],
            [{"data": "Row 2, Col 1", "rowspan": "2"}, {"data": "Row 2, Col 2"}],
            [{"data": "Row 3, Col 2"}],  # No first column due to rowspan above
        ]

        # Add table
        summary.add_table(rows)

        # Verify HTML with colspan and rowspan was added
        html = summary._buffer
        assert '<th colspan="2">Header</th>' in html
        assert '<td rowspan="2">Row 2, Col 1</td>' in html

    def test_add_details(self) -> None:
        """Test add_details method for adding collapsible sections."""
        action = GitHubAction()
        summary = action.summary

        # Add details element
        result = summary.add_details("Summary Text", "Collapsible content")

        # Verify HTML was added
        html = summary._buffer
        assert "<details>" in html
        assert "<summary>Summary Text</summary>" in html
        assert "Collapsible content" in html
        assert "</details>" in html

        # Verify method returns summary instance for chaining
        assert result is summary

    def test_add_image(self) -> None:
        """Test add_image method for adding images."""
        action = GitHubAction()
        summary = action.summary

        # Add image without optional attributes
        result = summary.add_image("path/to/image.png", "Alt text")

        # Verify HTML was added
        html = summary._buffer
        assert '<img src="path/to/image.png" alt="Alt text">' in html

        # Clear buffer
        summary.empty_buffer()

        # Add image with width and height
        summary.add_image("path/to/image.png", "Alt text", {"width": "100px", "height": "80px"})

        # Verify HTML with additional attributes was added
        html = summary._buffer
        assert '<img src="path/to/image.png" alt="Alt text" width="100px" height="80px">' in html

        # Verify method returns summary instance for chaining
        assert result is summary

    def test_add_heading(self) -> None:
        """Test add_heading method for adding headings."""
        action = GitHubAction()
        summary = action.summary

        # Add level 1 heading (default)
        result = summary.add_heading("Heading 1")

        # Verify HTML was added
        assert "<h1>Heading 1</h1>" in summary._buffer

        # Clear buffer
        summary.empty_buffer()

        # Add headings with different levels
        for level in range(1, 7):
            summary.add_heading(f"Heading {level}", level)

        # Verify all headings were added
        html = summary._buffer
        for level in range(1, 7):
            assert f"<h{level}>Heading {level}</h{level}>" in html

        # Test invalid level (should default to h1)
        summary.empty_buffer()
        summary.add_heading("Invalid Level", 8)
        assert "<h1>Invalid Level</h1>" in summary._buffer

        # Verify method returns summary instance for chaining
        assert result is summary

    def test_add_separator(self) -> None:
        """Test add_separator method for adding horizontal rules."""
        action = GitHubAction()
        summary = action.summary

        # Add separator
        result = summary.add_separator()

        # Verify HTML was added
        assert "<hr>" in summary._buffer

        # Verify method returns summary instance for chaining
        assert result is summary

    def test_add_break(self) -> None:
        """Test add_break method for adding line breaks."""
        action = GitHubAction()
        summary = action.summary

        # Add break
        result = summary.add_break()

        # Verify HTML was added
        assert "<br>" in summary._buffer

        # Verify method returns summary instance for chaining
        assert result is summary

    def test_add_quote(self) -> None:
        """Test add_quote method for adding blockquotes."""
        action = GitHubAction()
        summary = action.summary

        # Add quote without citation
        result = summary.add_quote("This is a quote")

        # Verify HTML was added
        assert "<blockquote>This is a quote</blockquote>" in summary._buffer

        # Clear buffer
        summary.empty_buffer()

        # Add quote with citation
        summary.add_quote("Cited quote", "https://example.com")

        # Verify HTML with citation was added
        assert '<blockquote cite="https://example.com">Cited quote</blockquote>' in summary._buffer

        # Verify method returns summary instance for chaining
        assert result is summary

    def test_add_link(self) -> None:
        """Test add_link method for adding hyperlinks."""
        action = GitHubAction()
        summary = action.summary

        # Add link
        result = summary.add_link("Link Text", "https://example.com")

        # Verify HTML was added
        assert '<a href="https://example.com">Link Text</a>' in summary._buffer

        # Verify method returns summary instance for chaining
        assert result is summary
