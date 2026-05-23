# Voice exemplars

This folder holds 1-2 examples of YOUR existing writing. The drafting stage
of the pipeline pastes these directly into the prompt as "write in this voice"
exemplars. Without them, drafts will read like every other AI health blog.

## What to drop here

Any of:

- A Substack post or essay you've written
- A long Twitter/X thread that captures how you think and write
- A blog post from anywhere
- Plaintext notes from a journal or doc
- Even a transcribed voice memo if it captures your spoken cadence

## Format

- Plain `.md` or `.txt` files, one per exemplar.
- Filename doesn't matter as long as it's not this README.
- 500-3,000 words each is the sweet spot. Less than 500 and the model
  doesn't have enough signal; more than 3,000 and the prompt token cost
  goes up without much marginal gain.

## How many

- Minimum: 1. The pipeline preflight will fail if this folder is empty.
- Recommended: 2. One technical/analytical piece and one more conversational
  piece, so the model learns your range.
- Maximum useful: 3-4. Beyond that, the prompt gets too long for not much extra benefit.

## What NOT to put here

- Other people's writing (the model will copy their voice, not yours).
- Ghost-written or heavily AI-edited content.
- Pieces you're not proud of stylistically - the pipeline will faithfully
  reproduce whatever tics, hedges, and patterns appear in the exemplars.

## Privacy

This folder is gitignored. Files stay on your machine only.
