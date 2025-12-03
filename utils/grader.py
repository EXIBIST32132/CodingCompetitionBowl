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

import json
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path
from typing import Dict, List, Optional

BASE_DIR = Path(__file__).resolve().parent.parent
# Ensure local judge modules are importable when this file is run directly.
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from judge import cpp_runner, java_runner, python_runner


PROBLEMS_DIR = BASE_DIR / "problems"
DEFAULT_TIMEOUT = 5
JAVA_IMPORT_LINE = "import java.util.*;"
CPP_INCLUDE_LINE = "#include <bits/stdc++.h>"


RUNNERS = {
    "python": python_runner.run,
    "py": python_runner.run,
    "java": java_runner.run,
    "c++": cpp_runner.run,
    "cpp": cpp_runner.run,
    "c": cpp_runner.run,
}


def ensure_java_imports(code: str) -> str:
    if "import java.util" in code:
        return code
    lines = code.splitlines()
    insert_at = 0
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("package ") or stripped.startswith("import "):
            insert_at = idx + 1
            continue
        if stripped == "":
            insert_at = idx + 1
            continue
        break
    lines.insert(insert_at, JAVA_IMPORT_LINE)
    return "\n".join(lines) + ("\n" if code.endswith("\n") else "")


def ensure_cpp_includes(code: str) -> str:
    if CPP_INCLUDE_LINE in code:
        return code
    prefix = f"{CPP_INCLUDE_LINE}\n"
    if code.startswith("#include"):
        return prefix + code
    return f"{prefix}\n{code}"


def ensure_python_imports(code: str) -> str:
    if "List[" in code and "from typing import" not in code and "import typing" not in code:
        return f"from typing import List\n\n{code}"
    return code


def apply_language_boilerplate(language: str, code: str) -> str:
    lang_key = (language or "").strip().lower()
    prepared = code or ""
    if lang_key == "java":
        return ensure_java_imports(prepared)
    if lang_key in {"c++", "cpp", "c"}:
        return ensure_cpp_includes(prepared)
    if lang_key in {"python", "py"}:
        return ensure_python_imports(prepared)
    return prepared


def list_problems() -> List[Dict]:
    problems = []
    for path in sorted(PROBLEMS_DIR.glob("*.json"), key=lambda p: int(p.stem)):
        with path.open() as f:
            data = json.load(f)
            problems.append(
                {
                    "id": data.get("id"),
                    "title": data.get("title"),
                    "description": data.get("description"),
                    "constraints": data.get("constraints"),
                }
            )
    return problems


def load_problem(problem_id: int) -> Dict:
    path = PROBLEMS_DIR / f"{problem_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"Problem {problem_id} not found")
    with path.open() as f:
        return json.load(f)


def grade_submission(language: str, code: str, problem: Dict):
    lang_key = (language or "").strip().lower()
    prepared_code = apply_language_boilerplate(lang_key, code or "")
    structured_cases = build_structured_cases(problem)
    if structured_cases and lang_key in {"java", "python"}:
        try:
            return grade_structured(lang_key, prepared_code, problem, structured_cases)
        except Exception:
            # fall back to stdin-based grading if structured path fails
            pass

    runner = RUNNERS.get(lang_key)
    if not runner:
        return {"error": f"Unsupported language: {language}"}

    tests = problem.get("tests", [])
    results = []
    passed = 0
    compile_failure = False

    for test in tests:
        if compile_failure:
            results.append(
                {
                    "input": test.get("input", ""),
                    "expected": test.get("output", "").strip(),
                    "output": "",
                    "passed": False,
                    "error": "Compilation failed",
                }
            )
            continue

        res = runner(prepared_code, test.get("input", ""), timeout=DEFAULT_TIMEOUT)
        output_clean = (res.get("output") or "").strip()
        expected_clean = (test.get("output") or "").strip()
        test_passed = res.get("success") and output_clean == expected_clean
        results.append(
            {
                "input": test.get("input", ""),
                "expected": expected_clean,
                "output": res.get("output", ""),
                "error": res.get("error", ""),
                "passed": test_passed,
                "compile_error": res.get("compile_error", False),
                "timeout": res.get("timeout", False),
            }
        )
        if res.get("compile_error"):
            compile_failure = True
        if test_passed:
            passed += 1

    return {
        "passed": passed,
        "total": len(tests),
        "details": results,
        "compile_error": compile_failure,
    }


