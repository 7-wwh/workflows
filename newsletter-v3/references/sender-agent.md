# Sender Agent (v4 — Retrieval & Delivery Only)

The Sender delivers finished editions. It is triggered by cron at EACH
`<profile>/settings.md -> slot_time` via `run-sender.sh --profile <id>`, which
cd's into `profiles/<id>/` and INJECTS the recipient address (read from that
profile's `settings.md`) into the prompt. It performs **zero production work**:
everything it sends was written, evaluated, and exported by the Intermediate Agent
into `profiles/<id>/outbox/<date>/slot-<HHMM>-final.html` during that profile's
nightly batch. This is what removes writing delay from send time.

## Hard boundaries

- **Profile isolation (v5)**: the sender operates exclusively within its own
  profile directory. It NEVER reads another profile's outbox, settings, or vault,
  and it NEVER sends to any address other than the injected recipient. If no
  recipient is set, the runner hard-fails before the agent launches.
- NEVER writes research, HTML drafts, or evals — if the outbox file is missing, it
  skips and logs (never fills the gap itself).
- NEVER touches planned topics/slots beyond flipping the delivered slot status
  (`READY -> DELIVERED`).
- NEVER sends without checking the eval pass status.

## Pre-send checklist (per firing slot_time)

1. **STATE CHECK** (role = send): read settings.md, state.json, content_plan.md.
   Identify the slot matching this firing `slot_time`.
2. Status gate:
   - `READY` -> continue.
   - `SCHEDULED` -> the batch has not finished/failed for this slot -> log
     "not ready", do NOT block, surface at next user interaction.
   - `DELIVERED` / `EMPTY` -> log, stop.
3. Retrieve `outbox/<date>/slot-<HHMM>-final.html`. Missing -> log + skip.
4. Verify the matching `eval/<date>-slot-<HHMM>-eval.json`: `pass: true`, or the
   recorded warning-banner failure (batch report `eval_pass: false`) -> skip + log
   with reason.

## Delivery

- **Mode A — one email per slot** (recommended): subject
  `[Newsletter] <headline>`, body = the outbox HTML.
- **Mode B — single bundled email**: concatenate the day editions with `<hr>`.
- **Email transport**: when `settings.md -> email` is non-null, the Sender uses
  the Hermes `google-workspace` skill (`google_api.py`) to send via the Gmail API.
  The OAuth token at `~/.hermes/google_token.json` is persistent and auto-refreshes.
  No email tool connected / `settings.md -> email: null` -> present the file to the
  user and suggest connecting Gmail/Outlook.

## After sending

1. Re-stamp the delivered file `<!-- newsletter-expiry: ... -->` marker to
   `now + html_expiry_days` and run `newsletter-workspace/cron/purge-expired.sh`.
2. Flip the slot to `DELIVERED` in `content_plan.md`.
3. Append the delivery record to `vault/editions.json` (schema in `references/schemas.md`)
   including `"profile"` and `"sent_to"` for the audit trail.
4. Vault: topic status -> `delivered`; update `vault/state.json` (last_edition_id,
   total_editions_delivered, next_due).
5. Close the run manifest (trigger `send`, with `"profile": "<id>"`).

## Confirm to the user (next interaction)

- How many editions were sent / skipped (and why: not ready, eval failed, missing file).
- Which email address they went to, or that they were presented as files.
