# Security policy

tiered-a11y-audit is a Claude Code plugin. It runs on your machine, as you, in
a session you started: it reads the repository you point it at, runs the
scripts in `skills/tiered-a11y-audit/scripts/` over it, and where a runtime is
available it drives a browser against your running application. It has no
backend of its own, no telemetry and no listening service; what leaves your
machine is whatever your Claude Code session already sends.

That shapes what a vulnerability here looks like.

## Reporting a vulnerability

Use GitHub's **private vulnerability reporting** on this repository
(Security › Report a vulnerability). Please do not open a public issue or pull
request for a security problem.

Useful to include: the plugin version, the Claude Code version, the mode you
ran (full, lean, mini, component), and the smallest repository, page or file
that shows the problem.

This is a one-person project. Reports are read as soon as there is time, with
no promised response time. A confirmed fix goes into the next release, and you
are credited unless you prefer otherwise.

## Supported versions

Only the latest release. An installed plugin moves only when the version in
`.claude-plugin/plugin.json` changes, so what is merged between two releases
does not reach an installation until the next one.

## What counts

- **A script that reaches further than it should.** The scripts read the
  repository and write the report. One that writes outside the working
  directory, executes something from the repository it scanned, or sends data
  anywhere is a finding.
- **Scanned content that steers the audit.** The files it reads and the pages
  it opens are untrusted input. An instruction hidden in a source file, a page
  or an `alt` attribute that changes what the agents do, what the report says,
  or what gets run, is a finding and an interesting one.
- **Anything installed or changed without the question being asked.** The
  audit asks once, in one message, before installing tooling and before
  touching a running app.

## Scope and known limits

- It runs with your permissions and is not a sandbox. Reading what a skill
  does before installing it stays your call, as with any plugin.
- Saying yes to the install question installs a browser and its dependencies.
  That is the question doing its job, not a flaw.
- It writes its report into your working directory.
- The personas are role-played by an AI. That is a limit of the audit's
  findings, not a security property.
