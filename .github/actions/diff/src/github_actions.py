#!/usr/bin/env python3
"""
This project is a partial python implementation of and contains code derived from or inspired
by actions/toolkit (https://github.com/actions/toolkit), which is licensed under the MIT License.
"""

import os
import sys
import json
import uuid
from typing import Any, Callable, TypeVar, final

T = TypeVar("T")


class AnnotationProperties:
    """Properties that can be sent with annotation commands (notice, error, warning)."""

    def __init__(
        self,
        title: str | None = None,
        file: str | None = None,
        start_line: str | None = None,
        end_line: str | None = None,
        start_column: str | None = None,
        end_column: str | None = None,
    ) -> None:
        """
        Initialize annotation properties.

        Args:
            title: A title for the annotation
            file: The path of the file for which the annotation should be created
            start_line: The start line for the annotation
            end_line: The end line for the annotation
            start_column: The start column for the annotation
            end_column: The end column for the annotation
        """
        self.title: str | None = title
        self.file: str | None = file
        self.start_line: str | None = start_line
        self.end_line: str | None = end_line
        self.start_column: str | None = start_column
        self.end_column: str | None = end_column


class InputOptions:
    """Options for getInput."""

    def __init__(self, required: bool = False, trim_whitespace: bool = True) -> None:
        """
        Initialize input options.

        Args:
            required: Whether the input is required. If required and not present, will throw
            trim_whitespace: Whether leading/trailing whitespace will be trimmed for the input
        """
        self.required: bool = required
        self.trim_whitespace: bool = trim_whitespace


class EnvOptions:
    """Options for getEnv."""

    def __init__(self, required: bool = False, trim_whitespace: bool = True, default: str | None = None) -> None:
        """
        Initialize environment variable options.

        Args:
            required: Whether the environment variable is required. If required and not present, will throw
            trim_whitespace: Whether leading/trailing whitespace will be trimmed
            default: Default value if the environment variable is not set
        """
        self.required: bool = required
        self.trim_whitespace: bool = trim_whitespace
        self.default: str | None = default


@final
class ExitCode:
    """The code to exit an action."""

    # A code indicating that the action was successful
    SUCCESS = 0

    # A code indicating that the action was a failure
    FAILURE = 1


