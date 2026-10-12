#!/usr/bin/env python3
"""debug-dojo: practice debugging an unfamiliar codebase under time pressure.

    python dojo.py list                 show the levels
    python dojo.py start <level>        copy the clean code into workspace/ and plant the bugs
    python dojo.py check [-v]           run the grader against workspace/
    python dojo.py demo <scenario>      run a scenario against workspace/ (reproduce the tickets)
    python dojo.py hint [n]             reveal hint n (default: next unseen hint)
    python dojo.py diff                 what you changed since `start`
    python dojo.py solution             reveal every planted bug and the fix
    python dojo.py reset                delete workspace/
    python dojo.py verify               maintainer check: every level fails, reference passes
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LEVELS = ROOT / "levels"
STATE_FILE = ROOT / ".dojo-state.json"
PY = sys.executable

# Each runtime: where the clean code lives, where the practice copy goes, how tests run.
RUNTIMES = {
    "py": {
        "reference": ROOT / "reference" / "supportdesk",
        "workspace": ROOT / "workspace",
        "copy_to": ROOT / "workspace" / "supportdesk",
        "test_cwd": ROOT,
    },
    "ts": {
        "reference": ROOT / "ts" / "reference" / "src",
        "workspace": ROOT / "ts" / "workspace",
        "copy_to": ROOT / "ts" / "workspace" / "src",
        "test_cwd": ROOT / "ts",
    },
}


@dataclass(frozen=True)
class Mutation:
    file: str
    old: str
    new: str
    why: str
    kind: str = ""


@dataclass
class Level:
    slug: str
    title: str
    minutes: int
    brief: str
    hints: list[str]
    mutations: list[Mutation]
    demo: list[str]
    runtime: str = "py"

    @property
    def paths(self) -> dict:
        return RUNTIMES[self.runtime]


def load_levels() -> list[Level]:
    levels = []
    for folder in sorted(p for p in LEVELS.iterdir() if p.is_dir() and (p / "_solution.py").exists()):
        spec = importlib.util.spec_from_file_location(f"level_{folder.name}", folder / "_solution.py")
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        brief = (folder / "BRIEF.md").read_text()
        levels.append(
            Level(
                slug=folder.name,
                title=module.TITLE,
                minutes=module.MINUTES,
                brief=brief,
                hints=list(module.HINTS),
                mutations=[Mutation(**m) for m in module.MUTATIONS],
                demo=list(getattr(module, "DEMO", [])),
                runtime=getattr(module, "RUNTIME", "py"),
            )
        )
    return levels


def find_level(name: str) -> Level:
    levels = load_levels()
    for level in levels:
        if level.slug == name or level.slug.split("-", 1)[0] == name or level.slug.split("-", 1)[1] == name:
            return level
    sys.exit(f"unknown level {name!r}. Try: {', '.join(lv.slug for lv in levels)}")


def apply_mutations(target: Path, mutations: list[Mutation]) -> None:
    for m in mutations:
        path = target / m.file
        text = path.read_text()
        count = text.count(m.old)
        if count != 1:
            raise RuntimeError(f"{m.file}: expected exactly one match for mutation, found {count}:\n{m.old}")
        path.write_text(text.replace(m.old, m.new))


def copy_reference(reference: Path, target: Path) -> None:
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(reference, target, ignore=shutil.ignore_patterns("__pycache__"))


def read_state() -> dict:
    if not STATE_FILE.exists():
        sys.exit("no level in progress. Run: python dojo.py start <level>")
    return json.loads(STATE_FILE.read_text())


def write_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2))


def elapsed(state: dict) -> str:
    seconds = int(time.time() - state["started_at"])
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


@dataclass
class TestRun:
    returncode: int
    output: str
    failed: list[str]


def run_tests(runtime: str, target: str, extra: list[str], quiet: bool) -> TestRun:
    """target is a directory (relative to the runtime root) holding the code under test."""
    env = {**os.environ, "DOJO_TARGET": target}
    cwd = RUNTIMES[runtime]["test_cwd"]
    if runtime == "py":
        cmd = [PY, "-m", "pytest", "-p", "no:cacheprovider", "-rfE", *(["-q", "--no-header"] if quiet else []), *extra]
        proc = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True)
        failed = []
        for line in proc.stdout.splitlines():
            if line.startswith("FAILED ") or line.startswith("ERROR "):
                failed.append(line.split(" ", 1)[1].split(" - ")[0])
        return TestRun(proc.returncode, proc.stdout + proc.stderr, failed)
    report = cwd / ".vitest-report.json"
    cmd = ["npx", "vitest", "run", "--reporter=default", "--reporter=json", f"--outputFile={report}", *extra]
    proc = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True)
    failed = []
    if report.exists():
        data = json.loads(report.read_text())
        for suite in data.get("testResults", []):
            suite_name = Path(suite["name"]).name
            for case in suite.get("assertionResults", []):
                if case["status"] == "failed":
                    failed.append(f"{suite_name}::{case['fullName']}")
            if suite["status"] == "failed" and not suite.get("assertionResults"):
                failed.append(f"{suite_name}::<suite failed to load>")
        report.unlink()
    return TestRun(proc.returncode, proc.stdout + proc.stderr, failed)


# -- commands -----------------------------------------------------------------


def cmd_list(_: argparse.Namespace) -> None:
    state = json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}
    print(f"{'level':<28} {'bugs':>4} {'time':>6}  title")
    for level in load_levels():
        marker = " <- in progress" if state.get("level") == level.slug else ""
        print(f"{level.slug:<28} {len(level.mutations):>4} {level.minutes:>4}m  {level.title}{marker}")


def cmd_start(args: argparse.Namespace) -> None:
    level = find_level(args.level)
    if STATE_FILE.exists() and not args.force:
        state = json.loads(STATE_FILE.read_text())
        sys.exit(f"workspace/ already holds {state['level']}. Use --force to replace it (your edits are lost).")
    for paths in RUNTIMES.values():
        if paths["workspace"].exists():
            shutil.rmtree(paths["workspace"])
    workspace = level.paths["workspace"]
    copy_reference(level.paths["reference"], level.paths["copy_to"])
    apply_mutations(level.paths["copy_to"], level.mutations)
    subprocess.run(["git", "init", "-q"], cwd=workspace, check=False)
    subprocess.run(["git", "add", "-A"], cwd=workspace, check=False)
    subprocess.run(
        ["git", "-c", "user.email=dojo@local", "-c", "user.name=dojo", "commit", "-q", "-m", f"start {level.slug}"],
        cwd=workspace,
        check=False,
    )
    write_state({"level": level.slug, "started_at": time.time(), "hints_seen": 0, "checks": 0})
    print(level.brief)
    where = level.paths["copy_to"].relative_to(ROOT)
    print(f"\nTime box: {level.minutes} minutes. Clock started. The code is in {where}/.")
    if level.demo:
        print(f"Reproduce a ticket:  python dojo.py demo {level.demo[0]}")
    print("Grade yourself:      python dojo.py check")


def cmd_check(args: argparse.Namespace) -> None:
    state = read_state()
    level = find_level(state["level"])
    state["checks"] += 1
    write_state(state)
    result = run_tests(level.runtime, "workspace", args.pytest_args, quiet=not args.verbose)
    failed = result.failed
    by_module: dict[str, int] = {}
    for name in failed:
        module = name.split("::")[0].replace("tests/test_", "").replace(".py", "").replace(".test.tsx", "").replace(".test.ts", "")
        by_module[module] = by_module.get(module, 0) + 1
    if args.verbose:
        print(result.output)
    print(f"[{elapsed(state)} elapsed, check #{state['checks']}, {len(level.mutations)} bugs planted]")
    if not failed and result.returncode == 0:
        print("All tests pass. Now: did you fix the cause or the symptom? Compare with: python dojo.py solution")
        return
    if result.returncode not in (0, 1):
        print("The test run itself broke (import error or syntax error). Run with -v to see it.")
    print(f"{len(failed)} failing test(s):")
    for module, count in sorted(by_module.items()):
        print(f"  {module:<14} {count}")
    if args.verbose or args.names:
        for name in failed:
            print("  -", name)
    else:
        print("Add --names to see test names, -v for full output (less realistic, more help).")


def cmd_demo(args: argparse.Namespace) -> None:
    level = find_level(read_state()["level"])
    if level.runtime != "py":
        sys.exit("demo scenarios exist for the Python levels only; for ts/ use `npx vitest` or a scratch test")
    workspace = level.paths["workspace"]
    cmd = [PY, "-m", "supportdesk.demo", *args.scenario]
    env = {**os.environ, "PYTHONPATH": str(workspace)}
    sys.exit(subprocess.run(cmd, cwd=workspace, env=env).returncode)


def cmd_hint(args: argparse.Namespace) -> None:
    state = read_state()
    level = find_level(state["level"])
    n = args.n if args.n is not None else state["hints_seen"] + 1
    if n < 1 or n > len(level.hints):
        sys.exit(f"this level has {len(level.hints)} hints")
    state["hints_seen"] = max(state["hints_seen"], n)
    write_state(state)
    print(f"hint {n}/{len(level.hints)} [{elapsed(state)}]: {level.hints[n - 1]}")


def cmd_diff(_: argparse.Namespace) -> None:
    level = find_level(read_state()["level"])
    subprocess.run(["git", "--no-pager", "diff"], cwd=level.paths["workspace"], check=False)


def cmd_solution(_: argparse.Namespace) -> None:
    state = read_state()
    level = find_level(state["level"])
    print(f"{level.title}: {len(level.mutations)} planted bugs  [{elapsed(state)} elapsed, {state['hints_seen']} hints]\n")
    for i, m in enumerate(level.mutations, 1):
        print(f"{i}. {m.file}  ({m.kind})")
        print(f"   {m.why}")
        for line in m.new.strip("\n").splitlines():
            print(f"   - {line}")
        for line in m.old.strip("\n").splitlines():
            print(f"   + {line}")
        print()
    print("Your diff vs the planted version: python dojo.py diff")


def cmd_reset(_: argparse.Namespace) -> None:
    for paths in RUNTIMES.values():
        if paths["workspace"].exists():
            shutil.rmtree(paths["workspace"])
    if STATE_FILE.exists():
        STATE_FILE.unlink()
    print("workspace copies removed")


def cmd_verify(_: argparse.Namespace) -> None:
    """Every planted bug must be caught by at least one test, and the reference must be green."""
    ok = True
    levels = load_levels()
    runtimes = sorted({lv.runtime for lv in levels})
    for runtime in runtimes:
        result = run_tests(runtime, "reference", [], quiet=True)
        if result.returncode != 0 or result.failed:
            ok = False
            print(f"reference ({runtime}) FAILS:\n" + result.output)
        else:
            print(f"reference ({runtime}): all tests pass")
    for level in levels:
        paths = level.paths
        with tempfile.TemporaryDirectory(dir=paths["test_cwd"], prefix="verify-") as tmp:
            target = Path(tmp) / paths["copy_to"].name
            for i, m in enumerate(level.mutations, 1):
                copy_reference(paths["reference"], target)
                try:
                    apply_mutations(target, [m])
                except RuntimeError as error:
                    ok = False
                    print(f"  {level.slug} #{i}: {error}")
                    continue
                res = run_tests(level.runtime, Path(tmp).name, [], quiet=True)
                if not res.failed:
                    ok = False
                    print(f"  {level.slug} #{i} ({m.file}): NOT CAUGHT by any test")
                else:
                    print(f"  {level.slug} #{i} ({m.file}): caught by {len(res.failed)} test(s)")
            copy_reference(paths["reference"], target)
            apply_mutations(target, level.mutations)
            res = run_tests(level.runtime, Path(tmp).name, [], quiet=True)
            print(f"{level.slug}: all {len(level.mutations)} bugs -> {len(res.failed)} failing tests")
    print("verify:", "OK" if ok else "PROBLEMS")
    sys.exit(0 if ok else 1)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list").set_defaults(fn=cmd_list)
    p = sub.add_parser("start")
    p.add_argument("level")
    p.add_argument("--force", action="store_true")
    p.set_defaults(fn=cmd_start)
    p = sub.add_parser("check")
    p.add_argument("-v", "--verbose", action="store_true")
    p.add_argument("--names", action="store_true")
    p.add_argument("pytest_args", nargs="*", help="extra args passed to pytest / vitest")
    p.set_defaults(fn=cmd_check)
    p = sub.add_parser("demo")
    p.add_argument("scenario", nargs="*")
    p.set_defaults(fn=cmd_demo)
    p = sub.add_parser("hint")
    p.add_argument("n", type=int, nargs="?")
    p.set_defaults(fn=cmd_hint)
    sub.add_parser("diff").set_defaults(fn=cmd_diff)
    sub.add_parser("solution").set_defaults(fn=cmd_solution)
    sub.add_parser("reset").set_defaults(fn=cmd_reset)
    sub.add_parser("verify").set_defaults(fn=cmd_verify)
    args = parser.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
