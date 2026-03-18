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

## Suggested sheet columns

Keep one tab named `Leads` with columns such as:

- `received_at`
- `event_type`
- `lead_id`
- `full_name`
- `email`
- `phone`
- `wechat_id`
- `contact_preference`
- `best_contact_time`
- `property_address`
- `brief_goal`
- `jurisdiction`
- `recommended_path`
- `risk_tier`
- `recommended_service`
- `stage`
- `disposition_reason`
- `assigned_to`
- `next_action`
- `source_tag`
- `utm_source`
- `utm_medium`
- `utm_campaign`
- `external_sync_status`
- `notes_json`

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
