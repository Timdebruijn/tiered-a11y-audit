# tiered-a11y-audit

An accessibility audit skill for [Claude Code](https://code.claude.com/docs/en/overview). You point it at a repository that has a user interface, it reads the code and, where possible, the running app, and it writes you a report that is sorted by how disruptive each fix is rather than by rule number.

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

1. **Orient.** One read-only command checks the git and ignore status, looks for an earlier audit and for the tools a runtime scan needs, and runs a detector over the repository: frameworks, interface libraries, styling, routing, translations, existing accessibility tooling, suppressed lint rules, interfaces embedded in source strings, vendored themes and build output. From the size of what it finds, it picks how large the audit should be.
2. **Ask once.** One message, at most five numbered questions, each with its default, so that answering "ok" answers all of them. The questions cover the ignore file, the runtime, permission to install, whether the running app may be changed, and which flows matter. In a run with nobody to answer, such as a pipeline, it does not wait: it takes for each question the option that needs no permission, leaves the ignore file alone, and says so in its reply.
3. **Pre-compute with scripts.** Every accessibility grep, the colour tokens and the failing contrast pairs. With a runtime it also runs axe-core in both colour schemes, walks the page with the Tab key, checks reflow at 320 pixels, text spacing, reduced motion and target sizes, and captures the accessibility tree per view.
4. **Run six expert lenses in parallel.** Semantics and structure, keyboard and focus, visual perception, forms and input, dynamic content, content and media. Each lens owns a fixed set of the 55 level A and level AA criteria of version 2.2 of the Web Content Accessibility Guidelines, and reports pass, fail, not tested or not applicable for every single one it owns. That is what makes the coverage matrix real instead of guessed.
5. **Merge, deduplicate and verify.** A script merges the findings, derives the tier from the visual impact, clusters findings that share a root cause, and builds the coverage matrix. The orchestrator then decides which findings are duplicates, and opens the code or the page for every blocker before anything is built on top of it. From the pre-computation onward, a script checks at the end of each phase that its output is complete and current before the next phase starts.
6. **Run the personas.** Subagents simulate people who depend on assistive technology: a screen-reader user, a low-vision user at 400 percent zoom, a voice-control and keyboard user, a user with dyslexia and attention deficit, a colour-blind user, a Deaf user, a user with a vestibular disorder, and an older novice. Each one walks the key flows first and reads the expert findings only afterwards, so that they are a second opinion rather than an echo. Each step of a walk carries its evidence, and a flow a persona could not finish raises the severity of the findings that caused it.
7. **Write the report.** In the language you are speaking, whichever that is. The agents write their findings in that language from the start, so nothing is translated afterwards. A script assembles the report from those findings and from the orchestrator's own prose, and nobody edits it by hand. It holds a summary a screen-reader user can stop reading after, a table per tier, a fix per finding written in the idiom of your own stack, the personas in their own words, structural advice, and appendices. The fixed words of the report ship in English and Dutch, and for any other language they are translated once. A second script then checks the finished report: nothing left unwritten, no finding dropped, and the read-aloud rules kept. A second audit of the same repository compares against the first on stable fingerprints and reports what is resolved, still open, regressed or new.

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

Afterwards, in any repository, ask in your own words: "maak een toegankelijkheidsrapport van deze site", or "how accessible is this app?". The skill asks its questions, runs from under ten minutes for a small site read from its code to 45 minutes for a full audit with a running app, and leaves everything in a folder called `.a11y-audit`. It asks permission to add that folder to your ignore file before it writes anything.

You need Python 3.9 or newer for the scripts, which use the standard library only, and git if you want the skill to check your ignore file. For the runtime checks you also need Node, and permission to install `playwright` and `@axe-core/playwright` into a throwaway directory. An already installed Chrome or Edge avoids the browser download.

## What it costs

Two sets of numbers follow: the estimates from real runs on real repositories, and the measured numbers from the evaluation cases. They are listed separately because they come from different repositories and count tokens differently, as the first warning below explains.

From real runs with the version before 1.1.0, a full audit is 13 to 15 subagents and 1 to 1.5 million subagent tokens. A lean audit is about 10 subagents and 0.5 to 0.7 million tokens. A mini audit is about 5 subagents and 0.3 million. All three take 20 to 45 minutes of wall-clock time, because the orchestrator's own verification takes about as long as the agents do.

The next table lists the four measured evaluation cases, with the tokens, the cost and the wall-clock time of each. In words: the lean audit of the fixture site took 5.1 million tokens, 4 dollars 28 and about 10 minutes; the mini audit of the themed site took 2.2 million tokens, 2 dollars 9 and about 6 minutes; the focused review took 170 thousand tokens, 36 cents and a little over a minute; the case that declines took 90 thousand tokens, 25 cents and 34 seconds. Judging adds 3 to 25 cents per case on top.

| Case | Tokens | Cost | Time |
|---|---|---|---|
| Lean audit of the fixture site, ten subagents | 5.1 million | 4 dollars 28 | 10 minutes |
| Mini audit of the themed site, five subagents | 2.2 million | 2 dollars 9 | 6 minutes |
| Focused review of a contact form | 170 thousand | 36 cents | 1 minute |
| Declining a repository without an interface | 90 thousand | 25 cents | 34 seconds |

Those were measured on 16 November 2026, with Claude Code 2.1.319, the orchestrator on Opus and the subagents on Sonnet, one run per arm. Tokens are the run total including cache reads, which is most of the number.

One warning about the figures. The token counts are higher than the estimates above because they count every time the conversation is read again, by the orchestrator and by each subagent, while the estimates count what the subagents were given. The cost is the figure to compare. Earlier the same day, with every subagent on the top model and a separate step that translated the report, the same audit cost 10 dollars 66.

A second warning about running the suite yourself. The ablation option defaults to comparing with and without the plugin, and the number of runs defaults to three, so the full suite is six complete audits unless you ask for one run.

## How well it works, measured

The detection rate is 23 of 24, or 96 percent, on the fixture site. That is one run, on 16 November 2026, with Claude Code 2.1.319, the orchestrator on Opus and ten subagents on Sonnet, using static analysis only. It was scored by `grade_findings.py` against the ground-truth file that ships with the fixture.

One run is a sign and not a rate. The two runs before it on the same day, with nearly the same pipeline, found 22 and 24. The first measured run, on 6 November and without subagents, found 21. A run on 17 November, the first one scored with the graders described below, found 22. The detail blocks below say what the number hides.

### The one miss was found under another criterion

The social links without an accessible name were reported, against criteria 1.1.1 and 2.4.4 where the ground truth expects 4.1.2. By substance the result is 24 of 24. By the grader's rule, which requires the criterion to match, it is 23.

### Every finding now names a criterion

On 6 November, 8 of 42 findings named no success criterion, and the merge script did not flag a single one of them. The merge script has since been taught to check what a finding claims: a criterion or the explicit best-practice marker, a level A or level AA criterion, a citation that exists in the repository, a contrast ratio that matches its colours. In this run none of the 48 findings lacked a criterion or the marker, every cited snippet was found in its file, and the list of problems was empty at the end.

### Three findings landed one tier off

3 of the 24 were placed in a tier next to the right one. The carousel arrows and the errors shown by a red border alone were put in tier 2 where the fixture expects tier 1. The 13-pixel root font size was put in tier 1 where it expects tier 2.

### One of the four should-pass items was flagged

The carousel slides were flagged for carrying alt text reading "Slide 1", "Slide 2" and "Slide 3". That is arguably a fair finding about non-descriptive alternative text rather than a false positive, but it counts against the fixture as it is written today. It has been flagged in every measured run.

### The whole pipeline ran

The lean audit spawned four expert subagents, five personas and the framework-maximizer. All four phase checks passed and the report passed the linter. The orchestrator wrote its prose in one file of 72 lines and never edited the report itself. The mini audit of the themed site ran two experts, two personas and the maximizer, and separated ten findings that need a change upstream from eight the project can fix.

The focused review reaches the skill as well, which it did not on 6 November: with the plugin all six of its graders pass, and without it the answer in three tiers is missing.

## Limitations, honestly

The next list gives the nine things this skill does not do, or does not yet know about itself.

- **Simulated personas.** They are role-played by an AI. They are good at catching what checklists miss. A colour-blind persona once found two palette tokens, both thought safe, collapsing into each other under deuteranopia, and nothing else caught it. They are still not a substitute for testing with disabled people. The report says so, and tier 3 asks for that testing explicitly.
- **Tools find little.** Automated checks catch a minority of real issues. The expert lenses do the work, and the orchestrator verifies every blocker by opening the code or the page.
- **One run per number.** Every figure above is a single run. Three runs on one day found 22, 23 and 24 of the 24 seeded failures, so read 96 percent as somewhere between 22 and 24.
- **A small fixture.** It is four files and 252 lines, and one context without subagents already found 21 of the 24. What ten subagents add on a large codebase, where no single context can read everything, has no measurement behind it yet.
- **Audit case scores: one run.** In the runs above 4 of the 21 graders of the lean audit passed, and that said more about the grading than about the audit. The graders of the two audit cases have been replaced since. One run on 17 November 2026 was scored with the new ones: 0.93 for the lean audit, 39 of 42 graders, and 1.00 for the themed site, 11 of 11. The detail block below explains both, and what the three failures were.
- **Only Dutch is measured.** All four evaluation prompts are Dutch. The skill writes its findings and its report in the language you speak, and the fixed words of the report ship in English and Dutch, but no run in another language has been graded.
- **Three stacks proven.** Those codebases have a real run behind them. Those are ESP32 firmware with HTML inside C++ strings, a React single-page application with canvas charts and a strict Content Security Policy, and a themed bilingual Hugo site. Other stacks have playbooks written for them but no run yet. Try it first on something you can afford to be wrong about, and read the feedback notes it leaves when something looked off.
- **Scripts go in the scratch directory.** The runtime scan needs them there. Node resolves imports from the directory the script itself sits in, so a script left in the skill folder cannot find the installed packages. The skill handles this; anything hand-written has to do the same.
- **No overlay widgets, ever.** The skill refuses to recommend one. They do not achieve conformance and they frequently make assistive technology worse.

### What the case score of an audit measures

Up to and including release 1.1.1 every grader of the two audit cases judged the trace with a language model. Such a judge sees only the first 12 and the last 12 messages of a trace, which is a documented limit rather than a defect. A lean audit with ten subagents is several hundred messages, so the judge marked things absent that it never saw. It failed the grader for using the merge script in a run that ran that script more than once.

The graders now read what the run wrote. Most of them are patterns on a file, which cost nothing, give the same answer every time and see the whole file. The lean audit has 41 graders:

- 24 hold the report to the seeded failures, one each. A failure counts as found when a finding block cites its criterion, names its file and uses one of its keywords in the title, the problem or the fix. That is the rule of `grade_findings.py`, read from the report instead of the merged findings, which makes it stricter in two ways. Only tiers 1 and 2 have finding blocks, so a seeded failure filed in tier 3 counts as missed. And a block names at most three places, so a finding whose only evidence in the right file is its fourth place counts as missed too.
- 3 hold a finding to more than that: the missing language is in tier 1, the fix for the focus outline in tier 1 names `:focus-visible`, and the table of proposed colours in tier 2 gives the muted text another colour.
- 9 check the report and the site: the report exists, is rendered in Dutch with findings written in Dutch, leaves no part unwritten, opens its short section with prose, keeps its tables to four columns and has the four core personas in its matrix; and two of the site's own files are unchanged.
- 2 check that the merge script and the last phase check were started on the workspace. They cannot see whether the check passed.
- 3 are still judged by a language model, on short text only: the closing reply, and the prose file for the four scores and for saying that nobody confirmed the audit's choices.

The themed site has 11 graders of the same kinds. What they cannot see is listed here, because a pattern is not a reader:

- **A fixed path.** They read `site/.a11y-audit/`. An audit that puts its workspace one folder higher fails nearly all of them at once; the grader for the report file shows that this happened.
- **The arm without the plugin.** It cannot pass graders that read the skill's own files, so on these two cases the difference between the arms says only that the pipeline ran. Run them with `--ablation none` to pay for one arm.
- **Whether a finding is right.** A pattern sees that a criterion, a file and a word stand together, not that the finding is true or the fix sound.

`python3 evals/test_graders.py` defines the pattern graders and checks them against reports the real merge and renderer produce: every seeded failure is found by its own grader and by no other, and not when the criterion, the file or the keyword is wrong. That check does not replace a run.

One run has been scored with these graders, on 17 November 2026, with one run per case and without the arm that leaves the plugin out. The themed site passed all 11. The lean audit passed 39 of the 42 it had then, at 4 dollars 31. Two of the three failures were seeded failures, the same two that `grade_findings.py` reported as missed on that run's merged findings, so the two ways of scoring agreed on 22 of 24. The missing skip link was not reported: the audit judged criterion 2.4.1 met, because the page has `main` and `nav` landmarks. The social links were reported under 1.1.1 and 2.4.4 again. The third failure was a grader and not the audit. It wanted at least one of four criteria that need a running site left untested, and the audit gave each of the four a verdict from the code: three failures with a finding, and one pass with the reason that the site has no content on hover. That grader is gone, which leaves the 41 above. Whether the scores are stable over several runs is unmeasured.

## Running the evaluation cases

Four cases live in the `evals/` directory, which is where the evaluation runner looks by default. They need the plugin manifest in `.claude-plugin/plugin.json` to resolve the skill, and they need three tools that are stripped unless you grant them explicitly. Run this from the repository root:

```bash
claude plugin eval . --scaffold --allow-tools Bash Write Edit --no-publish
```

The scaffold option runs each case's `place-files.sh`, which writes the fixture site into a temporary directory. Remember that this is six complete audits by default, as explained under costs above; ask for one run per arm with `--runs 1` to make it two, and use the case option to pick a single case. For the two audit cases `--ablation none` leaves out the arm without the plugin, which their graders cannot score anyway. Results land in `evals/results/`, which is ignored by git.

The 24 graders for the seeded failures put the detection rate into the case score. To score it yourself as well, which also names the misses and the should-pass items, add `--keep-temp`, the option that keeps the temporary directory. Without it the scaffold directory is deleted, and the merged findings file the grader reads goes with it. The run prints the path it kept, which has to be opened first with `chmod 700` on the directory and its `sealed` subdirectory. Then run:

```bash
python3 skills/tiered-a11y-audit/scripts/grade_findings.py <kept>/sealed/home/cwd/site/.a11y-audit/findings/_merged.json evals/full-audit-fixture-site/ground-truth.json
```

The workspace sits in the folder the audit was run on. That is usually `site`; when the audit was started from the folder above it, leave `site` out of the path.

## Repository layout

The next list gives every directory that matters, with what it holds.

- `.claude-plugin/plugin.json` is the plugin manifest. Without it the repository is not a plugin and the evaluation runner has nothing to load.
- `skills/tiered-a11y-audit/SKILL.md` is the workflow itself, and the file Claude Code reads.
- `skills/tiered-a11y-audit/agents/experts/` holds the six lenses, the framework-maximizer, and the protocol they share.
- `skills/tiered-a11y-audit/agents/personas/` holds the eight personas and the protocol they share.
- `skills/tiered-a11y-audit/references/` holds the tiering rules, the finding schema, the criterion ownership table, the framework playbooks, the stack profile template, the report template, the tooling notes, and the report labels per language.
- `skills/tiered-a11y-audit/scripts/` holds the preflight, the detector, the pattern scanner, the colour extractor, the contrast tool, the accessibility-tree digest, the runtime scan, the briefing builder, the phase check, the merge and coverage script, the renderer that writes the draft and assembles the report, the linter that checks it, the exporter, the grader for the evaluation fixture, and eight self-checks that cover most of them.
- `.github/workflows/self-checks.yml` runs the eight self-checks of the scripts, the one of the eval graders and the check of this file on every pull request, on Python 3.9 and on the current version. It calls no model and costs nothing.
- `evals/` holds the four test cases with their fixture sites, and `test_graders.py`, which defines the pattern graders of the two audit cases and checks them. It stays at the repository root, because that is where the evaluation runner looks.

## Contributing

The most useful thing you can contribute is a run on a stack that has no run behind it yet, together with the feedback file the orchestrator writes when you ask it to review the skill afterwards. Corrections to the playbooks are the second most useful: version-gated features and library quirks age fastest. Please keep the three tiers and keep severity independent of them, because that separation is the whole point.

## License

MIT. The full text is in the `LICENSE` file at the root of the repository.
