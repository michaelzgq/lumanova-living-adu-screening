# Lumanova Living ADU Screening

This project is a lightweight screening app for:

- guided intake
- lead capture
- preliminary Green / Yellow / Orange / Red routing
- local knowledge notes
- bilingual English / Chinese UI
- public-facing landing experience for real project inquiries
- contact preference capture for online leads
- optional WeChat contact capture for Chinese-language leads
- lead inbox filtering, stage tracking, assignment, and internal notes

## What it is for

Use it to test the workflow before putting customers into a production tool like Voiceflow.

## What it is not

- not legal advice
- not a final permit opinion
- not a full design or engineering workflow

## Run it

```bash
cd "/Users/mikezhang/Documents/lumanova living/adu_screening_mvp"
./run_app.command
```

Optional local launch modes:

- public-only local test:
  - [run_public_test.command](/Users/mikezhang/Documents/lumanova%20living/adu_screening_mvp/run_public_test.command)
- local admin review:
  - [run_admin_local.command](/Users/mikezhang/Documents/lumanova%20living/adu_screening_mvp/run_admin_local.command)

## Main tabs

- `Pre-Screen`: customer-style intake flow
- `Lead Inbox`: saved local leads for testing
- `Knowledge Loop`: explains how NotebookLM fits behind the scenes

## Public vs admin links

- customer-facing view:
  - `http://your-host:port/?view=public`
- internal admin view:
  - `http://your-host:port/?view=admin`

For front-door market testing, the public page now supports entry-specific landing variants:

- garage conversion:
  - `http://your-host:port/?view=public&entry=garage`
- detached ADU:
  - `http://your-host:port/?view=public&entry=adu`
- legalization / existing issue:
  - `http://your-host:port/?view=public&entry=legalization`

These variants keep the same intake and admin workflow, but change the front-door copy and preselect the closest project path for faster public testing.

For a more widget-like website embed test, add:

- `&embed=1`

Example:

- `http://your-host:port/?view=public&entry=garage&embed=1`

The public view hides the internal inbox and knowledge loop.

For a hosted test build, set:

- `ADU_FORCE_PUBLIC_ONLY=true`

That forces the app to stay in public mode even if someone manually adds `?view=admin`.

If you want the root public URL to open a specific front-door variant by default, set:

- `ADU_DEFAULT_PUBLIC_ENTRY=garage`
- `ADU_DEFAULT_PUBLIC_ENTRY=adu`
- `ADU_DEFAULT_PUBLIC_ENTRY=legalization`

For a hosted admin view, set:

- `ADU_ADMIN_PASSWORD=...`

If that password is present, admin view requires a login before leads and intake data are visible.

## Optional webhook delivery

This app still saves leads locally, but it can also POST each lead to a webhook.

Supported environment variables:

- `ADU_LEAD_WEBHOOK_URL`
- `ADU_LEAD_WEBHOOK_BEARER_TOKEN`
- `ADU_LEAD_WEBHOOK_HEADERS_JSON`
- `ADU_LEAD_WEBHOOK_TIMEOUT_SECONDS`
- `ADU_FORCE_PUBLIC_ONLY`
- `ADU_ADMIN_PASSWORD`

There is also a starter file here:

- [production_config.example](/Users/mikezhang/Documents/lumanova living/adu_screening_mvp/production_config.example)
- [secrets.example.toml](/Users/mikezhang/Documents/lumanova living/adu_screening_mvp/.streamlit/secrets.example.toml)

Typical use:

- Zapier catch hook
- Make webhook
- Google Apps Script web app
- Airtable automation webhook

The fastest shared inbox setup for this project is Google Sheets via Apps Script:

- [knowledge/google_sheets_setup.md](/Users/mikezhang/Documents/lumanova living/adu_screening_mvp/knowledge/google_sheets_setup.md)
- [integrations/google_sheets_webhook/README.md](/Users/mikezhang/Documents/lumanova living/adu_screening_mvp/integrations/google_sheets_webhook/README.md)
- [integrations/google_sheets_webhook/Code.gs](/Users/mikezhang/Documents/lumanova living/adu_screening_mvp/integrations/google_sheets_webhook/Code.gs)
- [run_prepare_google_sheets.command](/Users/mikezhang/Documents/lumanova living/adu_screening_mvp/run_prepare_google_sheets.command)