# Structured testing helpers (method-based testing) -------------------------


FUNCTION_NAMES = {
    1: "removedNames",
    2: "mirrorScore",
    3: "goodCookies",
    4: "sortElves",
    5: "meltIcicles",
    6: "checkSafety",
    7: "decodeMessage",
    8: "minDifference",
    9: "largestRegion",
    10: "checkCircuit",
}


def build_structured_cases(problem: Dict) -> Optional[List[Dict]]:
    problem_id = problem.get("id")
    tests = problem.get("tests", [])
    cases = []
    try:
        for test in tests:
            args, expected = parse_case(problem_id, test["input"], test["output"])
            cases.append({"args": args, "expected": expected})
    except Exception:
        return None
    return cases


def parse_case(problem_id: int, raw_input: str, raw_output: str):
    lines = [ln for ln in raw_input.splitlines() if ln.strip() != ""]
    if problem_id == 1:
        idx = 0
        n = int(lines[idx]); idx += 1
        draft = lines[idx: idx + n]; idx += n
        m = int(lines[idx]) if idx < len(lines) else 0; idx += 1
        fin = lines[idx: idx + m]
        expected = int(raw_output.strip())
        return [draft, fin], expected
    if problem_id == 2:
        s = raw_input.strip()
        return [s], int(raw_output.strip())
    if problem_id == 3:
        idx = 0
        n = int(lines[idx]) if lines else 0; idx += 1
        cookies = []
        for _ in range(n):
            size, temp = map(int, lines[idx].split())
            cookies.append([size, temp])
            idx += 1
        expected = int(raw_output.strip())
        return [cookies], expected
    if problem_id == 4:
        elves = [p.strip() for p in raw_input.split(",") if p.strip()]
        expected_list = raw_output.strip().splitlines()
        return [elves], expected_list
    if problem_id == 5:
        nums = [int(x.strip()) for x in raw_input.replace(",", " ").split() if x.strip()]
        expected_list = [int(x.strip()) for x in raw_output.strip().splitlines() if x.strip() != ""]
        return [nums], expected_list
    if problem_id == 6:
        start, end = map(int, lines[0].split())
        n = int(lines[1]) if len(lines) > 1 else 0
        intervals = []
        for i in range(n):
            a, b = map(int, lines[2 + i].split())
            intervals.append([a, b])
        return [start, end, intervals], raw_output.strip()
    if problem_id == 7:
        s = lines[0]
        k = int(lines[1])
        return [s, k], raw_output.strip()
    if problem_id == 8:
        nums = [int(x.strip()) for x in raw_input.replace(",", " ").split() if x.strip()]
        return [nums], int(raw_output.strip())
    if problem_id == 9:
        n = int(lines[0])
        grid = lines[1:1 + n]
        return [grid], int(raw_output.strip())
    if problem_id == 10:
        n = int(lines[0]) if lines else 0
        m = int(lines[1]) if len(lines) > 1 else 0
        edges = []
        for i in range(m):
            u, v = map(int, lines[2 + i].split())
            edges.append([u, v])
        return [n, edges], raw_output.strip()
    raise ValueError("Unknown problem id for structured parsing")


def get_function_name(problem: Dict, language: str) -> Optional[str]:
    sigs = problem.get("method_signatures") or {}
    sig = sigs.get(language) or sigs.get(language.lower())
    if not sig:
        return None
    if language == "python":
        if "def " in sig:
            return sig.split("def ", 1)[1].split("(", 1)[0].strip()
    elif language == "java":
        # public static return name(
        tokens = sig.split()
        if len(tokens) >= 4:
            return tokens[3].split("(")[0]
    return None


def grade_structured(language: str, code: str, problem: Dict, cases: List[Dict]):
    func_name = get_function_name(problem, language)
    problem_id = problem.get("id")
    if not func_name or not problem_id:
        raise ValueError("Missing function info")

    if language == "python":
        return grade_structured_python(code, func_name, cases)
    if language == "java":
        return grade_structured_java(code, func_name, cases, problem_id)
    raise ValueError("Structured testing not supported for this language")


