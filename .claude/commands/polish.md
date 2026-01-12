---
allowed-tools: Bash(./scripts/test.sh:*), Bash(uv:*), Bash(radon:*), Bash(pmd:*)
description: Runs the /test command and implements all recommendations in a loop for up to 4 cycles.
---

## Purpose

Run the comprehensive test validation pipeline and produce an actionable report for code quality improvements and then implement all of the improvements and then rinse and repeat for up to 4 cycles.

## Execution

1. Run the /test command (.claude/commands/test.md).
2. If there is nothing to action including non-blocking recommendations then halt and do nothing more.
3. Implement all recommendations including non-blocking.
4. Repeat from step 1. until this has been run 4 times or there is nothing more to do.

## Important Notes

- **DO NOT STOP**: Do not ask for user approval or stop because there is a lot to do etc. Just keep going.

