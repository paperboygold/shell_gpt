import os
import platform
import shlex
import re
from tempfile import NamedTemporaryFile
from typing import Any, Callable

import typer
from click import BadParameter, UsageError

from sgpt.__version__ import __version__
from sgpt.integration import bash_integration, zsh_integration


def sanitize_command(command: str) -> str:
    """
    Remove any chain-of-thought markers and content from the command string.
    """
    return re.sub(r'<think>.*?</think>', '', command, flags=re.DOTALL).strip()


def get_edited_prompt() -> str:
    """
    Opens the user's default editor to let them
    input a prompt, and returns the edited text.

    :return: String prompt.
    """
    with NamedTemporaryFile(suffix=".txt", delete=False) as file:
        # Create file and store path.
        file_path = file.name
    editor = os.environ.get("EDITOR", "vim")
    # This will write text to file using $EDITOR.
    os.system(f"{editor} {file_path}")
    # Read file when editor is closed.
    with open(file_path, "r", encoding="utf-8") as file:
        output = file.read()
    os.remove(file_path)
    if not output:
        raise BadParameter("Couldn't get valid PROMPT from $EDITOR")
    return output


def run_command(command: str) -> None:
    """
    Runs a command in the user's shell.
    It is aware of the current user's $SHELL.
    :param command: A shell command to run.
    """
    # Sanitize the command by removing any chain-of-thought content
    command = sanitize_command(command)
    
    # Extract code block content if present
    code_block_match = re.search(r'```(?:bash)?\s*(.*?)\s*```', command, flags=re.DOTALL)
    if code_block_match:
        command = code_block_match.group(1)
    
    # Split multiple commands and check if they exist
    commands = command.split('\n')
    filtered_commands = []
    
    for cmd in commands:
        # Skip empty lines
        if not cmd.strip():
            continue
            
        # Get the base command (before any arguments or pipes)
        base_cmd = cmd.split('|')[0].strip().split()[0]
        
        # Check if command exists using 'which'
        if platform.system() != "Windows":
            check_cmd = f"which {base_cmd} >/dev/null 2>&1"
            if os.system(check_cmd) == 0:
                filtered_commands.append(cmd)
            else:
                typer.secho(f"Command not found: {base_cmd}", fg="yellow", err=True)
        else:
            # On Windows, we'll add the command anyway since checking is more complex
            filtered_commands.append(cmd)
    
    if not filtered_commands:
        typer.secho("No valid commands to execute", fg="red", err=True)
        return
        
    # Join valid commands and execute
    if platform.system() == "Windows":
        is_powershell = len(os.getenv("PSModulePath", "").split(os.pathsep)) >= 3
        full_command = (
            f'powershell.exe -Command "{"; ".join(filtered_commands)}"'
            if is_powershell
            else f'cmd.exe /c "{" && ".join(filtered_commands)}"'
        )
    else:
        shell = os.environ.get("SHELL", "/bin/sh")
        full_command = f"{shell} -c {shlex.quote('; '.join(filtered_commands))}"

    os.system(full_command)


def option_callback(func: Callable) -> Callable:  # type: ignore
    def wrapper(cls: Any, value: str) -> None:
        if not value:
            return
        func(cls, value)
        raise typer.Exit()

    return wrapper


@option_callback
def install_shell_integration(*_args: Any) -> None:
    """
    Installs shell integration. Currently only supports ZSH and Bash.
    Allows user to get shell completions in terminal by using hotkey.
    Replaces current "buffer" of the shell with the completion.
    """
    # TODO: Add support for Windows.
    # TODO: Implement updates.
    shell = os.environ.get("SHELL", "")
    if "zsh" in shell:
        typer.echo("Installing ZSH integration...")
        with open(os.path.expanduser("~/.zshrc"), "a", encoding="utf-8") as file:
            file.write(zsh_integration)
    elif "bash" in shell:
        typer.echo("Installing Bash integration...")
        with open(os.path.expanduser("~/.bashrc"), "a", encoding="utf-8") as file:
            file.write(bash_integration)
    else:
        raise UsageError("ShellGPT integrations only available for ZSH and Bash.")

    typer.echo("Done! Restart your shell to apply changes.")


@option_callback
def get_sgpt_version(*_args: Any) -> None:
    """
    Displays the current installed version of ShellGPT
    """
    typer.echo(f"ShellGPT {__version__}")