When a webhook is configured:

- new public lead submissions send `event_type=lead.created`
- admin lead updates send `event_type=lead.updated`
- sync status is visible in the admin inbox

## Recommended first deployment

The best first release path for this project is `Streamlit Community Cloud`.

Why:

- this app is already a Streamlit app
- `requirements.txt` is already in place
- Cloud secrets are simple for webhook configuration
- you can test a public screening link without maintaining a server first

Suggested first hosted setup:

1. Push this folder to GitHub.
2. Create a new Streamlit Community Cloud app from `app.py`.
3. Add secrets from:
   - [secrets.example.toml](/Users/mikezhang/Documents/lumanova living/adu_screening_mvp/.streamlit/secrets.example.toml)
4. Start with:
   - `ADU_FORCE_PUBLIC_ONLY = "true"`
5. When you are ready to use hosted admin access, also set:
   - `ADU_ADMIN_PASSWORD = "your-real-password"`
6. Use the hosted URL as your customer-facing test link.

For the first public test, keep admin review local and only expose the public screening flow online.

## Public landing flow

The public view is now structured as a simple landing page:

- what the screen is for
- what it can and cannot tell the customer
- who it is best for
- the intake itself

This keeps the front door focused on lead qualification instead of generic remodeling questions.

## New for online lead testing

- customers can submit a preferred follow-up method
- customers can submit their best contact time
- consent to contact is required before saving a lead
- public links can use `entry` variants for market testing
- query params can carry source tracking:
  - `source`
  - `utm_source`
  - `utm_medium`
  - `utm_campaign`
- the inbox now supports:
  - search
  - stage filtering
  - path filtering
  - source filtering
  - assignee field
  - disposition reason
  - next action
  - internal notes
  - lead-stage updates
  - quick action buttons for common follow-up moves

## NotebookLM role

NotebookLM is your internal research layer:

1. load official files there
2. summarize rules and updates
3. rewrite those into clean playbook rules
4. feed the cleaned rules into the front-end chatbot

Related docs:

- [business_closure_loop.md](/Users/mikezhang/Documents/lumanova living/adu_screening_mvp/knowledge/business_closure_loop.md)
- [notebooklm_workflow.md](/Users/mikezhang/Documents/lumanova living/adu_screening_mvp/knowledge/notebooklm_workflow.md)
- [google_sheets_setup.md](/Users/mikezhang/Documents/lumanova living/adu_screening_mvp/knowledge/google_sheets_setup.md)
- [launch_readiness.md](/Users/mikezhang/Documents/lumanova living/adu_screening_mvp/knowledge/launch_readiness.md)
- [first_wave_launch_plan.md](/Users/mikezhang/Documents/lumanova living/adu_screening_mvp/knowledge/first_wave_launch_plan.md)
- [channel_copy_pack.md](/Users/mikezhang/Documents/lumanova living/adu_screening_mvp/knowledge/channel_copy_pack.md)
- [page_asset_plan.md](/Users/mikezhang/Documents/lumanova living/adu_screening_mvp/knowledge/page_asset_plan.md)
- [okara_url_solution.md](/Users/mikezhang/Documents/lumanova living/adu_screening_mvp/knowledge/okara_url_solution.md)
- [streamlit_cloud_deploy.md](/Users/mikezhang/Documents/lumanova living/adu_screening_mvp/knowledge/streamlit_cloud_deploy.md)
- [github_publish_steps.md](/Users/mikezhang/Documents/lumanova living/adu_screening_mvp/knowledge/github_publish_steps.md)

## Tests

```bash
cd "/Users/mikezhang/Documents/lumanova living/adu_screening_mvp"
python3 -m unittest discover -s tests
```
