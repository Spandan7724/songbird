# songbird/tools/multiedit_tool.py
"""
MultiEdit tool for atomic multi-file editing operations.

"""
import os
import tempfile
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
import difflib

console = Console()


async def multi_edit(
    edits: List[Dict[str, Any]],
    create_backup: bool = False,
    preview_only: bool = False,
    atomic: bool = True
) -> Dict[str, Any]:
    """
    Perform multiple file edits in a single atomic operation.
    
    Args:
        edits: List of edit operations, each containing:
               {
                   "file_path": str,
                   "new_content": str,
                   "operation": "edit|create|delete" (default: "edit"),
                   "encoding": str (default: "utf-8")
               }
        create_backup: Whether to create backup files (default: True)
        preview_only: Whether to only show previews without applying (default: False)
        atomic: Whether to apply all edits atomically (default: True)
        
    Returns:
        Dictionary with operation results and previews
    """
    try:
        console.print(f"\n[bold cyan]Multi-file edit operation:[/bold cyan] {len(edits)} files")
        
        # Validate and prepare edits
        prepared_edits = []
        validation_errors = []
        
        for i, edit in enumerate(edits):
            try:
                prepared_edit = await _prepare_edit(edit, i)
                prepared_edits.append(prepared_edit)
            except Exception as e:
                validation_errors.append(f"Edit {i + 1}: {e}")
        
        if validation_errors:
            return {
                "success": False,
                "error": f"Validation failed: {'; '.join(validation_errors)}",
                "validation_errors": validation_errors
            }
        
        # Generate previews for all edits
        previews = []
        for edit in prepared_edits:
            preview = await _generate_edit_preview(edit)
            previews.append(preview)
        
        # Display all previews
        _display_multi_edit_preview(previews)
        
        if preview_only:
            return {
                "success": True,
                "preview_only": True,
                "previews": previews,
                "total_edits": len(prepared_edits),
                "display_shown": True
            }
        
        # Ask for confirmation if not in auto-apply mode
        import os
        if os.getenv("SONGBIRD_AUTO_APPLY") != "y":
            from ..conversation import safe_interactive_menu
            
            selected_index = await safe_interactive_menu(
                "Apply all these changes?",
                ["Yes, apply all changes", "No, cancel operation"],
                default_index=0
            )
            
            if selected_index is None or selected_index != 0:
                return {
                    "success": False,
                    "message": "Operation cancelled by user",
                    "previews": previews
                }
        
        # Apply edits
        if atomic:
            result = await _apply_edits_atomic(prepared_edits, create_backup)
        else:
            result = await _apply_edits_sequential(prepared_edits, create_backup)
        
        result["previews"] = previews
        result["display_shown"] = True
        
        return result
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Multi-edit operation failed: {e}",
            "previews": []
        }


async def _prepare_edit(edit: Dict[str, Any], index: int) -> Dict[str, Any]:
    """Prepare and validate a single edit operation."""
    
    # Required fields
    if "file_path" not in edit:
        raise ValueError("Missing required field 'file_path'")
    
    file_path = Path(edit["file_path"]).resolve()
    operation = edit.get("operation", "edit")
    encoding = edit.get("encoding", "utf-8")
    
    # Validate operation type
    valid_operations = ["edit", "create", "delete"]
    if operation not in valid_operations:
        raise ValueError(f"Invalid operation '{operation}', must be one of: {valid_operations}")
    
    # For edit/create operations, content is required
    if operation in ["edit", "create"] and "new_content" not in edit:
        raise ValueError(f"Missing required field 'new_content' for {operation} operation")
    
    # Prepare the edit
    prepared = {
        "file_path": file_path,
        "operation": operation,
        "encoding": encoding,
        "index": index
    }
    
    if operation in ["edit", "create"]:
        prepared["new_content"] = edit["new_content"]
    
    # Read existing content for edit operations
    if operation == "edit":
        if not file_path.exists():
            raise ValueError(f"File does not exist for edit operation: {file_path}")
        
        if not file_path.is_file():
            raise ValueError(f"Path is not a file: {file_path}")
        
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                prepared["old_content"] = f.read()
        except UnicodeDecodeError:
            raise ValueError(f"Cannot read file with encoding {encoding}: {file_path}")
    
    elif operation == "create":
        if file_path.exists():
            raise ValueError(f"File already exists for create operation: {file_path}")
        prepared["old_content"] = ""
    
    elif operation == "delete":
        if not file_path.exists():
            raise ValueError(f"File does not exist for delete operation: {file_path}")
        
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                prepared["old_content"] = f.read()
        except UnicodeDecodeError:
            prepared["old_content"] = "<binary file>"
        
        prepared["new_content"] = ""
    
    return prepared


