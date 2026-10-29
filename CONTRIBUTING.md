# Contributing

Thanks for helping! Deutsch oder Englisch – both are fine in issues and pull requests.

## Reporting problems

Please include:

- Card model and `lspci -nnk | grep -A3 -i creative`
- Distribution, kernel (`uname -r`), PipeWire version (`pipewire --version`)
- A diagnostic log: `ae5-diag start`, reproduce the problem, `ae5-diag mark "what happened"`, then attach `~/.local/state/ae5-control/diag/current.log`

## Other CA0132 cards

Support for Sound Blaster Z, ZxR, AE-7 or Recon3D is welcome. These cards use other driver models
(`sbz`, `zxr`, `ae7`, `r3d`, …), different PCI/codec IDs and partly different controls. A good start:
`amixer -c <card> contents` and `/proc/asound/card*/codec#*` of your card.

## Code

- Python: `ae5control/` (PySide6 app, CLI). Shell: `tools/`.
- User-visible text is bilingual: Python uses `tr("Deutsch", "English")` from `ae5control/i18n.py`,
  shell scripts use `t "Deutsch" "English"`.
- Run the tests before a pull request: `python3 -m unittest discover -s tests -t .`
- Check shell scripts with `bash -n` (and `shellcheck` if available).
- Be careful with anything that changes volume or gain – never raise it without asking the user.
