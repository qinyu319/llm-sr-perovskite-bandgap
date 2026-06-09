# Publication Security Check

Audit date: 2026-06-10

The release scan covers tracked text, JSON, JSONL, Python, PowerShell, YAML,
CSV, and Markdown files. It checks for token-like secrets, authorization
headers, hard-coded private Windows paths, manuscript-system links, non-ASCII
path names, and spaces in tracked path names.

Results:

- no embedded API key, bearer token, GitHub token, or password was found;
- provider manifests retain only environment-variable names such as
  `DASHSCOPE_API_KEY` and `DEEPSEEK_API_KEY`;
- archived request payloads contain prompts and model parameters but no HTTP
  authorization headers;
- machine-specific paths were replaced with repository-relative paths;
- stderr logs, smoke runs, caches, temporary work directories, and duplicate
  train/test workbooks were removed;
- tracked path names are ASCII and contain no spaces.

Repeat the automated check before every release:

```bash
python scripts/security_scan.py
python scripts/verify_checksums.py
```

Never commit `.env` files or paste credentials into issues.
