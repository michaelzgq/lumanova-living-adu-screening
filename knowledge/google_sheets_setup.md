# Google Sheets Webhook Setup

This project already supports generic webhook delivery. The fastest production-safe shared inbox is:

- public Streamlit app
- Google Apps Script webhook
- Google Sheet as the first shared lead log

## Recommended use

Use Google Sheets when you want:

- one shared place to review leads
- a lightweight handoff before moving into a full CRM
- simple operations for `stage`, `assignee`, `contacted`, and source tracking

## What gets sent

Every successful submission or update can POST:

- `event_type`
- `sent_at`
- `lead.id`
- contact data
- WeChat ID when provided
- address and project intent
- route and risk result
- stage / disposition / assignee / next action / notes
- source / utm fields

## Fastest setup path

1. Create a new Google Sheet for lead intake.
2. Open `Extensions -> Apps Script`.
3. Paste the script from:
   - `integrations/google_sheets_webhook/Code.gs`
4. Set a shared secret inside the script.
5. Deploy as:
   - `Web app`
   - Execute as: `Me`
   - Who has access: `Anyone with the link`
6. Copy the deployment URL.
7. Add the secret in the query string:
   - `https://script.google.com/macros/s/.../exec?token=YOUR_SECRET`
8. Put that URL into:
   - `ADU_LEAD_WEBHOOK_URL`

## Why the token is in the URL

Google Apps Script web apps do not reliably expose incoming custom headers in the simple `doPost(e)` flow.

Because of that, the safest simple setup for this screening app is:

- keep the secret in the webhook URL query string
- do not rely on bearer headers for the Google Sheets receiver

## Suggested operating pattern

Use one tab named `Leads`.

The provided Apps Script now updates rows by `lead_id` instead of always appending.

That means:

- `lead.created` creates the row
- `lead.updated` overwrites the same row
- `lead.deleted` marks the row with `deleted_at`

If you want a separate audit trail later, add a second `Events` tab in a future version.

## Fastest local prep

To generate a ready-to-paste token, a customized `Code.gs`, and a Streamlit secrets snippet:

```bash
cd "/Users/mikezhang/Documents/lumanova living/adu_screening_mvp"
./run_prepare_google_sheets.command
```

This creates:

- `output/google_sheets_setup/Code.gs`
- `output/google_sheets_setup/google_sheets_token.txt`
- `output/google_sheets_setup/streamlit_secrets_snippet.toml`
- `output/google_sheets_setup/NEXT_STEPS.md`

## Operating model

- Public app captures the lead.
- Webhook writes the payload into Google Sheets.
- Team reviews the sheet and the app inbox.
- Qualified leads move into call-back, paid screening, and proposal flow.

## Important boundary

Google Sheets is the shared operations log, not the rules engine.

Routing logic should still live in:

- the Streamlit app
- your playbook
- your NotebookLM-backed internal research workflow

## Recommended next step after Sheets

After 20 to 50 real leads, decide whether to move from Google Sheets into:

- Airtable
- HubSpot
- Pipedrive
- or a custom internal ops database
