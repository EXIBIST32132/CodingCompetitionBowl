"""
MIT License

Copyright (c) 2025 Jonathan St-Georges

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import os
import resource
import subprocess
import sys
import tempfile
from pathlib import Path


MEMORY_LIMIT = 256 * 1024 * 1024  # 256 MB


def _limit_resources():
    try:
        resource.setrlimit(resource.RLIMIT_AS, (MEMORY_LIMIT, MEMORY_LIMIT))
        resource.setrlimit(resource.RLIMIT_DATA, (MEMORY_LIMIT, MEMORY_LIMIT))
    except (ValueError, resource.error):
        # Resource limits may not be supported on all platforms.
        pass


def run(code: str, input_data: str, timeout: int = 5):
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "solution.py"
        path.write_text(code)
        try:
            result = subprocess.run(
                [sys.executable or "python3", path.name],
                input=input_data.encode(),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=tmpdir,
                timeout=timeout,
                preexec_fn=_limit_resources,
            )
            return {
                "success": result.returncode == 0,
                "output": result.stdout.decode(),
                "error": result.stderr.decode(),
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "output": "",
                "error": "Execution timed out",
                "timeout": True,
            }
