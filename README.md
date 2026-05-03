# github-stats

Custom GitHub stats for [@zxzinn](https://github.com/zxzinn), counting only commits authored by me, including private repos.

## How it works

1. `collect.py` lists owned + contributed-to repos via GraphQL, then walks each repo's commits filtered by author, fetching per-commit `additions`/`deletions` per file from `repos/{repo}/commits/{sha}`. It maps file extensions to languages and aggregates per-language totals.
2. `recompute.py` strips Jupyter Notebook (notebook diffs are dominated by base64 cell outputs).
3. `render.py` writes `overview.svg` + `languages.svg`.
4. The workflow runs daily on cron, pushing artifacts to the `generated` branch.

## Why not the standard tools

The official `/repos/{repo}/stats/contributors` endpoint has been returning empty results (`{}` with HTTP 200) for many repos for months. Walking commits is slower but reliable.

## Output

- `https://raw.githubusercontent.com/zxzinn/github-stats/generated/overview.svg`
- `https://raw.githubusercontent.com/zxzinn/github-stats/generated/languages.svg`
- `result_clean.json` and `result_v2.json` for raw data
