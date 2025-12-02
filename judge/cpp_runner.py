import resource
import subprocess
import tempfile
from pathlib import Path


MEMORY_LIMIT = 256 * 1024 * 1024  # 256 MB


def _limit_resources():
    try:
        resource.setrlimit(resource.RLIMIT_AS, (MEMORY_LIMIT, MEMORY_LIMIT))
        resource.setrlimit(resource.RLIMIT_DATA, (MEMORY_LIMIT, MEMORY_LIMIT))
    except (ValueError, resource.error):
        pass


def run(code: str, input_data: str, timeout: int = 7):
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        code_path = tmpdir_path / "main.cpp"
        binary_path = tmpdir_path / "a.out"
        code_path.write_text(code)

        try:
            compile_proc = subprocess.run(
                ["g++", "-std=c++17", "-O2", code_path.name, "-o", binary_path.name],
                cwd=tmpdir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "output": "",
                "error": "Compilation timed out",
                "compile_error": True,
                "timeout": True,
            }

        if compile_proc.returncode != 0:
            return {
                "success": False,
                "output": "",
                "error": compile_proc.stderr.decode(),
                "compile_error": True,
            }

        try:
            exec_proc = subprocess.run(
                [f"./{binary_path.name}"],
                input=input_data.encode(),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=tmpdir,
                timeout=timeout,
                preexec_fn=_limit_resources,
            )
            return {
                "success": exec_proc.returncode == 0,
                "output": exec_proc.stdout.decode(),
                "error": exec_proc.stderr.decode(),
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "output": "",
                "error": "Execution timed out",
                "timeout": True,
            }