def grade_structured_python(code: str, func_name: str, cases: List[Dict]):
    results = []
    passed = 0
    with tempfile.TemporaryDirectory() as tmp:
        sol_path = Path(tmp) / "solution.py"
        sol_path.write_text(code)
        runner_path = Path(tmp) / "runner.py"
        runner_code = textwrap.dedent(
            """
            import json, traceback
            import solution

            cases = {cases_json}
            fn = getattr(solution, "{func}", None)
            if fn is None:
                print("RESULT|0|ERROR|Function not found")
                raise SystemExit(0)

            for idx, case in enumerate(cases):
                try:
                    res = fn(*case["args"])
                    ok = res == case["expected"]
                    if ok:
                        print(f"RESULT|{{idx}}|PASS")
                    else:
                        print(f"RESULT|{{idx}}|FAIL|{{json.dumps(res)}}|{{json.dumps(case['expected'])}}")
                except Exception as e:
                    print(f"RESULT|{{idx}}|ERROR|{{type(e).__name__}}:{{e}}")
            """
        ).format(cases_json=json.dumps(cases), func=func_name)
        runner_path.write_text(runner_code)

        proc = subprocess.run(
            ["python3", runner_path.name],
            cwd=tmp,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=DEFAULT_TIMEOUT,
        )
        stdout_lines = proc.stdout.decode().splitlines()
        compile_error = proc.returncode != 0
        for line in stdout_lines:
            if not line.startswith("RESULT|"):
                continue
            parts = line.split("|")
            idx = int(parts[1])
            status = parts[2]
            if status == "PASS":
                results.append({"passed": True, "error": ""})
                passed += 1
            elif status.startswith("FAIL"):
                err = "Mismatch"
                if len(parts) >= 5:
                    err = f"Got {parts[3]} Expected {parts[4]}"
                results.append({"passed": False, "error": err})
            else:
                err = parts[3] if len(parts) > 3 else "Error"
                results.append({"passed": False, "error": err})

    return {"passed": passed, "total": len(cases), "details": results, "compile_error": compile_error}


def grade_structured_java(code: str, func_name: str, cases: List[Dict], problem_id: int):
    passed = 0
    results: List[Dict] = []
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        (tmp_path / "Main.java").write_text(code)
        harness_code = build_java_harness(func_name, cases, problem_id)
        (tmp_path / "Harness.java").write_text(harness_code)

        compile_proc = subprocess.run(
            ["javac", "Main.java", "Harness.java"],
            cwd=tmp,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=DEFAULT_TIMEOUT,
        )
        if compile_proc.returncode != 0:
            return {
                "passed": 0,
                "total": len(cases),
                "details": [
                    {"passed": False, "error": compile_proc.stderr.decode(), "compile_error": True}
                ],
                "compile_error": True,
            }

        run_proc = subprocess.run(
            ["java", "Harness"],
            cwd=tmp,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=DEFAULT_TIMEOUT,
        )
        stdout_lines = run_proc.stdout.decode().splitlines()
        for line in stdout_lines:
            if not line.startswith("RESULT|"):
                continue
            parts = line.split("|")
            idx = int(parts[1])
            status = parts[2]
            if status == "PASS":
                results.append({"passed": True, "error": ""})
                passed += 1
            elif status == "FAIL":
                actual = parts[3] if len(parts) > 3 else ""
                expected = parts[4] if len(parts) > 4 else ""
                results.append({"passed": False, "error": f"Got {actual} Expected {expected}"})
            else:
                err = parts[3] if len(parts) > 3 else "Runtime error"
                results.append({"passed": False, "error": err})

    return {"passed": passed, "total": len(cases), "details": results, "compile_error": False}


def java_list_str(items: List[str]) -> str:
    return f"Arrays.asList({', '.join(items)})"


