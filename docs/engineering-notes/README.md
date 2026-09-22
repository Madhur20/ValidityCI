# Engineering notes

This directory is the working memory for ValidityCI. It records why the system looks the way it does, what went wrong while building it, which claims have actually been tested, and which ideas are still hypotheses.

The labels matter:

- **Observed** means the problem occurred during implementation or a live test.
- **Design decision** means a tradeoff was made deliberately, even if nothing had failed yet.
- **Assumption** means the project currently depends on a belief that still needs evidence.
- **Anticipated** means the issue has not occurred in this repository but is credible enough to design or test for.

Keeping those categories separate makes these notes useful in interviews without turning possible failure modes into invented personal history.

## Contents

- [Hurdles and lessons](hurdles-and-lessons.md) contains implementation problems, root causes, fixes, and verification.
- [Decision log](decision-log.md) explains the architecture and product choices that shaped the project.
- [Assumption register](assumption-register.md) lists what must be true for ValidityCI to become useful and commercially viable.
- [Ideas and failure modes](ideas-and-failure-modes.md) is the technical and product backlog behind the formal roadmap.
- [Project talking points](project-talking-points.md) turns the work into an honest demo and interview narrative.

## Maintenance rule

After each backlog item, update at least one of these files. Record the symptom before the solution, distinguish a local development problem from a product problem, and include the test or observation that supports any claim of completion.
