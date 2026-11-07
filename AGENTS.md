# Working on Ruin Everything

- Use English throughout the project, including documentation, CLI messages, examples, code comments, figure labels, prompts, commit messages and repository metadata.
- Update README.md with every project update. Describe the observable change and its verification status. Commit the README and its figures with the implementation, push them to GitHub, and check that the published branch contains the update.
- Pair every explanation with an original, labeled figure. A multi-panel figure may cover several explanations if the text points to the relevant panel. Provide descriptive alt text. Preserve editable vector sources in docs/figures.
- Before drawing, write down the reader's question, actual components, sequence, and boundaries. Sketch the overview first, then the detail that answers the question. Use a white field, muted blue-gray structure, fine outlines, and a single accent for the active path. Use cutaways or exploded layers only when they clarify a relationship.
- Use the figure brief below when drawing. Replace bracketed fields with concrete project facts. Review at README width, check every arrow against the implementation, and revise the figure and text together.

## Reusable figure brief

Draw an editable scientific schematic answering “[reader question]” for [audience]. In the overview, arrange [named components] in execution order. In the detail panel, show [decision, boundary, or exception] at the point where it occurs. Label each connection with the data or action it carries. Use parallel projection for layered structures, consistent line weights, short English labels and enough whitespace to read at phone width. Apply slate to structure and muted teal to the active path. Use a warm neutral for human action. Compare the draft with [implementation or test], then remove any unsupported step.

![Figure development proceeds from a question to a labeled drawing and a checked result.](docs/figures/editorial.svg)