def java_literal(val):
    if isinstance(val, str):
        escaped = val.replace("\\", "\\\\").replace('"', '\\"')
        return f"\"{escaped}\""
    if isinstance(val, bool):
        return "true" if val else "false"
    if isinstance(val, int):
        return str(val)
    if isinstance(val, list):
        if not val:
            return "new ArrayList<>()"
        if all(isinstance(x, int) for x in val):
            return f"Arrays.asList({', '.join(str(x) for x in val)})"
        if all(isinstance(x, str) for x in val):
            return java_list_str([java_literal(x) for x in val])
        if all(isinstance(x, list) and all(isinstance(y, int) for y in x) for x in val):
            inner = ", ".join("new int[]{" + ", ".join(str(y) for y in x) + "}" for x in val)
            return "new int[][]{" + inner + "}"
        if all(isinstance(x, list) and all(isinstance(y, str) for y in x) for x in val):
            inner = ", ".join("new String[]{" + ", ".join(java_literal(y) for y in x) + "}" for x in val)
            return "new String[][]{" + inner + "}"
    return "null"


def build_java_harness(func_name: str, cases: List[Dict], problem_id: int) -> str:
    case_calls = []
    expected_cases = []
    for idx, case in enumerate(cases):
        args = case["args"]
        expected = case["expected"]
        call_args = []
        if problem_id == 1:
            call_args = [
                java_literal(args[0]),
                java_literal(args[1]),
            ]
        elif problem_id == 2:
            call_args = [java_literal(args[0])]
        elif problem_id == 3:
            cookies_literal = "new int[0][0]" if not args[0] else java_literal(args[0])
            call_args = [cookies_literal]
        elif problem_id == 4:
            call_args = [java_literal(args[0])]
        elif problem_id == 5:
            call_args = [java_literal(args[0])]
        elif problem_id == 6:
            intervals_literal = "new int[][]{" + ", ".join(
                "new int[]{" + ", ".join(str(v) for v in pair) + "}" for pair in args[2]
            ) + "}"
            call_args = [str(args[0]), str(args[1]), intervals_literal]
        elif problem_id == 7:
            call_args = [java_literal(args[0]), str(args[1])]
        elif problem_id == 8:
            arr_literal = "new int[]{" + ", ".join(str(x) for x in args[0]) + "}"
            call_args = [arr_literal]
        elif problem_id == 9:
            grid_literal = "new char[][]{" + ", ".join(
                f"{java_literal(row)}.toCharArray()" for row in args[0]
            ) + "}"
            call_args = [grid_literal]
        elif problem_id == 10:
            edges_literal = "new int[][]{" + ", ".join(
                "new int[]{" + ", ".join(str(v) for v in e) + "}" for e in args[1]
            ) + "}"
            call_args = [str(args[0]), edges_literal]

        call = f"case {idx}: return Main.{func_name}({', '.join(call_args)});"
        case_calls.append(call)
        expected_cases.append(f"case {idx}: return {java_literal(expected)};")

    switch_calls = "\n            ".join(case_calls)
    switch_expected = "\n            ".join(expected_cases)

    return textwrap.dedent(
        f"""
        import java.util.*;

        public class Harness {{
            public static void main(String[] args) {{
                int total = {len(cases)};
                for (int i = 0; i < total; i++) {{
                    try {{
                        Object actual = runCase(i);
                        Object expected = expectedCase(i);
                        if (Objects.deepEquals(actual, expected)) {{
                            System.out.println("RESULT|" + i + "|PASS");
                        }} else {{
                            System.out.println("RESULT|" + i + "|FAIL|" + stringify(actual) + "|" + stringify(expected));
                        }}
                    }} catch (Exception e) {{
                        System.out.println("RESULT|" + i + "|ERROR|" + e.getClass().getSimpleName() + ":" + e.getMessage());
                    }}
                }}
            }}

            static Object runCase(int idx) {{
                switch (idx) {{
            {textwrap.indent(switch_calls, ' ' * 12)}
                    default: return null;
                }}
            }}

            static Object expectedCase(int idx) {{
                switch (idx) {{
            {textwrap.indent(switch_expected, ' ' * 12)}
                    default: return null;
                }}
            }}

            static String stringify(Object o) {{
                if (o == null) return "null";
                if (o.getClass().isArray()) {{
                    if (o instanceof int[]) return Arrays.toString((int[]) o);
                    if (o instanceof char[]) return Arrays.toString((char[]) o);
                    if (o instanceof Object[]) return Arrays.deepToString((Object[]) o);
                }}
                if (o instanceof Collection) return o.toString();
                return String.valueOf(o);
            }}
        }}
        """
    )
