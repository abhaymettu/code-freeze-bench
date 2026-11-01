# Submitting the paper

The PDF is `paper/main.pdf`, built from `paper/main.tex` with `make paper` (tectonic). Nothing has been submitted
anywhere. These steps need Abhay's own accounts.

## arXiv

1. Rebuild: `make scoreboard && make paper`, and check the PDF opens and the tables match `results/SCOREBOARD.md`.
2. Make the source bundle: `cd paper && tar czf ../arxiv.tar.gz main.tex results.tex refs.bib main.bbl`
   (tectonic writes `main.bbl` when run with `-k`; arXiv needs the `.bbl` because it does not run BibTeX for you
   reliably).
3. Log in at https://arxiv.org/user, choose "Start new submission".
4. License: CC BY 4.0. Primary category: cs.SE (Software Engineering); cross-list cs.AI and cs.CR.
5. First-time submitters to cs.SE or cs.AI may need an endorsement. arXiv shows the endorsement page during submission
   if one is required; send the generated endorsement code to someone who has published in the category.
6. Upload `arxiv.tar.gz`, check the rendered PDF in arXiv's preview, then fill in title, authors and the abstract
   (copy from `main.tex`, removing LaTeX macros).
7. Comments field: "Code and all raw runs: https://github.com/abhaymettu/code-freeze-bench".

## Optional

- Zenodo: connect the GitHub repo at https://zenodo.org/account/settings/github/ and cut a release to get a DOI for the
  code and raw runs.
- Workshops that take short empirical agent-safety papers: check the current calls before submitting.
