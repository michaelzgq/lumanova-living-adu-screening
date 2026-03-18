# Streamlit Community Cloud Deploy

## 1. Push Code To GitHub

Put the full `adu_screening_mvp` folder in a GitHub repository that you control.

## 2. Create The App

In Streamlit Community Cloud:

1. Connect GitHub.
2. Choose the repository.
3. Set the main file to:

```text
app.py
```

## 3. Add Secrets

Use the secrets panel and paste values based on `.streamlit/secrets.example.toml`.

Minimum example:

```toml
ADU_FORCE_PUBLIC_ONLY = "true"
ADU_ADMIN_PASSWORD = "replace-me"
ADU_LEAD_WEBHOOK_URL = "https://your-webhook-url"
ADU_LEAD_WEBHOOK_BEARER_TOKEN = "optional-token"
```

## 4. First Safe Launch Mode

For the first test:

- keep public access on
- keep hosted admin hidden unless you really need it
- review live leads through your webhook target

Recommended:

```toml
ADU_FORCE_PUBLIC_ONLY = "true"
```

## 5. After Deploy

Open the hosted link with:

- `?view=public`
- `?view=public&entry=garage`
- `?view=public&entry=adu`
- `?view=public&entry=legalization`

## 6. When To Enable Hosted Admin

Only enable hosted admin after:

- webhook delivery is working
- you have a real admin password set
- you are comfortable reviewing leads online

Then set:

```toml
ADU_FORCE_PUBLIC_ONLY = "false"
ADU_ADMIN_PASSWORD = "your-real-password"
```
