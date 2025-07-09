# Prompt-toolkit based input handler for Songbird commands with message history support.


import os
from pathlib import Path
from typing import Optional, List, Dict, Any
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.history import History
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.filters import Condition
from prompt_toolkit.application import get_app
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.styles import Style
from rich.console import Console
from rich.table import Table

from .base import BaseCommand
from .registry import CommandRegistry
from ..memory.history_manager import MessageHistoryManager
from .file_reference_parser import FileReferenceParser


class SongbirdHistory(History):
    # Custom history adapter that bridges prompt-toolkit with MessageHistoryManager.
    
    def __init__(self, history_manager: MessageHistoryManager):
        super().__init__()
        self.history_manager = history_manager
        self._history_strings: Optional[List[str]] = None
        self._loaded = False
    
    def load_history_strings(self) -> List[str]:
        if self._history_strings is None:
            self.history_manager._history_cache = None
            messages = self.history_manager._load_project_user_messages()
            self._history_strings = messages
            self._loaded = True
        return self._history_strings
    
    async def load(self):
        if not self._loaded:
            self.load_history_strings()
        
        for item in self._history_strings or []:
            yield item
    
    def get_strings(self) -> List[str]:
        return self.load_history_strings()
    
    def append_string(self, string: str) -> None:
        self.history_manager.invalidate_cache()
        self._history_strings = None
        
    def store_string(self, string: str) -> None:
        self.append_string(string)
    
    def __getitem__(self, index: int) -> str:
        strings = self.load_history_strings()
        try:
            return strings[index]
        except IndexError:
            return ""
    
    def __len__(self) -> int:
        return len(self.load_history_strings())


class SongbirdCompleter(Completer):
    # Enhanced completer for Songbird commands and file references.
    
    def __init__(self, registry: CommandRegistry, working_directory: Optional[str] = None):
        self.registry = registry
        self.working_directory = Path(working_directory or os.getcwd()).resolve()
        self.file_parser = FileReferenceParser(str(self.working_directory))
    
    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        
        if '@' in text:
            last_at_index = text.rfind('@')
            if last_at_index >= 0:
                after_at = text[last_at_index + 1:]
                
                # Only complete if there's no space after @
                if ' ' not in after_at:
                    yield from self._get_file_completions(after_at, last_at_index + 1)
                    return

        if text.startswith('/') and ' ' not in text:
            command_part = text[1:].lower() 
            
            for command in self.registry.get_all_commands():
                if command.name.lower().startswith(command_part):
                    yield Completion(
                        command.name,
                        start_position=-len(command_part),
                        display=f"/{command.name}",
                        display_meta=command.description
                    )
                
                for alias in command.aliases:
                    if alias.lower().startswith(command_part):
                        yield Completion(
                            alias,
                            start_position=-len(command_part),
                            display=f"/{alias}",
                            display_meta=f"{command.description} (alias for /{command.name})"
                        )
    
    def _get_file_completions(self, partial_path: str, start_position: int):
        try:
            partial_path = partial_path.strip()
            
            if partial_path.startswith('"'):
                partial_path = partial_path[1:]
                quote_offset = 1
            else:
                quote_offset = 0
            
            if '/' in partial_path:
                path_parts = partial_path.split('/')
                if partial_path.endswith('/'):
                    search_dir = Path('/'.join(path_parts[:-1])) if len(path_parts) > 1 else Path(path_parts[0])
                    filename_pattern = ""
                else:
                    search_dir = Path('/'.join(path_parts[:-1])) if len(path_parts) > 1 else Path('.')
                    filename_pattern = path_parts[-1]
            else:
                search_dir = Path('.')
                filename_pattern = partial_path
            
            if search_dir.is_absolute():
                return
            
            try:
                resolved_search_dir = (self.working_directory / search_dir).resolve()
                resolved_search_dir.relative_to(self.working_directory)
            except (ValueError, OSError):
                return
            
            if not resolved_search_dir.exists() or not resolved_search_dir.is_dir():
                return
            
            matches = []
            try:
                for item in resolved_search_dir.iterdir():
                    item_name = item.name
                    
                    if item_name.startswith('.') and not filename_pattern.startswith('.'):
                        continue
                    
                    if item_name.lower().startswith(filename_pattern.lower()):
                        try:
                            rel_path = item.relative_to(self.working_directory)
                            display_path = str(rel_path)
                        except ValueError:
                            display_path = item_name
                        
                        if search_dir == Path('.'):
                            insert_text = item_name
                        else:
                            insert_text = f"{search_dir}/{item_name}"
                        
                        if item.is_dir():
                            display_text = f"{display_path}/"
                            insert_text += "/"
                        else:
                            display_text = display_path
                        
                        matches.append((insert_text, display_text))
            except (PermissionError, OSError):
                return
            
            for insert_text, display_text in sorted(matches):
                replace_length = len(partial_path) + quote_offset
                
                yield Completion(
                    insert_text,
                    start_position=-replace_length,
                    display=f"@{display_text}"
                )
        
        except Exception:
            pass


