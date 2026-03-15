1. Go to the current section you are working on in `@IMPLEMENTATION_PLAN.md`. Focus only on that section.
1B. Reminder: do NOT commit anything directly. you are only allowed to add and put the commit message here: `.loop-commit-msg`.
2. Implement only the current section. Do not skip ahead. Read the current section, gain context, and read instructions from `@AGENTS.md` on how to build / test.
3. Before editing, inspect the existing code so you do not rebuild something that already exists.
4. Complete all the steps in the current section. Do not skip any.
5. This loop must contain exactly one non-empty line: the final commit subject only which is put in `.loop-commit-msg`.
   Use exactly one of these formats:
   - `{phase}-{plan}-task{task-number}`
   - `{phase}-{plan}-test{test-number}`
   - `{phase}-{plan}-summary`
   Do not include labels, bullets, explanations, markdown, or extra lines in `.loop-commit-msg`.
5. If the current section is a testing section, update the corresponding test-plan result notes before stopping. When the source test markdown is a file such as `01-02-tests.md`, write the actual outcome back into that file too and keep the plan notes aligned. 
6. Before stopping, make sure `Current section to work on` in `@IMPLEMENTATION_PLAN.md` has been moved forward by one if this section completed and that update has not already been made.
9. Do not end the iteration with uncommitted changes.
10. Stop after completing that section and return 20 thumbs up so the user knows we finished.

Keep `@AGENTS.md` operational only.
