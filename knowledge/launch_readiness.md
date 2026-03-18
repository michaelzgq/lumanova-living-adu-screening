# Launch Readiness

## Goal

Put the first public version online, capture real leads, and review them in a controlled workflow.

## Recommended Deployment Path

Use Streamlit Community Cloud for the first public test.

Why:

- the app already runs on Streamlit
- `requirements.txt` is already in place
- secrets can be pasted directly into Community Cloud settings
- the public/admin split already exists

## Before Deployment

1. Push this folder to a GitHub repository.
2. Confirm these files are present:
   - `app.py`
   - `requirements.txt`
   - `.streamlit/secrets.example.toml`
   - `production_config.example`
3. Decide which webhook target will receive live leads:
   - Google Sheets via Apps Script
   - Zapier
   - Make
   - Airtable webhook

## Recommended Secrets

Paste these into Community Cloud secrets and replace the placeholders:

```toml
ADU_FORCE_PUBLIC_ONLY = "true"
ADU_ADMIN_PASSWORD = "change-this-before-admin-goes-online"
ADU_LEAD_WEBHOOK_URL = "https://your-webhook-url"
ADU_LEAD_WEBHOOK_BEARER_TOKEN = "optional-token"
```

For the first public test, keep `ADU_FORCE_PUBLIC_ONLY = "true"` if you do not want hosted admin access.

## First Public Rollout

Start with only three front-door links:

- garage conversion
- detached ADU
- legalization / existing issue

Use source tags so each channel can be measured separately.

Examples:

- `?view=public&entry=garage&source=wechat_sgv&utm_source=wechat&utm_medium=social&utm_campaign=garage_test`
- `?view=public&entry=adu&source=agent_referral&utm_source=agent&utm_medium=referral&utm_campaign=adu_test`
- `?view=public&entry=legalization&source=wechat_legalize&utm_source=wechat&utm_medium=social&utm_campaign=legalization_test`

## First 7-Day KPIs

Track only these:

1. total public starts
2. completed submissions
3. contact submission rate
4. path mix: A / C / B
5. source quality by channel
6. follow-up speed
7. paid screening conversations started

## Minimum Daily Operating Rhythm

1. Check `Priority review queue`.
2. Contact all `new` and `needs_review` leads within 24 hours.
3. Update:
   - `stage`
   - `assigned_to`
   - `disposition_reason`
   - `next_action`
4. Review source tags once per day.

## Stop Conditions

Pause and adjust before sending more traffic if:

- many leads are missing contact details
- most leads are obvious bad fit
- one channel drives volume but no usable leads
- public copy is causing repeated confusion about what the tool does

## What Not To Change During The First Test

Do not change:

- routing logic
- required intake fields
- stage definitions
- webhook target

unless something is clearly broken.

The goal of the first test is to learn from real usage, not to keep redesigning the product every day.