async def _generate_edit_preview(edit: Dict[str, Any]) -> Dict[str, Any]:
    """Generate preview for a single edit operation."""
    
    operation = edit["operation"]
    file_path = edit["file_path"]
    
    preview = {
        "file_path": str(file_path),
        "operation": operation,
        "index": edit["index"]
    }
    
    if operation == "create":
        preview["preview_type"] = "creation"
        preview["content"] = edit["new_content"]
        preview["lines_added"] = len(edit["new_content"].splitlines())
        
    elif operation == "delete":
        preview["preview_type"] = "deletion"
        preview["content"] = edit["old_content"]
        preview["lines_removed"] = len(edit["old_content"].splitlines())
        
    elif operation == "edit":
        preview["preview_type"] = "modification"
        
        # Generate diff
        old_lines = edit["old_content"].splitlines(keepends=True)
        new_lines = edit["new_content"].splitlines(keepends=True)
        
        diff_lines = list(difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=f"a/{file_path.name}",
            tofile=f"b/{file_path.name}",
            lineterm=""
        ))
        
        preview["diff"] = '\n'.join(diff_lines)
        preview["has_changes"] = len(diff_lines) > 0
        
        # Count changes
        preview["lines_added"] = len([line for line in diff_lines if line.startswith('+')])
        preview["lines_removed"] = len([line for line in diff_lines if line.startswith('-')])
    
    return preview


def _display_multi_edit_preview(previews: List[Dict[str, Any]]):
    """Display previews for all edit operations."""
    
    if not previews:
        console.print("[dim]No edits to preview[/dim]")
        return
    
    console.print(f"\n[bold]Preview of {len(previews)} file operations:[/bold]")
    
    for preview in previews:
        _display_single_edit_preview(preview)


def _display_single_edit_preview(preview: Dict[str, Any]):
    """Display preview for a single edit operation."""
    
    file_path = preview["file_path"]
    operation = preview["operation"]
    
    # Operation-specific display
    if operation == "create":
        console.print(f"\n[bold green]CREATE:[/bold green] {file_path}")
        console.print(f"[dim]Lines to add: {preview['lines_added']}[/dim]")
        
        # Show content preview
        content = preview["content"]
        if len(content) > 500:
            content_preview = content[:500] + "\n... (truncated)"
        else:
            content_preview = content
        
        syntax = Syntax(
            content_preview,
            lexer=_get_lexer_from_filename(file_path),
            theme="github-dark",
            line_numbers=True,
            word_wrap=False
        )
        panel = Panel(
            syntax,
            title=f"New content: {Path(file_path).name}",
            border_style="green",
            padding=(0, 1)
        )
        console.print(panel)
        
    elif operation == "delete":
        console.print(f"\n[bold red] DELETE:[/bold red] {file_path}")
        console.print(f"[dim]Lines to remove: {preview['lines_removed']}[/dim]")
        
        console.print("[yellow]This file will be permanently deleted![/yellow]")
        
    elif operation == "edit":
        console.print(f"\n[bold blue]EDIT:[/bold blue] {file_path}")
        
        if not preview["has_changes"]:
            console.print("[dim]No changes detected[/dim]")
            return
        
        console.print(f"[dim]Lines +{preview['lines_added']} -{preview['lines_removed']}[/dim]")
        
        # Show diff
        diff_content = preview["diff"]
        if diff_content:
            syntax = Syntax(
                diff_content,
                "diff",
                theme="github-dark",
                line_numbers=False,
                word_wrap=False
            )
            panel = Panel(
                syntax,
                title=f"Changes to {Path(file_path).name}",
                border_style="blue",
                padding=(0, 1)
            )
            console.print(panel)