class PromptToolkitInputHandler:
    # input handler using prompt-toolkit with message history support.

    def __init__(self, registry: CommandRegistry, console: Console, history_manager: Optional[MessageHistoryManager] = None):
        self.registry = registry
        self.console = console
        self.history_manager = history_manager
        self.show_model_in_prompt = False 
        self.session: PromptSession 
        
        self._create_session()
    
    def _create_session(self):
        history = None
        if self.history_manager:
            history = SongbirdHistory(self.history_manager)
        
        completer = SongbirdCompleter(self.registry)
        
        kb = self._create_key_bindings()
        
        transparent_style = Style.from_dict({
            'completion-menu': 'noinherit',
            'completion-menu.completion': 'noinherit',
            'completion-menu.completion.current': 'reverse',
            'completion-menu.meta': 'noinherit',
            'completion-menu.meta.current': 'noinherit',
            'completion-menu.multi-column-meta': 'noinherit',
        })
        
        self.session = PromptSession(
            history=history,
            completer=completer,
            key_bindings=kb,
            complete_while_typing=False,
            enable_history_search=True,
            search_ignore_case=True,
            style=transparent_style,
        )
    
    
    def _create_key_bindings(self) -> KeyBindings:
        kb = KeyBindings()
        
        @kb.add('?', filter=Condition(lambda: self._should_show_help()))
        def show_help_on_question_mark(event):
            app = event.app
            buffer = app.current_buffer
            
            if buffer.text == '?':
                buffer.delete_before_cursor(1)
                self._show_commands()
        
        return kb
    
    def _should_show_help(self) -> bool:
        app = get_app()
        if app and app.current_buffer:
            return app.current_buffer.text == '?'
        return False

    async def get_input_with_commands(self, prompt: str = "You", context: Optional[Dict[str, Any]] = None) -> str:

        if self.show_model_in_prompt and context:
            model = context.get('model', '')
            if model:
                model_short = model.split(':')[0] if ':' in model else model
                prompt_text = f"{prompt} [{model_short}]"
            else:
                prompt_text = prompt
        else:
            prompt_text = prompt

        try:
    
            colored_prompt = HTML(f'<b><ansicyan>{prompt_text}:</ansicyan></b> ')
            user_input = await self.session.prompt_async(colored_prompt)
        except KeyboardInterrupt:
            raise
        except EOFError:
            return "exit"
        
        if user_input == "/":
            self._show_commands()
            return ""

        elif user_input.startswith("/") and " " not in user_input:
            cmd_name = user_input[1:].lower()
            command = self._find_command(cmd_name)

            if command:
                return f"/{command.name}"
            else:
                self.console.print(f"[red]Unknown command: {user_input}[/red]")
                self.console.print("Available commands:")
                self._show_commands()
                return ""

        return user_input

    def _find_command(self, name: str) -> Optional[BaseCommand]:
        for cmd in self.registry.get_all_commands():
            if cmd.name.lower() == name or name in [a.lower() for a in cmd.aliases]:
                return cmd
        return None

    def _show_commands(self):
        commands = self.registry.get_all_commands()

        if not commands:
            self.console.print("[yellow]No commands available[/yellow]")
            return

        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Command", style="cornflower_blue")
        table.add_column("Description", style="dim")

        for cmd in sorted(commands, key=lambda x: x.name):
            cmd_text = f"/{cmd.name}"
            if cmd.aliases:
                aliases = ", ".join(f"/{a}" for a in cmd.aliases[:2])
                cmd_text = f"{cmd_text} ({aliases})"

            table.add_row(cmd_text, cmd.description)

        self.console.print()
        self.console.print(table)
        self.console.print(
            "\n[dim]Type [spring_green1]/help[/spring_green1] for detailed command information[/dim]")

    def invalidate_history_cache(self):
        if self.history_manager:
            self.history_manager.invalidate_cache()
            if hasattr(self.session, 'history') and isinstance(self.session.history, SongbirdHistory):
                self.session.history._history_strings = None
                self.session.history._loaded = False
class KeyCodes:
    """Key codes for compatibility."""
    UP = 'UP'
    DOWN = 'DOWN'
    ENTER = 'ENTER'
    ESCAPE = 'ESCAPE'
    CTRL_C = 'CTRL_C'


def show_status_line(console: Console, provider: str, model: str):
    """Show a status line with current provider and model."""
    # Extract model name for display
    model_display = model.split(':')[0] if ':' in model else model
    status = f"[dim][ {provider} | {model_display} ][/dim]"
    console.print(status, justify="right")