Thank you for your interest in contributing!

Contributing guidelines:

1. Fork the repository and create feature branches off `main`.
2. Run tests locally before opening a PR:

```bash
"d:/Hackathon Bot/venv/Scripts/python.exe" -m pytest -q
```

3. Follow code style: `black` formatting and `ruff` linting. Run pre-commit hooks locally:

```bash
pre-commit run --all-files
```

4. Write tests for new features and ensure CI passes.

5. Keep changes small and focused; add a changelog entry for public-facing changes.