async def _apply_edits_atomic(edits: List[Dict[str, Any]], create_backup: bool) -> Dict[str, Any]:
    """Apply edits atomically using temporary files."""
    
    console.print("\n[bold]Applying changes atomically...[/bold]")
    
    temp_files = {}
    backup_files = {}
    applied_edits = []
    
    try:
        # Phase 1: Prepare all changes in temporary files
        for edit in edits:
            file_path = edit["file_path"]
            operation = edit["operation"]
            
            if operation == "delete":
                # For delete, just mark for deletion
                if create_backup and file_path.exists():
                    backup_path = file_path.with_suffix(file_path.suffix + '.bak')
                    backup_files[str(file_path)] = backup_path
                continue
            
            # Create temporary file
            temp_fd, temp_path = tempfile.mkstemp(
                suffix=file_path.suffix,
                prefix=f"songbird_edit_{file_path.name}_"
            )
            
            try:
                with os.fdopen(temp_fd, 'w', encoding=edit["encoding"]) as temp_file:
                    temp_file.write(edit["new_content"])
                
                temp_files[str(file_path)] = temp_path
                
                # Create backup if needed
                if create_backup and file_path.exists():
                    backup_path = file_path.with_suffix(file_path.suffix + '.bak')
                    backup_files[str(file_path)] = backup_path
                    
            except Exception:
                # Clean up temp file on error
                os.unlink(temp_path)
                raise
        
        # Phase 2: Create backups
        if create_backup:
            for original_path, backup_path in backup_files.items():
                try:
                    shutil.copy2(original_path, backup_path)
                except Exception as e:
                    # Rollback on backup failure
                    await _rollback_atomic_operation(temp_files, backup_files, applied_edits)
                    raise Exception(f"Backup failed for {original_path}: {e}")
        
        # Phase 3: Apply all changes atomically
        for edit in edits:
            file_path = edit["file_path"]
            operation = edit["operation"]
            
            try:
                if operation == "delete":
                    if file_path.exists():
                        file_path.unlink()
                        applied_edits.append(f"Deleted {file_path}")
                
                elif operation in ["edit", "create"]:
                    temp_path = temp_files[str(file_path)]
                    
                    # Ensure parent directory exists
                    file_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    # Atomic move
                    shutil.move(temp_path, str(file_path))
                    temp_files.pop(str(file_path))  # Remove from temp tracking
                    
                    applied_edits.append(f"{operation.title()}d {file_path}")
                    
            except Exception as e:
                # Rollback on any failure
                await _rollback_atomic_operation(temp_files, backup_files, applied_edits)
                raise Exception(f"Failed to apply {operation} to {file_path}: {e}")
        
        # Clean up remaining temp files
        for temp_path in temp_files.values():
            try:
                os.unlink(temp_path)
            except Exception:
                pass
        
        console.print(f"[bold green]Successfully applied {len(edits)} changes[/bold green]")
        
        return {
            "success": True,
            "message": f"Successfully applied {len(edits)} changes atomically",
            "applied_edits": applied_edits,
            "backup_files": list(backup_files.values()) if create_backup else [],
            "atomic": True
        }
        
    except Exception as e:
        console.print(f"[bold red]Atomic operation failed: {e}[/bold red]")
        
        return {
            "success": False,
            "error": f"Atomic operation failed: {e}",
            "applied_edits": applied_edits,
            "rollback_attempted": True
        }


