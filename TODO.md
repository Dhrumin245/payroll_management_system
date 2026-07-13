- [ ] Verify dependency list includes missing package causing CI failure (itsdangerous)
- [ ] Update requirements.txt (and lock if applicable) to add itsdangerous
- [ ] Re-run pytest with coverage locally to confirm ImportError is resolved
- [ ] If needed, adjust Starlette SessionMiddleware usage (ensure cookie/session deps are installed)

