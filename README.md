# tiered-a11y-audit

An accessibility audit skill for [Claude Code](https://docs.claude.com/en/docs/claude-code). You point it at a repository that has a user interface, it reads the code and, where possible, the running app, and it writes you a report that is sorted by how disruptive each fix is rather than by rule number.

This file is written to be read aloud. Sections have a fixed shape: one paragraph, then one list or one table, then any detail. Tables have at most four columns and never hold a fact that is not also in the text. Abbreviations are spelled out the first time.

## Why sorting by disruption matters

Most accessibility audits hand a team a long list sorted by success criterion. The team reads it, agrees with it, and ships none of it, because every line looks like it needs a designer, a sprint and an argument. Sorting by disruption separates the part that needs none of that from the part that does.

The audit uses three tiers. The next list gives all three, with the promise each one makes to the team.

- **Tier 1**, invisible improvements. A sighted mouse user with default settings sees no difference at all. This covers accessible names, semantics, focus management, announcements, support for reduced motion and forced colours, and tooling. A team can ship this today, without asking anyone.
- **Tier 2**, small and non-shocking adjustments. Visible, but the product stays instantly recognisable. A brand colour shifted in lightness only, with the perceptual difference computed and stated. Underlined links. One pixel more text. A target grown to 24 pixels. A designer signs this off in one sprint.
- **Tier 3**, the road to a ten. Everything larger: triple-A criteria, redesigns, plain-language rewrites, new features, testing with disabled people, process and continuous integration.

Severity is tracked separately from tier, and the two are independent. A blocker can sit in tier 1, because a missing label is invisible to fix. A nicety can sit in tier 3, because it needs a redesign.

## What a run does

A run has seven phases. The next list names them in order.

1. **Orient.** A detector reads the repository: frameworks, interface libraries, styling, routing, translations, existing accessibility tooling, suppressed lint rules, interfaces embedded in source strings, vendored themes and build output. From the size of what it finds, it picks how large the audit should be.
2. **Ask once.** One message, at most five numbered questions, each with its default, so that answering "ok" answers all of them. The questions cover the ignore file, the runtime, permission to install, whether the running app may be changed, and which flows matter.
3. **Pre-compute with scripts.** Every accessibility grep, the colour tokens and the failing contrast pairs. With a runtime it also runs axe-core in both colour schemes, walks the page with the Tab key, checks reflow at 320 pixels, text spacing, reduced motion and target sizes, and captures the accessibility tree per view.
4. **Run six expert lenses in parallel.** Semantics and structure, keyboard and focus, visual perception, forms and input, dynamic content, content and media. Each lens owns a fixed set of the 55 level A and level AA criteria of version 2.2 of the Web Content Accessibility Guidelines, and reports pass, fail, not tested or not applicable for every single one it owns. That is what makes the coverage matrix real instead of guessed.
5. **Merge, deduplicate and verify.** A script merges the findings, derives the tier from the visual impact, clusters findings that share a root cause, and builds the coverage matrix. The orchestrator then decides which findings are duplicates, and opens the code or the page for every blocker before anything is built on top of it.
6. **Run the personas.** Subagents simulate people who depend on assistive technology: a screen-reader user, a low-vision user at 400 percent zoom, a voice-control and keyboard user, a user with dyslexia and attention deficit, a colour-blind user, a Deaf user, a user with a vestibular disorder, and an older novice. Each one walks the key flows first and reads the expert findings only afterwards, so that they are a second opinion rather than an echo. Each step of a walk carries its evidence, and a flow a persona could not finish raises the severity of the findings that caused it.
7. **Write the report.** In the language you are speaking, whichever that is: English and Dutch labels ship with the skill and any other language is translated once, with a summary a screen-reader user can stop reading after, a table per tier, a fix per finding written in the idiom of your own stack, the personas in their own words, structural advice, and appendices. A script then checks the finished report: nothing left unwritten, no finding dropped, and the read-aloud rules kept. A second audit of the same repository compares against the first on stable fingerprints and reports what is resolved, still open, regressed or new.

Alongside the personas, a framework-maximizer looks for the single token, base component or hook that would fix several findings at once.

There are six modes: a full audit, a lean audit for a small interface, a mini audit for a handful of files without forms, a focused review of one component or pull request, a re-audit, and a mode that applies the fixes.

The findings can be exported three ways: as SARIF 2.1.0, the Static Analysis Results Interchange Format that GitHub and GitLab code scanning read; as a draft conformance table in the style of an Accessibility Conformance Report, for whoever has to sign one; and as comma-separated values for a ticket system.

## Install

The skill itself lives in the `skills/tiered-a11y-audit/` subdirectory, which is what makes the repository loadable as a plugin as well. The repository root has no `SKILL.md` of its own, so a personal install has to link the subdirectory, not the root.

First clone the repository:

```bash
git clone https://github.com/Timdebruijn/tiered-a11y-audit ~/src/tiered-a11y-audit
```

Then link the skill directory into your personal skills folder:

```bash
mkdir -p ~/.claude/skills && ln -s ~/src/tiered-a11y-audit/skills/tiered-a11y-audit ~/.claude/skills/tiered-a11y-audit
```

As an alternative, load the whole repository as a plugin for one session. This is also how the evaluation cases load it:

```bash
claude --plugin-dir ~/src/tiered-a11y-audit
```

Afterwards, in any repository, ask in your own words: "maak een toegankelijkheidsrapport van deze site", or "how accessible is this app?". The skill asks its questions, runs for 20 to 45 minutes depending on the mode, and leaves everything in a folder called `.a11y-audit`. It asks permission to add that folder to your ignore file before it writes anything.

You need Python 3 for the scripts, which use the standard library only. For the runtime checks you also need Node, and permission to install `playwright` and `@axe-core/playwright` into a throwaway directory. An already installed Chrome or Edge avoids the browser download.

## What it costs

Two sets of numbers follow: the estimates from real runs on real repositories, and the measured numbers from the evaluation cases. They are listed separately because the measured run did something the estimates do not describe.

From real runs, a full audit is 13 to 15 subagents and 1 to 1.5 million subagent tokens. A lean audit is about 10 subagents and 0.5 to 0.7 million tokens. A mini audit is about 5 subagents and 0.3 million. All three take 20 to 45 minutes of wall-clock time, because the orchestrator's own verification takes about as long as the agents do.

The next table lists the three measured evaluation cases, with the tokens, the cost and the wall-clock time of each. In words: the full fixture audit took 1.29 million tokens, 2 dollars 59 and about 12 minutes; the focused review took 43 thousand tokens, 21 cents and about a minute; the case that declines took 110 thousand tokens, 25 cents and 34 seconds. Judging adds 2 to 24 cents per case on top.

| Case | Tokens | Cost | Time |
|---|---|---|---|
| Full audit of the fixture site | 1.29 million | 2 dollars 59 | 12 minutes |
| Focused review of a contact form | 43 thousand | 21 cents | 1 minute |
| Declining a repository without an interface | 110 thousand | 25 cents | 34 seconds |

Those were measured on 6 November 2026, with Claude Code 2.1.319 on Opus, one run per arm. Tokens are the run total including cache reads, which is most of the number.

One warning about the figures. The full audit does land inside the 1-to-1.5-million range above, but it did so on a fixture of four files and 252 lines, and with no subagents at all. A real repository spreads that same token count over 13 to 15 agents instead of one context.

A second warning about running the suite yourself. The ablation option defaults to comparing with and without the plugin, and the number of runs defaults to three, so the full suite is six complete audits unless you ask for one run.

## How well it works, measured

The detection rate is 21 of 24, or 88 percent, on the fixture site. That is one run, on 6 November 2026, with Claude Code 2.1.319 on Opus, using static analysis only. It was scored by `grade_findings.py` against the ground-truth file that ships with the fixture.

The number hides something in both directions, and the detail blocks below give each one.

### All 24 seeded failures were actually found

The three that the grader counts as missed are criterion-attribution failures rather than blind spots. The generic "read more" links were reported against criterion 2.4.9, which is level AAA, where the ground truth expects 2.4.4 at level A. The missing skip link and the blocked paste on the password field were both reported with an empty criterion list. By substance the result is 24 of 24. By the grader's rule, which requires the criterion to match, it is 21.

### Nearly a fifth of findings carried no criterion at all

8 of 42 findings, which is 19 percent, named no success criterion, and the merge script did not flag a single one of them. Its list of problems came back empty. The skill's own ground rules require either a criterion or an explicit best-practice marker on every finding, so this is a real gap in the schema check, and it is what cost two of the three detections above. The merge script has since been taught to flag it: a finding without a criterion and without the marker, a criterion that is triple-A only, a citation that does not exist in the repository and a contrast ratio that does not match its colours are now all listed as problems to resolve. No run has been measured with that check in place yet.

### Four findings landed one tier off

4 of the 24 were placed in the wrong tier, all of them adjacent to the right one. Carousel autoplay, the colour-only status dots and the 13-pixel root font size were put in tier 1 where they belong in tier 2. Placeholder-only labels were put in tier 2 where they belong in tier 1.

### One of the four should-pass items was flagged

The carousel slides were flagged for carrying alt text reading "Slide 1", "Slide 2" and "Slide 3". That is arguably a fair finding about non-descriptive alternative text rather than a false positive, but it counts against the fixture as it is written today.

## Limitations, honestly

The next list gives the eight things this skill does not do, or does not yet know about itself.

- **Simulated personas.** They are role-played by an AI. They are good at catching what checklists miss. A colour-blind persona once found two palette tokens, both thought safe, collapsing into each other under deuteranopia, and nothing else caught it. They are still not a substitute for testing with disabled people. The report says so, and tier 3 asks for that testing explicitly.
- **Tools find little.** Automated checks catch a minority of real issues. The expert lenses do the work, and the orchestrator verifies every blocker by opening the code or the page.
- **No subagents measured.** The fixture does not exercise that pipeline. It is four files and 252 lines, and on that the orchestrator ran all six lenses and five personas itself instead of spawning subagents: zero delegation calls, although delegation was available. It said so plainly in its own report, so this is a disclosed shortcut rather than a fabrication. It does mean the 88 percent is an orchestrator-only number, and that the 13-to-15-subagent workflow has no measurement behind it yet.
- **Ignore the case score.** The 7 out of 21 graders says more about the grading than about the audit. The detail block below explains why.
- **No trigger on focused reviews.** The skill does not fire there at all. In both arms of that case the only tool calls were three file reads and no skill invocation, so the three-tier structure the grader checks was simply absent and the measured difference was zero. Nothing was gained because nothing was measured. The prompt does contain the Dutch word for accessible, which is in the trigger list, but for a single form the model chooses to answer directly.
- **Three stacks proven.** Those codebases have a real run behind them. Those are ESP32 firmware with HTML inside C++ strings, a React single-page application with canvas charts and a strict Content Security Policy, and a themed bilingual Hugo site. Other stacks have playbooks written for them but no run yet. Try it first on something you can afford to be wrong about, and read the feedback notes it leaves when something looked off.
- **Scripts go in the scratch directory.** The runtime scan needs them there. Node resolves imports from the directory the script itself sits in, so a script left in the skill folder cannot find the installed packages. The skill handles this; anything hand-written has to do the same.
- **No overlay widgets, ever.** The skill refuses to recommend one. They do not achieve conformance and they frequently make assistive technology worse.

### Why the case score is low

Every grader judges the trace with a language model, and such a judge sees only the first 12 and the last 12 messages of that trace. That is a documented limit rather than a defect.

A full audit is 160 messages. The judge therefore received 24 of them, with 136 elided in the middle, and then marked things absent that it never saw. The report does contain the four score values, the persona matrix and the contrast fix that it was marked down for missing.

The repair is to grade the written artefacts instead of the trace, and to use the deterministic grader types for questions such as whether a given script ran. Until that is done, read the detection rate and ignore the case score.

## Running the evaluation cases

Four cases live in the `evals/` directory, which is where the evaluation runner looks by default. They need the plugin manifest in `.claude-plugin/plugin.json` to resolve the skill, and they need three tools that are stripped unless you grant them explicitly. Run this from the repository root:

```bash
claude plugin eval . --scaffold --allow-tools Bash Write Edit --no-publish
```

The scaffold option runs each case's `place-files.sh`, which writes the fixture site into a temporary directory. Remember that this is six complete audits by default, as explained under costs above; pass one run to halve it, and use the case option to pick a single case. Results land in `evals/results/`, which is ignored by git.

To score the detection rate yourself, add the option that keeps the temporary directory. Without it the scaffold directory is deleted, and the merged findings file the grader reads goes with it. The run prints the path it kept, which has to be opened first with `chmod 700` on the directory and its `sealed` subdirectory. Then run:

```bash
python3 skills/tiered-a11y-audit/scripts/grade_findings.py <kept>/sealed/home/cwd/.a11y-audit/findings/_merged.json evals/full-audit-fixture-site/ground-truth.json
```

## Repository layout

The next list gives every directory that matters, with what it holds.

- `.claude-plugin/plugin.json` is the plugin manifest. Without it the repository is not a plugin and the evaluation runner has nothing to load.
- `skills/tiered-a11y-audit/SKILL.md` is the workflow itself, and the file Claude Code reads.
- `skills/tiered-a11y-audit/agents/experts/` holds the six lenses, the framework-maximizer, and the protocol they share.
- `skills/tiered-a11y-audit/agents/personas/` holds the eight personas and the protocol they share.
- `skills/tiered-a11y-audit/references/` holds the tiering rules, the finding schema, the criterion ownership table, the framework playbooks, the report template, the tooling notes, and the report labels per language.
- `skills/tiered-a11y-audit/scripts/` holds the detector, the pattern scanner, the colour extractor, the contrast tool, the accessibility-tree digest, the runtime scan, the briefing builder, the merge and coverage script, the renderer that writes the draft report, and the linter that checks the finished one.
- `evals/` holds the four test cases with their fixture sites. It stays at the repository root, because that is where the evaluation runner looks.

## Contributing

The most useful thing you can contribute is a run on a stack that has no run behind it yet, together with the feedback file the orchestrator writes when you ask it to review the skill afterwards. Corrections to the playbooks are the second most useful: version-gated features and library quirks age fastest. Please keep the three tiers and keep severity independent of them, because that separation is the whole point.

## License

MIT