class Summary:
    """Summary functionality for GitHub Actions."""

    def __init__(self, gh: "GitHubAction") -> None:
        """
        Initialize the Summary class.

        Args:
            gh: Reference to the GitHubAction instance for accessing environment variables
        """
        self._buffer: str = ""
        self._file_path: str | None = None
        self._gh: GitHubAction = gh

    def file_path(self) -> str:
        """
        Finds the summary file path from the environment.

        Returns:
            Step summary file path

        Raises:
            ValueError: If environment variable is not found
            IOError: If file doesn't have read/write permissions
        """
        if self._file_path:
            return self._file_path

        path_from_env = self._gh.get_env("GITHUB_STEP_SUMMARY", EnvOptions(required=True))

        try:
            # Check file permissions
            with open(path_from_env, "a+"):
                pass
        except IOError:
            raise IOError(
                f"Unable to access summary file: '{path_from_env}'. "
                + "Check if the file has correct read/write permissions."
            )

        self._file_path = path_from_env
        return self._file_path

    def _wrap(self, tag: str, content: str | None = None, attrs: dict[str, str] | None = None) -> str:
        """
        Wraps content in an HTML tag.

        Args:
            tag: HTML tag to wrap
            content: Content within the tag
            attrs: Key-value list of HTML attributes to add

        Returns:
            Content wrapped in HTML element
        """
        attrs = attrs or {}
        html_attrs = "".join(f' {key}="{value}"' for key, value in attrs.items())

        if content is None:
            return f"<{tag}{html_attrs}>"

        return f"<{tag}{html_attrs}>{content}</{tag}>"

    def write(self, options: dict[str, bool] | None = None) -> "Summary":
        """
        Writes text in the buffer to the summary file and empties buffer.

        Args:
            options: Options for write operation

        Returns:
            Summary instance
        """
        options = options or {}
        overwrite = options.get("overwrite", False)

        file_path = self.file_path()

        with open(file_path, "w" if overwrite else "a", encoding="utf-8") as f:
            _ = f.write(self._buffer)

        return self.empty_buffer()

    def clear(self) -> "Summary":
        """
        Clears the summary buffer and wipes the summary file.

        Returns:
            Summary instance
        """
        return self.empty_buffer().write({"overwrite": True})

    def stringify(self) -> str:
        """
        Returns the current summary buffer as a string.

        Returns:
            String of summary buffer
        """
        return self._buffer

    def is_empty_buffer(self) -> bool:
        """
        Checks if the summary buffer is empty.

        Returns:
            True if the buffer is empty
        """
        return len(self._buffer) == 0

    def empty_buffer(self) -> "Summary":
        """
        Resets the summary buffer without writing to summary file.

        Returns:
            Summary instance
        """
        self._buffer = ""
        return self

    def add_raw(self, text: str, add_eol: bool = False) -> "Summary":
        """
        Adds raw text to the summary buffer.

        Args:
            text: Content to add
            add_eol: Append an EOL to the raw text

        Returns:
            Summary instance
        """
        self._buffer += text
        return self.add_eol() if add_eol else self

    def add_eol(self) -> "Summary":
        """
        Adds the operating system-specific end-of-line marker to the buffer.

        Returns:
            Summary instance
        """
        return self.add_raw(os.linesep)

    def add_code_block(self, code: str, lang: str | None = None) -> "Summary":
        """
        Adds an HTML codeblock to the summary buffer.

        Args:
            code: Content to render within fenced code block
            lang: Language to syntax highlight code

        Returns:
            Summary instance
        """
        attrs = {}
        if lang:
            attrs["lang"] = lang

        element = self._wrap("pre", self._wrap("code", code), attrs)
        return self.add_raw(element).add_eol()

    def add_list(self, items: list[str], ordered: bool = False) -> "Summary":
        """
        Adds an HTML list to the summary buffer.

        Args:
            items: list of items to render
            ordered: If the rendered list should be ordered or not

        Returns:
            Summary instance
        """
        tag = "ol" if ordered else "ul"
        list_items = "".join(self._wrap("li", item) for item in items)
        element = self._wrap(tag, list_items)
        return self.add_raw(element).add_eol()

    def add_table(self, rows: list[list[dict[str, Any] | str]]) -> "Summary":
        """
        Adds an HTML table to the summary buffer.

        Args:
            rows: Table rows

        Returns:
            Summary instance
        """
        table_body = ""

        for row in rows:
            cells = ""
            for cell in row:
                if isinstance(cell, str):
                    cells += self._wrap("td", cell)
                else:
                    header = cell.get("header", False)
                    data = cell.get("data", "")
                    colspan = cell.get("colspan")
                    rowspan = cell.get("rowspan")

                    tag = "th" if header else "td"
                    attrs = {}

                    if colspan:
                        attrs["colspan"] = colspan
                    if rowspan:
                        attrs["rowspan"] = rowspan

                    cells += self._wrap(tag, data, attrs)

            table_body += self._wrap("tr", cells)

        element = self._wrap("table", table_body)
        return self.add_raw(element).add_eol()

    def add_details(self, label: str, content: str) -> "Summary":
        """
        Adds a collapsable HTML details element to the summary buffer.

        Args:
            label: Text for the closed state
            content: Collapsable content

        Returns:
            Summary instance
        """
        element = self._wrap("details", self._wrap("summary", label) + content)
        return self.add_raw(element).add_eol()

    def add_image(self, src: str, alt: str, options: dict[str, str] | None = None) -> "Summary":
        """
        Adds an HTML image tag to the summary buffer.

        Args:
            src: Path to the image to embed
            alt: Text description of the image
            options: Additional image attributes

        Returns:
            Summary instance
        """
        options = options or {}
        attrs = {"src": src, "alt": alt}

        if "width" in options:
            attrs["width"] = options["width"]
        if "height" in options:
            attrs["height"] = options["height"]

        element = self._wrap("img", None, attrs)
        return self.add_raw(element).add_eol()

    def add_heading(self, text: str, level: int | str | None = 1) -> "Summary":
        """
        Adds an HTML section heading element.

        Args:
            text: Heading text
            level: The heading level

        Returns:
            Summary instance
        """
        tag = f"h{level}"
        allowed_tags = ["h1", "h2", "h3", "h4", "h5", "h6"]
        tag = tag if tag in allowed_tags else "h1"

        element = self._wrap(tag, text)
        return self.add_raw(element).add_eol()

    def add_separator(self) -> "Summary":
        """
        Adds an HTML thematic break (<hr>) to the summary buffer.

        Returns:
            Summary instance
        """
        element = self._wrap("hr", None)
        return self.add_raw(element).add_eol()

    def add_break(self) -> "Summary":
        """
        Adds an HTML line break (<br>) to the summary buffer.

        Returns:
            Summary instance
        """
        element = self._wrap("br", None)
        return self.add_raw(element).add_eol()

    def add_quote(self, text: str, cite: str | None = None) -> "Summary":
        """
        Adds an HTML blockquote to the summary buffer.

        Args:
            text: Quote text
            cite: Citation URL

        Returns:
            Summary instance
        """
        attrs = {}
        if cite:
            attrs["cite"] = cite

        element = self._wrap("blockquote", text, attrs)
        return self.add_raw(element).add_eol()

    def add_link(self, text: str, href: str) -> "Summary":
        """
        Adds an HTML anchor tag to the summary buffer.

        Args:
            text: Link text/content
            href: Hyperlink

        Returns:
            Summary instance
        """
        element = self._wrap("a", text, {"href": href})
        return self.add_raw(element).add_eol()


