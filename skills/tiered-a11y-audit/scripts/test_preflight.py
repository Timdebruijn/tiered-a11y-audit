#!/usr/bin/env python3
"""Self-check for preflight.py: Phase 0 writes nothing, and --start sets the workspace up without losing anything.

    python3 scripts/test_preflight.py

The script runs in someone else's repository, so most of this is about what it must leave alone.
Standard library and git only, writes to a temp dir.
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from preflight import mode_for  # noqa: E402

EMPTY = Path(tempfile.mkdtemp())


def repo(git=True, ignore=None):
    root = Path(tempfile.mkdtemp()).resolve()
    (root / "index.html").write_text("<!doctype html><html lang=en><title>x</title><main><h1>x</h1></main></html>", encoding="utf-8")
    if git:
        subprocess.run(["git", "init", "-q", str(root)], check=True)
    if ignore is not None:
        (root / ".gitignore").write_bytes(ignore)
    return root


def run(root, *args, path=None, attended="1"):
    # The answer must come from the repository alone: no global or system git config, no global ignore file,
    # and no git repository above the temp dir.
    env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1", "XDG_CONFIG_HOME": str(EMPTY),
           "GIT_CEILING_DIRECTORIES": str(Path(root).parent)}
    if path is not None:
        env["PATH"] = path
    env.pop("CLAUDE_CODE_SESSION_ATTENDED", None)           # this test may itself run inside an attended or unattended session
    if attended is not None:
        env["CLAUDE_CODE_SESSION_ATTENDED"] = attended
    return subprocess.run([sys.executable, str(HERE / "preflight.py"), str(root), *args], capture_output=True, text=True, env=env)


def tree(root):
    """Every file outside .git with its content, and every directory."""
    return {str(p.relative_to(root)): (p.read_bytes() if p.is_file() else None)
            for p in sorted(root.rglob("*")) if ".git" not in p.relative_to(root).parts}


def line(out, label):
    return next(row for row in out.splitlines() if row.startswith(f"- {label}:"))


def fill(ws, *rels):
    for rel in rels:
        (ws / rel).parent.mkdir(parents=True, exist_ok=True)
        (ws / rel).write_text(rel, encoding="utf-8")


def test_phase_0_reports_and_writes_nothing():
    root = repo(ignore=b"node_modules/\n")
    fill(root / ".a11y-audit", "stack-detect.md", "stack-profile.md", "findings/keyboard-focus.json")
    before = tree(root)
    r = run(root)
    assert r.returncode == 0, r.stderr
    assert tree(root) == before, "the read-only run changed the repository"
    for want in ("- Git repository: yes", "- .a11y-audit/ ignored by git: no", "- Project-owned UI files: 1", "mini candidate", "# Stack detection"):
        assert want in r.stdout, f"missing: {want}\n{r.stdout[:600]}"
    plain = run(repo(git=False))
    assert "- Git repository: no" in plain.stdout and "ignored by git: not applicable" in plain.stdout


def test_a_git_that_cannot_answer_is_not_reported_as_no_repository():
    out = run(repo(), path=str(EMPTY)).stdout
    assert "- Git repository: unknown (git is not installed)" in out and "ignored by git: unknown" in out, out[:400]


def test_an_unattended_session_is_told_not_to_wait():
    root = repo()
    yes, no, unknown = (run(root, attended=a).stdout for a in ("1", "0", None))
    assert "- Someone to answer questions: yes: ask the Phase 1 questions and wait" in yes and "After the user's answer, run this script again with --start." in yes
    assert "- Someone to answer questions: no, this session is unattended. Your next message is the Phase 1 message" in no and "go on without waiting" in no
    assert "without --ignore" in no and "After the user's answer" not in no, "an unattended run was still told to wait for an answer"
    assert "- Someone to answer questions: unknown: ask the Phase 1 questions and wait" in unknown and "After the user's answer" in unknown
    assert "unknown" in line(run(root, attended="maybe").stdout, "Someone to answer questions"), "an unexpected value must not read as yes or no"


def test_ignored_means_every_kind_of_file_in_the_workspace():
    cases = {b"": "no",
             b"*.json\n": "partly",                                                                     # screenshots would be committed
             b".a11y-audit/*\n!.a11y-audit/findings/\n!.a11y-audit/findings/*\n": "partly",            # a negation is not an ignore
             b".a11y-audit\n": "yes (.gitignore:1:.a11y-audit)",
             b".a11y-audit/*\n!.a11y-audit/REPORT.md\n": "yes (.gitignore:1:.a11y-audit/*), REPORT.md stays trackable"}
    for content, want in cases.items():
        got = line(run(repo(ignore=content)).stdout, ".a11y-audit/ ignored by git")
        assert got.split(": ", 1)[1].startswith(want), f"{content!r}: {got}"


def test_a_backend_beside_the_frontend_is_named_and_the_count_is_explained():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "web").mkdir()
        (root / "web/index.html").write_text('<!doctype html><html lang="en"><head><title>x</title></head><body></body></html>')
        (root / "web/util.ts").write_text("export const add = (a: number, b: number) => a + b\n")
        (root / "web/package.json").write_text('{"scripts": {"dev": "vite", "preview": "vite preview"}}')
        out = run(root).stdout
        (root / "web/App.tsx").write_text("export const App = () => <main>hi</main>\n")
        out = run(root).stdout
        assert line(out, "Project-owned UI files") == "- Project-owned UI files: 2 (TSX 1, HTML 1); not counted: 1 scripts of logic beside the components", line(out, "Project-owned UI files")
        assert "- Backend:" not in out
        (root / "go.mod").write_text("module example.test/app\n")
        out = run(root).stdout
        assert "(go.mod)" in line(out, "Backend") and "ask how the whole application is started" in line(out, "Backend")
        assert line(out, "Backend")[len("- Backend: "):] in out.split("\n# Stack detection")[1], "the preflight and the detector say the same thing"


def test_audit_size_follows_the_thresholds_of_the_skill():
    assert [mode_for(n).split()[0] for n in (0, 1, 10, 11, 25, 26)] == ["none:", "mini", "mini", "lean", "lean", "full"]


def test_start_creates_the_workspace_and_leaves_gitignore_alone():
    root = repo()
    r = run(root, "--start")
    assert r.returncode == 0, r.stderr
    assert (root / ".a11y-audit" / "stack-detect.md").read_text(encoding="utf-8").startswith("# Stack detection")
    assert not (root / ".gitignore").exists() and ".gitignore: not changed" in r.stdout
    assert "earlier audit" not in r.stdout and not (root / ".a11y-audit" / "previous").exists(), "a first audit has nothing to move"
    assert line(run(root).stdout, "Earlier audit").endswith(": no") and "unfinished" not in run(root, "--start").stdout, "a workspace with only the detector output is not a run"
    for flag in ("--ignore", "--fresh"):
        other = repo()
        before = tree(other)
        assert run(other, *([flag, "all"] if flag == "--ignore" else [flag])).returncode == 2 and tree(other) == before, f"{flag} without --start wrote"


def test_ignore_appends_once_and_never_rewrites_what_is_there():
    odd = b"node_modules/\r\ncaf\xe9.txt"                                        # CRLF, not UTF-8, no newline at the end
    root = repo(ignore=odd)
    run(root, "--start", "--ignore", "report")
    run(root, "--start", "--ignore", "report")
    assert (root / ".gitignore").read_bytes() == odd + b"\r\n.a11y-audit/*\r\n!.a11y-audit/REPORT.md\r\n!.a11y-audit/coverage.md\r\n"
    assert "yes (.gitignore:3:.a11y-audit/*), REPORT.md stays trackable" in run(root).stdout
    other = repo()
    run(other, "--start", "--ignore", "all")
    assert (other / ".gitignore").read_bytes() == b".a11y-audit/\n"
    assert line(run(other).stdout, ".a11y-audit/ ignored by git").endswith("yes (.gitignore:1:.a11y-audit/)")


def test_ignore_does_not_add_lines_that_cannot_work():
    root = repo(ignore=b".a11y-audit\n")                                         # the whole workspace, spelled without the slash
    r = run(root, "--start", "--ignore", "report")
    assert (root / ".gitignore").read_bytes() == b".a11y-audit\n" and "cannot be made trackable" in r.stdout, r.stdout
    r = run(root, "--start", "--ignore", "all")
    assert (root / ".gitignore").read_bytes() == b".a11y-audit\n" and r.stdout.rstrip().endswith(".gitignore: not changed"), r.stdout


def test_ignore_does_not_write_through_a_symbolic_link():
    root = repo()
    target = Path(tempfile.mkdtemp()) / "dotfiles-ignore"
    target.write_bytes(b"*.log\n")
    (root / ".gitignore").symlink_to(target)
    r = run(root, "--start", "--ignore", "all")
    assert target.read_bytes() == b"*.log\n" and "symbolic link" in r.stdout, r.stdout


def test_a_workspace_that_is_no_plain_directory_is_refused():
    root = repo()
    (root / ".a11y-audit").write_text("mine", encoding="utf-8")
    assert "not a plain directory" in line(run(root).stdout, "Earlier audit")
    r = run(root, "--start")
    assert r.returncode == 2 and "nothing was written" in r.stderr and (root / ".a11y-audit").read_text(encoding="utf-8") == "mine"
    linked = repo()
    elsewhere = Path(tempfile.mkdtemp())
    (linked / ".a11y-audit").symlink_to(elsewhere, target_is_directory=True)
    assert run(linked, "--start").returncode == 2 and list(elsewhere.iterdir()) == [], "wrote outside the repository through a link"


def test_a_run_in_progress_is_left_in_place():
    root = repo()
    ws = root / ".a11y-audit"
    assert run(root, "--start").returncode == 0
    fill(ws, "stack-profile.md", "briefs/_agents.json", "findings/keyboard-focus.json")
    assert "an unfinished run is in the workspace" in line(run(root).stdout, "Earlier audit")
    before = tree(ws)
    r = run(root, "--start")                                                    # for example after the orchestrator lost its context
    after = tree(ws)
    assert "left in place" in r.stdout and not (ws / "previous").exists(), r.stdout
    assert {k: v for k, v in after.items() if k != "stack-detect.md"} == {k: v for k, v in before.items() if k != "stack-detect.md"}
    r = run(root, "--start", "--fresh")
    assert (ws / "previous" / "findings" / "keyboard-focus.json").is_file() and not (ws / "findings").exists()
    assert "it has no merge, so there is nothing to compare against" in r.stdout, r.stdout


def test_a_finished_audit_is_moved_aside_as_a_whole_and_nothing_is_deleted():
    root = repo()
    ws = root / ".a11y-audit"
    fill(ws, "findings/keyboard-focus.json", "findings/_merged.json", "personas/screen-reader-user.md", "briefs/_agents.json",
         "automated/summary.json", "REPORT.md", "coverage.md", "report-ids.json", "delta.md", "report-labels.de.json", "previous/REPORT.md")
    assert "yes, finished" in line(run(root).stdout, "Earlier audit")
    r = run(root, "--start")
    assert r.returncode == 0 and "this is a re-audit" in r.stdout, r.stdout + r.stderr
    now = sorted(p.name for p in ws.iterdir())
    older = [n for n in now if n.startswith("previous-")]
    assert len(older) == 1 and (ws / older[0] / "REPORT.md").read_text(encoding="utf-8") == "previous/REPORT.md", "the older audit was lost"
    assert sorted(set(now) - set(older)) == ["previous", "report-labels.de.json", "stack-detect.md"], now
    assert sorted(p.name for p in (ws / "previous").iterdir()) == ["REPORT.md", "automated", "briefs", "coverage.md", "delta.md", "findings",
                                                                    "personas", "report-ids.json"]
    assert (ws / "previous" / "findings" / "keyboard-focus.json").read_text(encoding="utf-8") == "findings/keyboard-focus.json"
    again = run(root, "--start")
    assert "earlier audit" not in again.stdout and (ws / "previous" / "REPORT.md").exists(), "a second start moved the audit again"
    report_only = repo()                                                         # an older report without findings is an earlier audit too
    fill(report_only / ".a11y-audit", "REPORT.md", "stack-profile.md")
    run(report_only, "--start")
    assert sorted(p.name for p in (report_only / ".a11y-audit" / "previous").iterdir()) == ["REPORT.md", "stack-profile.md"]


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"ok  {t.__name__}")
    print(f"{len(tests)} checks passed")