async def _apply_edits_sequential(edits: List[Dict[str, Any]], create_backup: bool) -> Dict[str, Any]:
    """Apply edits sequentially (non-atomic)."""
    
    console.print("\n[bold]Applying changes sequentially...[/bold]")
    
    applied_edits = []
    failed_edits = []
    backup_files = []
    
    for edit in edits:
        file_path = edit["file_path"]
        operation = edit["operation"]
        
        try:
            # Create backup if needed
            if create_backup and file_path.exists():
                backup_path = file_path.with_suffix(file_path.suffix + '.bak')
                shutil.copy2(file_path, backup_path)
                backup_files.append(str(backup_path))
            
            # Apply the edit
            if operation == "delete":
                if file_path.exists():
                    file_path.unlink()
                    applied_edits.append(f"Deleted {file_path}")
            
            elif operation == "create":
                # Ensure parent directory exists
                file_path.parent.mkdir(parents=True, exist_ok=True)
                
                with open(file_path, 'w', encoding=edit["encoding"]) as f:
                    f.write(edit["new_content"])
                
                applied_edits.append(f"Created {file_path}")
            
            elif operation == "edit":
                with open(file_path, 'w', encoding=edit["encoding"]) as f:
                    f.write(edit["new_content"])
                
                applied_edits.append(f"Edited {file_path}")
            
            console.print(f"[green]{operation.title()}d {file_path.name}[/green]")
            
        except Exception as e:
            error_msg = f"Failed {operation} on {file_path}: {e}"
            failed_edits.append(error_msg)
            console.print(f"[red]{error_msg}[/red]")
    
    # Summary
    success_count = len(applied_edits)
    failure_count = len(failed_edits)
    
    if failure_count == 0:
        console.print(f"[bold green]Successfully applied all {success_count} changes[/bold green]")
        success = True
        message = f"Successfully applied all {success_count} changes"
    else:
        console.print(f"[bold yellow]Applied {success_count} changes, {failure_count} failed[/bold yellow]")
        success = False
        message = f"Applied {success_count} changes, {failure_count} failed"
    
    return {
        "success": success,
        "message": message,
        "applied_edits": applied_edits,
        "failed_edits": failed_edits,
        "backup_files": backup_files,
        "atomic": False
    }


async def _rollback_atomic_operation(temp_files: Dict[str, str], backup_files: Dict[str, str], applied_edits: List[str]):
    """Rollback a failed atomic operation."""
    
    console.print("\n[yellow]Rolling back failed atomic operation...[/yellow]")
    
    # Remove any temp files
    for temp_path in temp_files.values():
        try:
            os.unlink(temp_path)
        except Exception:
            pass
    
    # Restore from backups if any changes were applied
    for original_path, backup_path in backup_files.items():
        try:
            if Path(backup_path).exists():
                shutil.copy2(backup_path, original_path)
                console.print(f"[dim]Restored {original_path} from backup[/dim]")
        except Exception:
            pass


def _get_lexer_from_filename(filename: str) -> str:
    """Get appropriate lexer based on file extension."""
    ext = Path(filename).suffix.lower()
    lexer_map = {
        '.py': 'python',
        '.js': 'javascript',
        '.ts': 'typescript',
        '.jsx': 'jsx',
        '.tsx': 'tsx',
        '.java': 'java',
        '.c': 'c',
        '.cpp': 'cpp',
        '.cs': 'csharp',
        '.go': 'go',
        '.rs': 'rust',
        '.php': 'php',
        '.rb': 'ruby',
        '.swift': 'swift',
        '.kt': 'kotlin',
        '.scala': 'scala',
        '.yaml': 'yaml',
        '.yml': 'yaml',
        '.json': 'json',
        '.xml': 'xml',
        '.html': 'html',
        '.css': 'css',
        '.md': 'markdown',
        '.sql': 'sql',
        '.sh': 'bash',
        '.ps1': 'powershell',
        '.dockerfile': 'docker',
        '.toml': 'toml',
        '.ini': 'ini',
    }
    return lexer_map.get(ext, 'text')


