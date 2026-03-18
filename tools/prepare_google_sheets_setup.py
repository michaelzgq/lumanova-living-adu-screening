from __future__ import annotations

import secrets
from pathlib import Path
from urllib.parse import quote


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    template_path = project_root / "integrations" / "google_sheets_webhook" / "Code.gs"
    output_dir = project_root / "output" / "google_sheets_setup"
    output_dir.mkdir(parents=True, exist_ok=True)

    shared_token = secrets.token_urlsafe(24)
    template = template_path.read_text(encoding="utf-8")
    customized_code = template.replace("const SHARED_TOKEN = 'replace-me';", f"const SHARED_TOKEN = '{shared_token}';")

    (output_dir / "Code.gs").write_text(customized_code, encoding="utf-8")
    (output_dir / "google_sheets_token.txt").write_text(shared_token, encoding="utf-8")
    webhook_url_template = f"https://script.google.com/macros/s/DEPLOYMENT_ID/exec?token={quote(shared_token)}"
    healthcheck_url_template = f"https://script.google.com/macros/s/DEPLOYMENT_ID/exec?token={quote(shared_token)}"
    (output_dir / "streamlit_secrets_snippet.toml").write_text(
        "\n".join(
            [
                "# Paste these into Streamlit Cloud secrets after you deploy Apps Script.",
                f'ADU_LEAD_WEBHOOK_URL = "{webhook_url_template}"',
                'ADU_LEAD_WEBHOOK_BEARER_TOKEN = ""',
                'ADU_LEAD_WEBHOOK_HEADERS_JSON = ""',
                'ADU_LEAD_WEBHOOK_TIMEOUT_SECONDS = "8"',
                'ADU_FORCE_PUBLIC_ONLY = "true"',
                'ADU_ADMIN_PASSWORD = ""',
                "",
            ]
        ),
        encoding="utf-8",
    )
    (output_dir / "NEXT_STEPS.md").write_text(
        "\n".join(
            [
                "# Next Steps",
                "",
                "1. Open your Google Sheet.",
                "2. Go to Extensions -> Apps Script.",
                "3. Replace the default file with the generated `Code.gs` in this folder.",
                "4. Deploy the script as a Web app:",
                "   - Execute as: Me",
                "   - Who has access: Anyone with the link",
                "5. Copy the deployed Web app URL.",
                "6. Replace `DEPLOYMENT_ID` in `streamlit_secrets_snippet.toml` with the real Apps Script deployment ID or full URL path segment.",
                f"7. Health-check the deployment in a browser with: `{healthcheck_url_template}` (replace DEPLOYMENT_ID first).",
                "8. Paste the resulting values into Streamlit Cloud secrets and redeploy the app.",
                "",
                f"Shared token generated for this setup: `{shared_token}`",
                "",
            ]
        ),
        encoding="utf-8",
    )

    print(f"Prepared Google Sheets setup files in: {output_dir}")
    print(f"Shared token: {shared_token}")


if __name__ == "__main__":
    main()