class GitHubAction:
    """
    Core functionality for GitHub Actions.

    This class provides methods to interact with GitHub Actions workflow commands,
    including setting outputs, secrets, environment variables, and more.
    """

    def __init__(self) -> None:
        """Initialize the GitHubAction class."""
        self._summary = Summary(self)

    @property
    def summary(self) -> Summary:
        """Get the summary instance."""
        return self._summary

    def get_env(self, name: str, options: EnvOptions | None = None) -> str:
        """
        Gets the value of an environment variable.

        Args:
            name: The name of the environment variable
            options: Optional. See EnvOptions

        Returns:
            The value of the environment variable

        Raises:
            ValueError: If the environment variable is required and not set
        """
        options = options or EnvOptions()
        val = os.environ.get(name, "")

        if not val:
            if options.required:
                raise ValueError(f"Environment variable required and not supplied: {name}")
            elif options.default is not None:
                val = options.default

        if options.trim_whitespace:
            val = val.strip()

        return val

    def export_variable(self, name: str, val: Any) -> None:
        """
        Sets env variable for this action and future actions in the job.

        Args:
            name: The name of the variable to set
            val: The value of the variable. Non-string values will be converted to a string via JSON
        """
        converted_val = self._to_command_value(val)
        os.environ[name] = converted_val

        file_path = self.get_env("GITHUB_ENV")
        if file_path:
            self._issue_file_command("ENV", self._prepare_key_value_message(name, val))
        else:
            self._issue_command("set-env", {"name": name}, converted_val)

    def set_secret(self, secret: str) -> None:
        """
        Registers a secret which will get masked from logs.

        Args:
            secret: Value of the secret to be masked
        """
        self._issue_command("add-mask", {}, secret)

    def add_path(self, input_path: str) -> None:
        """
        Prepends inputPath to the PATH for this action and future actions.

        Args:
            input_path: The path to add
        """
        file_path = self.get_env("GITHUB_PATH")
        if file_path:
            self._issue_file_command("PATH", input_path)
        else:
            self._issue_command("add-path", {}, input_path)

        # Also update PATH for current process
        path_value = self.get_env("PATH") or ""
        os.environ["PATH"] = f"{input_path}{os.pathsep}{path_value}"

    def get_input(self, name: str, options: InputOptions | None = None) -> str:
        """
        Gets the value of an input.

        Args:
            name: Name of the input to get
            options: Optional. See InputOptions

        Returns:
            String value of the input

        Raises:
            ValueError: If the input is required and not supplied
        """
        options = options or InputOptions()
        env_var = f"INPUT_{name.replace(' ', '_').replace('-', '_').upper()}"

        env_options = EnvOptions(required=options.required, trim_whitespace=options.trim_whitespace)

        try:
            return self.get_env(env_var, env_options)
        except ValueError as e:
            # Translate the error message to reference the input name, not the env var
            raise ValueError(f"Input required and not supplied: {name}") from e

    def get_multiline_input(self, name: str, options: InputOptions | None = None) -> list[str]:
        """
        Gets the values of a multiline input.

        Args:
            name: Name of the input to get
            options: Optional. See InputOptions

        Returns:
            list of string values from the multiline input
        """
        options = options or InputOptions()
        inputs = self.get_input(name, options).split("\n")
        inputs = [x for x in inputs if x]

        if not options.trim_whitespace:
            return inputs

        return [input_line.strip() for input_line in inputs]

    def get_boolean_input(self, name: str, options: InputOptions | None = None) -> bool:
        """
        Gets the input value of the boolean type in the YAML 1.2 "core schema" specification.

        Args:
            name: Name of the input to get
            options: Optional. See InputOptions

        Returns:
            Boolean value of the input

        Raises:
            TypeError: If the input is not valid boolean format
        """
        true_values = ["true", "True", "TRUE"]
        false_values = ["false", "False", "FALSE"]
        val = self.get_input(name, options)

        if val.lower() in (v.lower() for v in true_values):
            return True
        if val.lower() in (v.lower() for v in false_values):
            return False

        raise TypeError(
            f"Input does not meet YAML 1.2 'Core Schema' specification: {name}\n"
            + "Support boolean input list: `true | True | TRUE | false | False | FALSE`"
        )

    def set_output(self, name: str, value: str) -> None:
        """
        Sets the value of an output.

        Args:
            name: Name of the output to set
            value: Value to store. Non-string values will be converted to a string via JSON
        """
        file_path = self.get_env("GITHUB_OUTPUT")
        if file_path:
            self._issue_file_command("OUTPUT", self._prepare_key_value_message(name, value))
        else:
            print(os.linesep, end="")
            self._issue_command("set-output", {"name": name}, self._to_command_value(value))

    def set_command_echo(self, enabled: bool) -> None:
        """
        Enables or disables the echoing of commands into stdout.

        Args:
            enabled: True to enable echoing, false to disable
        """
        self._issue("echo", "on" if enabled else "off")

    def set_failed(self, message: str | Exception) -> None:
        """
        Sets the action status to failed.

        Args:
            message: Add error issue message
        """
        self.error(message)
        sys.exit(ExitCode.FAILURE)

    def is_debug(self) -> bool:
        """
        Gets whether Actions Step Debug is on or not.

        Returns:
            True if step debug is enabled
        """
        return self.get_env("RUNNER_DEBUG") == "1"

    def debug(self, message: str) -> None:
        """
        Writes debug message to user log.

        Args:
            message: Debug message
        """
        self._issue_command("debug", {}, message)

    def error(self, message: str | Exception, properties: AnnotationProperties | None = None) -> None:
        """
        Adds an error issue.

        Args:
            message: Error issue message
            properties: Optional properties to add to the annotation
        """
        properties = properties or AnnotationProperties()
        self._issue_command(
            "error",
            self._to_command_properties(properties),
            str(message) if isinstance(message, Exception) else message,
        )

    def warning(self, message: str | Exception, properties: AnnotationProperties | None = None) -> None:
        """
        Adds a warning issue.

        Args:
            message: Warning issue message
            properties: Optional properties to add to the annotation
        """
        properties = properties or AnnotationProperties()
        self._issue_command(
            "warning",
            self._to_command_properties(properties),
            str(message) if isinstance(message, Exception) else message,
        )

    def notice(self, message: str | Exception, properties: AnnotationProperties | None = None) -> None:
        """
        Adds a notice issue.

        Args:
            message: Notice issue message
            properties: Optional properties to add to the annotation
        """
        properties = properties or AnnotationProperties()
        self._issue_command(
            "notice",
            self._to_command_properties(properties),
            str(message) if isinstance(message, Exception) else message,
        )

    def info(self, message: str) -> None:
        """
        Writes info to log with console.log.

        Args:
            message: Info message
        """
        print(f"{message}")

    def start_group(self, name: str) -> None:
        """
        Begin an output group.

        Args:
            name: The name of the output group
        """
        self._issue("group", name)

    def end_group(self) -> None:
        """End an output group."""
        self._issue("endgroup")

    def group(self, name: str, fn: Callable[[], T]) -> T:
        """
        Wrap a function call in a group.

        Args:
            name: The name of the group
            fn: The function to wrap in the group

        Returns:
            The same type as the function itself
        """
        self.start_group(name)

        try:
            result = fn()
        finally:
            self.end_group()

        return result

    def save_state(self, name: str, value: Any) -> None:
        """
        Saves state for current action.

        Args:
            name: Name of the state to store
            value: Value to store. Non-string values will be converted to a string via JSON
        """
        file_path = self.get_env("GITHUB_STATE")
        if file_path:
            self._issue_file_command("STATE", self._prepare_key_value_message(name, value))
        else:
            self._issue_command("save-state", {"name": name}, self._to_command_value(value))

    def get_state(self, name: str) -> str:
        """
        Gets the value of an state set by this action's main execution.

        Args:
            name: Name of the state to get

        Returns:
            String state value
        """
        return self.get_env(f"STATE_{name}")

    def _issue(self, name: str, message: str = "") -> None:
        """
        Issue a command.

        Args:
            name: Command name
            message: Command message
        """
        self._issue_command(name, {}, message)

    def _issue_command(self, command: str, properties: dict[str, Any], message: Any) -> None:
        """
        Issue a command to the GitHub Actions runner.

        Args:
            command: The command name
            properties: Additional properties
            message: The message to include
        """
        cmd_str = f"::{command}"

        if properties and len(properties) > 0:
            cmd_str += " "
            first = True
            for key, val in properties.items():
                if val:
                    if first:
                        first = False
                    else:
                        cmd_str += ","

                    cmd_str += f"{key}={self._escape_property(val)}"

        cmd_str += f"::{self._escape_data(message)}"
        print(cmd_str)

    def _issue_file_command(self, command: str, message: Any) -> None:
        """
        Issue a file command.

        Args:
            command: The command name
            message: The message to include

        Raises:
            ValueError: If the environment variable for the command is not found
            FileNotFoundError: If the file path doesn't exist
        """
        file_path = self.get_env(f"GITHUB_{command}")
        if not file_path:
            raise ValueError(f"Unable to find environment variable for file command {command}")

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Missing file at path: {file_path}")

        with open(file_path, "a", encoding="utf-8") as f:
            _ = f.write(f"{self._to_command_value(message)}{os.linesep}")

    def _prepare_key_value_message(self, key: str, value: Any) -> str:
        """
        Prepare key value message for file command.

        Args:
            key: The key
            value: The value

        Returns:
            Formatted key-value message

        Raises:
            ValueError: If key or value contains delimiter
        """
        delimiter = f"ghadelimiter_{uuid.uuid4()}"
        converted_value = self._to_command_value(value)

        if delimiter in key:
            raise ValueError(f'Unexpected input: name should not contain the delimiter "{delimiter}"')

        if delimiter in converted_value:
            raise ValueError(f'Unexpected input: value should not contain the delimiter "{delimiter}"')

        return f"{key}<<{delimiter}{os.linesep}{converted_value}{os.linesep}{delimiter}"

    def _to_command_value(self, input_value: Any) -> str:
        """
        Convert an input value to a string.

        Args:
            input_value: Input to sanitize to a string

        Returns:
            String value
        """
        if input_value is None:
            return ""
        elif isinstance(input_value, str):
            return input_value
        return json.dumps(input_value)

    def _to_command_properties(self, annotation_properties: AnnotationProperties) -> dict[str, Any]:
        """
        Convert annotation properties to command properties.

        Args:
            annotation_properties: The annotation properties

        Returns:
            Command properties dictionary
        """
        properties = {}
        prop_dict = vars(annotation_properties)

        if not prop_dict:
            return properties

        # Map annotation properties to command properties
        mapping = {
            "title": "title",
            "file": "file",
            "start_line": "line",
            "end_line": "endLine",
            "start_column": "col",
            "end_column": "endColumn",
        }

        for ann_prop, cmd_prop in mapping.items():
            if prop_dict.get(ann_prop) is not None:
                properties[cmd_prop] = prop_dict[ann_prop]

        return properties

    def _escape_data(self, s: Any) -> str:
        """
        Escape data for command.

        Args:
            s: Data to escape

        Returns:
            Escaped string
        """
        return self._to_command_value(s).replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")

    def _escape_property(self, s: Any) -> str:
        """
        Escape property for command.

        Args:
            s: Property to escape

        Returns:
            Escaped string
        """
        return (
            self._to_command_value(s)
            .replace("%", "%25")
            .replace("\r", "%0D")
            .replace("\n", "%0A")
            .replace(":", "%3A")
            .replace(",", "%2C")
        )
