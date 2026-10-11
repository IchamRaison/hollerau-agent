"""The DSH pilot: a language model negotiates the case through DeepSeek Harness.

The model reads, decides what to propose and writes the e-mails; this package computes costs,
keeps the factual state of the case, validates what the model wants to send and is the only
thing that talks to the arena. See `configs/dsh/tacto.patch.yml` for the harness profile and
`prompts/tacto_negotiator.md` for what the model is told.
"""
