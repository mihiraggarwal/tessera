"""
Python Executor - Sandboxed Python execution for chat queries.
Uses pattern-based blocking for security with basic exec.
"""
import io
import traceback
from typing import Dict, Any
from contextlib import redirect_stdout, redirect_stderr

import numpy as np
import pandas as pd
import math

from app.services.dcel import get_current_dcel
from app.services.helper_functions import create_helper_functions


# Dangerous patterns to block
BLOCKED_PATTERNS = [
    'import os', 'import sys', 'import subprocess',
    'import socket', 'import requests', 'import urllib',
    'import shutil', 'import pathlib',
    '__import__', 'open(', 'exec(', 'eval(',
    'compile(', 'globals(', 'locals(',
    '__builtins__', '__code__', '__class__',
]


class PythonExecutor:
    """
    Python executor for DCEL queries with pattern-based security.
    """
    
    MAX_OUTPUT_SIZE = 100 * 1024  # 100KB max output
    
    def __init__(self):
        self.dcel = None
        self.helpers = {}
    
    def _validate_code(self, code: str) -> tuple[bool, str]:
        """Check code for dangerous patterns."""
        code_lower = code.lower()
        
        for pattern in BLOCKED_PATTERNS:
            if pattern.lower() in code_lower:
                return False, f"Blocked pattern detected: {pattern}"
        
        return True, ""
    
    def _create_safe_environment(self) -> Dict[str, Any]:
        """Create the execution environment with DCEL and helpers."""
        self.dcel = get_current_dcel()
        
        if not self.dcel:
            return None
        
        # Create helper functions bound to current DCEL
        self.helpers = create_helper_functions(self.dcel)
        
        # Build safe environment
        env = {
            # DCEL access
            'dcel': self.dcel,
            
            # Helper functions
            **self.helpers,
            
            # Safe libraries
            'np': np,
            'pd': pd,
            'math': math,
            'len': len,
            'sum': sum,
            'min': min,
            'max': max,
            'abs': abs,
            'round': round,
            'sorted': sorted,
            'list': list,
            'dict': dict,
            'set': set,
            'tuple': tuple,
            'str': str,
            'int': int,
            'float': float,
            'bool': bool,
            'range': range,
            'enumerate': enumerate,
            'zip': zip,
            'any': any,
            'all': all,
            'filter': filter,
            'map': map,
            'print': print,  # Will be captured
            'getattr': getattr,
            'hasattr': hasattr,
        }
        
        return env
    
    def _generate_hint(self, error: Exception, code: str) -> str:
        """Generate helpful hint based on error type."""
        error_str = str(error).lower()
        error_type = type(error).__name__
        
        if 'not found' in error_str or 'keyerror' in error_str:
            return "Use get_available_values() or fuzzy_search() to find correct values."
        
        if 'zerodivision' in error_type.lower():
            return "List might be empty. Add: if len(items) > 0: before division."
        
        if 'nonetype' in error_str or 'attributeerror' in error_type.lower():
            return "Use safe_get_property(f, 'prop', default) for null-safe access."
        
        if 'index' in error_str:
            return "List might be empty. Check length before accessing indices."
        
        return "Try inspect_sample() to see actual data structure."
    
    def execute(self, code: str) -> Dict[str, Any]:
        """
        Execute Python code in a sandboxed environment.
        
        Args:
            code: Python code to execute
            
        Returns:
            {success: bool, output: str} or {success: False, error: str, hint: str}
        """
        # Validate code
        is_valid, error_msg = self._validate_code(code)
        if not is_valid:
            return {
                "success": False,
                "error": f"Security violation: {error_msg}",
                "hint": "Remove blocked patterns and try again."
            }
        
        # Create environment
        env = self._create_safe_environment()
        if env is None:
            return {
                "success": False,
                "error": "No DCEL available. Please load facility data first.",
                "hint": "Upload facility data and compute Voronoi diagram."
            }
        
        # Capture stdout/stderr
        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()
        
        try:
            # Compile code
            code_obj = compile(code, '<user_code>', 'exec')
            
            # Execute with output capture
            with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                exec(code_obj, env)
            
            output = stdout_capture.getvalue()
            stderr_output = stderr_capture.getvalue()
            
            # Limit output size
            if len(output) > self.MAX_OUTPUT_SIZE:
                output = output[:self.MAX_OUTPUT_SIZE] + "\n... (output truncated)"
            
            return {
                "success": True,
                "output": output if output else "(No output - use print() to show results)",
                "stderr": stderr_output if stderr_output else None
            }
            
        except Exception as e:
            error_msg = str(e)
            tb = traceback.format_exc()
            
            # Extract relevant line from traceback
            lines = tb.split('\n')
            relevant_lines = [l for l in lines if '<user_code>' in l or 'line' in l.lower()]
            
            return {
                "success": False,
                "error": f"{type(e).__name__}: {error_msg}",
                "hint": self._generate_hint(e, code),
                "traceback": '\n'.join(relevant_lines[-3:]) if relevant_lines else None
            }


# Singleton instance
_executor = None

def get_executor() -> PythonExecutor:
    """Get the singleton executor instance."""
    global _executor
    if _executor is None:
        _executor = PythonExecutor()
    return _executor
