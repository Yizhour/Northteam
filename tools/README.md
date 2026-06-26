# Internal Tools

This directory contains standalone internal tools that are mounted inside the
NorthTeam2 Django workspace.

## Structure

- `bondreminder/`: Bond interest and redemption reminder tool. Its original
  business logic is reused directly through Django views at `/tools/bond-reminder/`.

## Conventions

- Put each new tool in its own lowercase directory under `tools/`.
- Keep runtime data, uploads, outputs, logs, and secrets out of Git.
- Expose tools through the Django toolbox page so users enter from one place.
