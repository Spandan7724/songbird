# Context manager for handling file references and injecting file content into LLM context..


import os
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass

from ..commands.file_reference_parser import FileReferenceParser, FileReference
from ..tools.file_operations import file_read


@dataclass
class FileContext:
    file_path: str
    relative_path: str
    content: str
    line_count: int
    size_bytes: int
    error: Optional[str] = None


class FileContextManager:
    def __init__(self, working_directory: Optional[str] = None, max_file_size: int = 100_000):
        self.working_directory = Path(working_directory or os.getcwd()).resolve()
        self.max_file_size = max_file_size
        self.parser = FileReferenceParser(str(self.working_directory))
    
    async def process_message_with_file_context(self, message: str) -> tuple[str, List[FileContext]]:
        file_refs = self.parser.parse_message(message)
        
        if not file_refs:
            return message, []
        
        file_contexts = []
        for ref in file_refs:
            if ref.exists and ref.resolved_path:
                context = await self._read_file_context(ref)
                if context:
                    file_contexts.append(context)
        
        if file_contexts:
            enhanced_message = self._build_enhanced_message(message, file_contexts)
            return enhanced_message, file_contexts
        
        return message, []
    
    async def _read_file_context(self, file_ref: FileReference) -> Optional[FileContext]:
        try:
            file_path = file_ref.resolved_path
            
            file_size = file_path.stat().st_size
            if file_size > self.max_file_size:
                return FileContext(
                    file_path=str(file_path),
                    relative_path=file_ref.file_path,
                    content="",
                    line_count=0,
                    size_bytes=file_size,
                    error=f"File too large ({file_size} bytes, max {self.max_file_size})"
                )
            
            result = await file_read(str(file_path))
            
            if result.get("success"):
                content = result.get("content", "")
                line_count = len(content.splitlines()) if content else 0
                
                return FileContext(
                    file_path=str(file_path),
                    relative_path=file_ref.file_path,
                    content=content,
                    line_count=line_count,
                    size_bytes=file_size
                )
            else:
                error_msg = result.get("error", "Unknown error reading file")
                return FileContext(
                    file_path=str(file_path),
                    relative_path=file_ref.file_path,
                    content="",
                    line_count=0,
                    size_bytes=file_size,
                    error=error_msg
                )
        
        except Exception as e:
            return FileContext(
                file_path=str(file_ref.resolved_path) if file_ref.resolved_path else file_ref.file_path,
                relative_path=file_ref.file_path,
                content="",
                line_count=0,
                size_bytes=0,
                error=f"Error reading file: {str(e)}"
            )
    
    def _build_enhanced_message(self, original_message: str, file_contexts: List[FileContext]) -> str:
        clean_message = self.parser.remove_file_references(original_message)
        
        context_sections = []
        for ctx in file_contexts:
            if ctx.error:
                context_sections.append(
                    f"=== {ctx.relative_path} ===\n"
                    f"Error: {ctx.error}\n"
                )
            else:
                file_ext = Path(ctx.relative_path).suffix.lower()
                lang_hint = self._get_language_hint(file_ext)
                
                context_sections.append(
                    f"=== {ctx.relative_path} ===\n"
                    f"```{lang_hint}\n"
                    f"{ctx.content}\n"
                    f"```\n"
                )
        
        if context_sections:
            context_block = "\n".join(context_sections)
            enhanced_message = (
                f"Here are the referenced files for context:\n\n"
                f"{context_block}\n"
                f"User Request: {clean_message}"
            )
        else:
            enhanced_message = clean_message
        
        return enhanced_message
    
    def _get_language_hint(self, file_extension: str) -> str:
        ext_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.jsx': 'jsx',
            '.tsx': 'tsx',
            '.html': 'html',
            '.css': 'css',
            '.scss': 'scss',
            '.sass': 'sass',
            '.json': 'json',
            '.xml': 'xml',
            '.yaml': 'yaml',
            '.yml': 'yaml',
            '.toml': 'toml',
            '.md': 'markdown',
            '.txt': 'text',
            '.sh': 'bash',
            '.bash': 'bash',
            '.zsh': 'zsh',
            '.fish': 'fish',
            '.rs': 'rust',
            '.go': 'go',
            '.java': 'java',
            '.c': 'c',
            '.cpp': 'cpp',
            '.h': 'c',
            '.hpp': 'cpp',
            '.php': 'php',
            '.rb': 'ruby',
            '.sql': 'sql',
            '.dockerfile': 'dockerfile',
            '.gitignore': 'gitignore',
            '.env': 'bash'
        }
        
        return ext_map.get(file_extension.lower(), '')
    
    def get_file_summary(self, file_contexts: List[FileContext]) -> str:
        if not file_contexts:
            return "No files included in context."
        
        successful = [ctx for ctx in file_contexts if not ctx.error]
        failed = [ctx for ctx in file_contexts if ctx.error]
        
        summary_parts = []
        
        if successful:
            total_lines = sum(ctx.line_count for ctx in successful)
            file_names = [ctx.relative_path for ctx in successful]
            summary_parts.append(
                f"Included {len(successful)} file(s) ({total_lines} lines total): {', '.join(file_names)}"
            )
        
        if failed:
            failed_names = [f"{ctx.relative_path} ({ctx.error})" for ctx in failed]
            summary_parts.append(f"Failed to include: {', '.join(failed_names)}")
        
        return " | ".join(summary_parts)


async def process_file_references(message: str, working_directory: Optional[str] = None) -> tuple[str, List[FileContext]]:
    manager = FileContextManager(working_directory)
    return await manager.process_message_with_file_context(message)