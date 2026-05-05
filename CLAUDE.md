# Build and testing requirements
- All build steps must happen inside docker container
- All testing should happen inside docker container
- Docker compose should be used for building and testing
- Do not plan any migrations from previous versions, assume new deployment
- Write tests for relevant operations

# Workflow
- After each major step of TODO.md it should be updated to match current state
- If we need to stray from TODO.md you must ask user for opinion
- After each major step update NEXT.md to reflect current state and next operation to continue in a new session
- Git commit of current progress should be done after TODO.md and NEXT.md update
