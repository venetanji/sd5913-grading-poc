# SD5913 grading POC

A local-first prototype for preparing small, auditable evidence packets from SD5913 Assignment 1 and 2 repositories. It never assigns final grades, publishes data, or modifies student repositories. By default it makes no model calls; optional Laya scoring runs locally and every score must be reviewed by a human.

## Why this workflow

A whole submission set is a poor prompt. This tool handles one repo at a time using a shallow, partial Git clone. It lists the tree without checking out all blobs, then fetches a bounded selection of text: README/PROCESS first, followed by code/config. It records paths for data and output assets without fetching those blobs. Each packet is capped at 18 files, 10,000 characters per file and 38,000 characters total. This keeps source evidence inspectable and reduces context, cost and accidental transfer. It does not yet inspect images or execute student code; Assignment 2's picture therefore always needs human inspection.

Student repository URLs are private working data. The provided `inputs/assignment-1.txt` (104 URLs) and `inputs/assignment-2.txt` (101 URLs) were generated from the attached Canvas export zips and are git-ignored. A few links pointed to a file/tree/commit inside a repo; those were normalized to the repository root. `runs/`, which may contain student work, is also git-ignored. Do not commit either or send them to a provider without the teaching team's explicit approval.

## Requirements and local run

Install [uv](https://docs.astral.sh/uv/) and Git. From this directory:

```bash
uv run --project . sd5913-grade-poc inputs/assignment-1.txt --assignment 1 --limit 3
uv run --project . sd5913-grade-poc inputs/assignment-2.txt --assignment 2 --limit 3
```

Omit `--limit 3` to prepare all repositories. Outputs appear in `runs/latest/`:

- `evidence.jsonl` — bounded evidence, deterministic preflight checks and pseudonymous IDs.
- `judge-packets.jsonl` — same evidence plus source-grounded rubric and a strict JSON response contract; ready for a chosen judge, but no call is made.
- `failures.json` — failures keyed by pseudonymous submission ID.

After publishing this repository, run it from Git while keeping the URL list local:

```bash
uvx --from 'git+https://github.com/venetanji/sd5913-grading-poc.git' sd5913-grade-poc INPUT.txt --assignment 1
```

Use a private remote and keep local input/output files out of commits. Public student repositories are not permission to transmit their contents to an external model service.

## Rubrics and evidence

`grading_poc/rubrics.json` transcribes the weighted criteria in the current assignment briefs: `pfad/assignments/01-why-are-we-here.md` and `pfad/assignments/02-data-visualisation.md`. Current teaching slides reinforce those briefs. The teaching repo's `syllabus/` currently contains no syllabus document, so this prototype does not invent syllabus criteria. Source links are cited in the rubric data.

The generic judge-packet contract requests integer criterion scores from 0-4, short path-cited evidence, reasons, missing evidence and review flags. Laya instead returns continuous 0-4 estimates and no rationale. Scores are provisional and are not automatically converted into final course marks. Assignment 2's informative and artistic paths are treated equally; model evaluation of picture quality is explicitly not implemented.

## Jev, Laya and model evaluation

Optional local inference uses the PyPI `laya==0.3.28` package and CPU-only PyTorch; the `laya-local` extra pins its install and `uv.lock` routes PyTorch to the CPU wheel index so it does not pull NVIDIA CUDA wheels on Linux. First inference downloads Laya weights from Hugging Face. Run a small pilot explicitly:

```bash
uvx --from 'sd5913-grading-poc[laya-local] @ git+https://github.com/venetanji/sd5913-grading-poc.git' sd5913-grade-poc INPUT.txt --assignment 1 --limit 1 --judge laya-local
```

Laya's scores are continuous 0-4 estimates. It does not generate explanations or evidence citations, so every result is flagged for human review. The judge packs criterion-specific excerpts to reduce context loss; a truncated input is recorded as a review warning. For Assignment 2, Picture is deliberately left unscored for a person to inspect because this prototype does not render images. Local inference sends submission text to the local model process, not the Laya hosted API. The downloaded model weights come from Hugging Face.

Hosted Jev is not wired into this public POC. The one-submission Laya smoke test was local; it showed why bounded contexts matter: the initial all-in-one packet was truncated, so the implementation now judges one criterion at a time and exposes truncation flags. Hosted model comparison needs an explicit provider choice, an approved privacy path and its own adapter; do not silently switch providers.

For a fair POC comparison, retain the same evidence packets and rubric for each chosen judge; have two humans independently grade the same small sample first; compare criterion-level agreement and evidence citations, not just total scores; and record disagreements for adjudication. Do not send identifying URLs/names or large repository dumps. The stable IDs are plain hashes of URLs and are **not anonymous** (they can be guessed/reidentified); keep packets and any grade mapping access-controlled.

## Known limitations

- Git/network access is required to fetch public repos. Private repos fail unless the runner has authorized access; this prototype does not manage credentials.
- Partial clone support depends on the Git host. Failed submissions are reported without printing repository URLs.
- The tree is recorded but source selection is heuristic; max-file and character caps can omit relevant evidence.
- No rendering, execution, dependency installation, image inspection, citation verification or plagiarism/authorship assessment is performed.
- Preflight checks are approximate and must not be treated as the course's official checker.
- This code repository is public; keep URL lists, packets, scores and any grade mapping local and private.
