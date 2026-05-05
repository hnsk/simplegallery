# Build and testing requirements
- All build steps must happen inside docker container
- All testing should happen inside docker container
- Docker compose should be used for building and testing
- No Python interpreter, pip, or project tooling runs on host. All execution (build, test, smoke checks, ad-hoc `python -c`, REPL, lint, format) goes through docker compose
- If no compose service fits an ad-hoc check, add one (e.g. a `shell` service with `command: python ...`) rather than running on host
- Do not plan any migrations from previous versions, assume new deployment
- Write tests for relevant operations

# Workflow
- After each major step of docs/TODO.md it should be updated to match current state
- If we need to stray from docs/TODO.md you must ask user for opinion
- After each major step update docs/NEXT.md to reflect current state and next operation to continue in a new session
- Git commit of current progress should be done after docs/TODO.md and docs/NEXT.md update
