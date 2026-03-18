# Google Sheets Receiver

This folder contains a Google Apps Script receiver for the ADU screening app.

## Files

- `Code.gs`: webhook receiver that accepts POST requests from the app and upserts normalized rows into a sheet by `lead_id`

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

## Health check

Open the same tokenized URL in a browser.

- Expected: a JSON response with `"ok": true`
- Not expected: a Google sign-in page or a Drive error page

## App configuration example

```bash
export ADU_LEAD_WEBHOOK_URL="https://script.google.com/macros/s/DEPLOYMENT_ID/exec?token=replace-me"
export ADU_LEAD_WEBHOOK_BEARER_TOKEN=""
export ADU_LEAD_WEBHOOK_HEADERS_JSON=""
```

## Notes

- This receiver is optimized for first production testing.
- It supports `lead.created`, `lead.updated`, and `lead.deleted`.
- It also stores `wechat_id` and `disposition_reason` when present.
- The receiver stores the raw payload JSON in the row so you can inspect the full lead later.
- The `Leads` tab is updated by `lead_id`, so updates and deletes do not create duplicate rows by default.
