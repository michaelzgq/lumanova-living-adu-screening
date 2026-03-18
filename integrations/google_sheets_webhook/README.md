# Google Sheets Receiver

This folder contains a minimal Google Apps Script receiver for the ADU screening app.

## Files

- `Code.gs`: webhook receiver that accepts POST requests from the app and appends normalized rows into a sheet

## Deploy steps

1. Create a Google Sheet.
2. Open `Extensions -> Apps Script`.
3. Replace the default script with the contents of `Code.gs`.
4. In the script:
   - set `SHEET_NAME`
   - set `SHARED_TOKEN`
5. Deploy as a `Web app`.
6. Copy the deployment URL and append:
   - `?token=YOUR_SHARED_TOKEN`
7. Put that full URL into:
   - `ADU_LEAD_WEBHOOK_URL`

## App configuration example

```bash
export ADU_LEAD_WEBHOOK_URL="https://script.google.com/macros/s/DEPLOYMENT_ID/exec?token=replace-me"
export ADU_LEAD_WEBHOOK_BEARER_TOKEN=""
export ADU_LEAD_WEBHOOK_HEADERS_JSON=""
```

## Notes

- This receiver is intentionally simple and optimized for first production testing.
- It supports `lead.created`, `lead.updated`, and `lead.deleted`.
- It also stores `wechat_id` and `disposition_reason` when present.
- The receiver stores the raw payload JSON in the row so you can inspect the full lead later.