# Additional utility functions

async def multi_edit_pattern(
    pattern: str,
    replacement: str,
    file_patterns: List[str],
    directory: str = ".",
    regex: bool = False,
    case_sensitive: bool = False,
    preview_only: bool = True
) -> Dict[str, Any]:
    """
    Apply a find/replace pattern across multiple files.
    
    Args:
        pattern: Text pattern to find
        replacement: Replacement text
        file_patterns: List of file patterns to search (e.g., ["*.py", "*.js"])
        directory: Directory to search in
        regex: Whether pattern is regex
        case_sensitive: Whether search is case sensitive
        preview_only: Whether to only preview changes
        
    Returns:
        Dictionary with operation results
    """
    from .glob_tool import glob_pattern
    
    # Find files matching patterns
    all_files = []
    for file_pattern in file_patterns:
        glob_result = await glob_pattern(file_pattern, directory)
        if glob_result["success"]:
            all_files.extend([match["absolute_path"] for match in glob_result["matches"] if match["is_file"]])
    
    # Remove duplicates
    all_files = list(set(all_files))
    
    if not all_files:
        return {
            "success": False,
            "error": "No files found matching the specified patterns",
            "files_found": 0
        }
    
    # Find files with matches
    edits = []
    for file_path in all_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Apply replacement
            if regex:
                import re
                flags = 0 if case_sensitive else re.IGNORECASE
                new_content = re.sub(pattern, replacement, content, flags=flags)
            else:
                if case_sensitive:
                    new_content = content.replace(pattern, replacement)
                else:
                    # Case-insensitive replacement
                    import re
                    new_content = re.sub(re.escape(pattern), replacement, content, flags=re.IGNORECASE)
            
            # Only include files with changes
            if new_content != content:
                edits.append({
                    "file_path": file_path,
                    "new_content": new_content,
                    "operation": "edit"
                })
                
        except Exception:
            continue  # Skip files that can't be read
    
    if not edits:
        return {
            "success": True,
            "message": f"No changes needed - pattern '{pattern}' not found in any files",
            "files_searched": len(all_files),
            "files_with_changes": 0
        }
    
    # Apply multi-edit
    return await multi_edit(edits, preview_only=preview_only)


async def multi_create_from_template(
    template_path: str,
    target_files: List[Dict[str, Any]],
    variables: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """
    Create multiple files from a template with variable substitution.
    
    Args:
        template_path: Path to template file
        target_files: List of target files with structure:
                     [{"path": "target/path", "variables": {"VAR": "value"}}]
        variables: Global variables to substitute in template
        
    Returns:
        Dictionary with creation results
    """
    # Read template
    template_file = Path(template_path)
    if not template_file.exists():
        return {
            "success": False,
            "error": f"Template file not found: {template_path}"
        }
    
    try:
        with open(template_file, 'r', encoding='utf-8') as f:
            template_content = f.read()
    except Exception as e:
        return {
            "success": False,
            "error": f"Cannot read template file: {e}"
        }
    
    # Prepare edits
    edits = []
    for target in target_files:
        target_path = target["path"]
        target_variables = target.get("variables", {})
        
        # Combine global and target-specific variables
        all_variables = {**(variables or {}), **target_variables}
        
        # Substitute variables in template
        content = template_content
        for var, value in all_variables.items():
            content = content.replace(f"{{{{{var}}}}}", value)
        
        edits.append({
            "file_path": target_path,
            "new_content": content,
            "operation": "create"
        })
    
    # Apply multi-edit
    return await multi_edit(edits)