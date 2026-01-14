"""Code file inspection and metadata extraction."""

import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import asyncio

async def inspect_code(file_path: str) -> Dict[str, Any]:
    """
    Inspect a source code file and extract metadata and content.
    
    Args:
        file_path: Absolute path to the code file
        
    Returns:
        Structured data context for the agent
    """
    def _extract():
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            
        lines = content.splitlines()
        file_name = Path(file_path).name
        ext = Path(file_path).suffix.lower().lstrip('.')
        
        # Simple analysis
        line_count = len(lines)
        word_count = len(content.split())
        
        # Basic structural identification for common languages
        import re
        classes = []
        functions = []
        
        # Patterns for common languages (Py, JS, Java, etc.)
        class_patterns = [r'^class\s+([A-Za-z0-9_]+)', r'^export\s+class\s+([A-Za-z0-9_]+)']
        func_patterns = [r'^def\s+([A-Za-z0-9_]+)', r'^function\s+([A-Za-z0-9_]+)', r'([A-Za-z0-9_]+)\s*\([^)]*\)\s*\{']

        for line in lines:
            trimmed = line.strip()
            # Try to match classes
            for p in class_patterns:
                match = re.search(p, trimmed)
                if match:
                    classes.append(match.group(1))
                    break
            # Try to match functions
            for p in func_patterns:
                match = re.search(p, trimmed)
                if match:
                    functions.append(match.group(1))
                    break

        # Generate human-readable description
        description_parts = [
            "Source Code Overview:",
            f"- File: {file_name}",
            f"- Language: {ext.upper()}",
            f"- Lines: {line_count}",
        ]
        
        if classes:
            description_parts.append(f"- Classes found: {', '.join(classes[:5])}" + ("..." if len(classes) > 5 else ""))
        if functions:
            description_parts.append(f"- Principal functions: {', '.join(functions[:10])}" + ("..." if len(functions) > 10 else ""))
            
        # Add content preview
        preview_length = min(1500, len(content))
        description_parts.append(f"\nCode Preview (first {preview_length} chars):")
        description_parts.append(f"```python\n{content[:preview_length]}\n```")
        if len(content) > preview_length:
            description_parts.append("...")
            
        description = "\n".join(description_parts)
        
        return {
            "file_path": os.path.abspath(file_path),
            "file_name": file_name,
            "document_type": f"{ext.upper()} Source Code",
            "analyzed_at": datetime.now().isoformat(),
            "description": description,
            "full_text": content,
            "summary": {
                "line_count": line_count,
                "word_count": word_count,
                "language": ext,
                "classes": classes,
                "functions": functions
            },
            "capabilities": [
                "code_analysis",
                "logic_extraction",
                "bug_detection",
                "refactoring_suggestions"
            ]
        }
    
    return await asyncio.to_thread(_extract)
