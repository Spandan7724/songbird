# File reference parser for extracting @filename patterns from user messages.


import re
import os
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass


@dataclass
class FileReference:
    raw_text: str
    file_path: str
    start_pos: int
    end_pos: int
    exists: bool = False
    resolved_path: Optional[Path] = None
    error: Optional[str] = None


class FileReferenceParser:
    
    FILE_REFERENCE_PATTERN = re.compile(
        r'@(?:'
        r'"([^"]+)"'
        r'|'
        r'([^\s@,;!?]+)' 
        r')'
    )
    
    def __init__(self, working_directory: Optional[str] = None):
        self.working_directory = Path(working_directory or os.getcwd()).resolve()
    
    def parse_message(self, message: str) -> List[FileReference]:

        references = []
        
        for match in self.FILE_REFERENCE_PATTERN.finditer(message):
            quoted_path = match.group(1)
            unquoted_path = match.group(2)
            file_path = quoted_path if quoted_path else unquoted_path
            
            if not file_path or not file_path.strip():
                continue
            
            start_pos = match.start()
            
            if start_pos > 0 and message[start_pos - 1].isalnum():
                continue
            
            if self._looks_like_domain(file_path):
                continue
                
            reference = FileReference(
                raw_text=match.group(0),
                file_path=file_path,
                start_pos=start_pos,
                end_pos=match.end()
            )
            
            self._resolve_file_reference(reference)
            references.append(reference)
        
        return references
    
    def _looks_like_domain(self, path: str) -> bool:
        if '.' in path and all(c.isalnum() or c in '.-' for c in path):
            parts = path.split('.')
            if (len(parts) >= 2 and 
                len(parts[-1]) >= 2 and len(parts[-1]) <= 4 and 
                parts[-1].isalpha() and 
                '/' not in path and
                not self._is_common_file_extension(parts[-1])):
                return True
        return False
    
    def _is_common_file_extension(self, ext: str) -> bool:
        common_exts = {
            'py', 'js', 'ts', 'html', 'css', 'json', 'xml', 'txt', 'md', 
            'java', 'cpp', 'c', 'h', 'rs', 'go', 'php', 'rb', 'swift',
            'kt', 'scala', 'sh', 'bat', 'ps1', 'yml', 'yaml', 'toml',
            'ini', 'cfg', 'conf', 'log', 'sql', 'csv', 'tsv', 'jpg',
            'png', 'gif', 'svg', 'pdf', 'doc', 'docx', 'xls', 'xlsx'
        }
        return ext.lower() in common_exts
    
    def _resolve_file_reference(self, reference: FileReference) -> None:
        try:
            clean_path = reference.file_path.strip()
            
            if clean_path.startswith('./'):
                path = Path(clean_path[2:])
            elif clean_path.startswith('/'):    
                reference.error = "Absolute paths not allowed for security reasons"
                return
            elif '..' in clean_path:
                reference.error = "Parent directory access (..) not allowed for security reasons"
                return
            else:
                path = Path(clean_path)
            
            resolved_path = (self.working_directory / path).resolve()
            
            try:
                resolved_path.relative_to(self.working_directory)
            except ValueError:
                reference.error = "File path outside working directory not allowed"
                return
            
            reference.resolved_path = resolved_path
            reference.exists = resolved_path.exists() and resolved_path.is_file()
            
            if not reference.exists:
                if resolved_path.exists():
                    reference.error = "Path exists but is not a file (might be a directory)"
                else:
                    reference.error = "File does not exist"
        
        except Exception as e:
            reference.error = f"Error resolving path: {str(e)}"
    
    def extract_file_paths(self, message: str) -> List[str]:

        references = self.parse_message(message)
        return [
            str(ref.resolved_path) 
            for ref in references 
            if ref.exists and ref.resolved_path
        ]
    
    def remove_file_references(self, message: str) -> str:

        result = self.FILE_REFERENCE_PATTERN.sub('', message)
        result = ' '.join(result.split())
        return result
    
    def get_reference_summary(self, references: List[FileReference]) -> str:

        if not references:
            return "No file references found."
        
        valid_refs = [ref for ref in references if ref.exists]
        invalid_refs = [ref for ref in references if not ref.exists]
        
        summary_parts = []
        
        if valid_refs:
            file_list = ", ".join(ref.file_path for ref in valid_refs)
            summary_parts.append(f"Found {len(valid_refs)} file(s): {file_list}")
        
        if invalid_refs:
            invalid_list = []
            for ref in invalid_refs:
                error_msg = ref.error or "file not found"
                invalid_list.append(f"{ref.file_path} ({error_msg})")
            
            summary_parts.append(f"Invalid references: {', '.join(invalid_list)}")
        
        return " | ".join(summary_parts)


def parse_file_references(message: str, working_directory: Optional[str] = None) -> List[FileReference]:

    parser = FileReferenceParser(working_directory)
    return parser.parse_message(message)


def extract_valid_file_paths(message: str, working_directory: Optional[str] = None) -> List[str]:
    parser = FileReferenceParser(working_directory)
    return parser.extract_file_paths(message)