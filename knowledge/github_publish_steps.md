# GitHub Publish Steps

Use this when you are ready to push the local repository to GitHub and connect it to Streamlit Community Cloud.

## Current local repository state

- branch: `main`
- latest commit: `17db16e Initial launch-ready screening app`
- project path: `/Users/mikezhang/Documents/lumanova living/adu_screening_mvp`

## 1. Create a GitHub repository

Create a new empty repository in your GitHub account.

Recommended name:

- `lumanova-living-adu-screening`

Do not add a README or `.gitignore` from GitHub, because the local repository already has both.

## 2. Add the GitHub remote locally

From the project folder:

```bash
cd "/Users/mikezhang/Documents/lumanova living/adu_screening_mvp"
git remote add origin https://github.com/YOUR_USERNAME/lumanova-living-adu-screening.git
```

If you already added a remote and need to replace it:

```bash
git remote remove origin
git remote add origin https://github.com/YOUR_USERNAME/lumanova-living-adu-screening.git
```

## 3. Push the local branch

```bash
cd "/Users/mikezhang/Documents/lumanova living/adu_screening_mvp"
git push -u origin main
```

## 4. Deploy on Streamlit Community Cloud

1. Open Streamlit Community Cloud.
2. Choose the GitHub repository you just pushed.
3. Set the entry file to `app.py`.
4. Add secrets from:
   - `.streamlit/secrets.example.toml`
5. Start with:
   - `ADU_FORCE_PUBLIC_ONLY = "true"`
6. If you also want hosted admin access, add:
   - `ADU_ADMIN_PASSWORD = "your-real-password"`

## 5. Recommended first hosted setup

For the first public release:

- keep public mode open online
- keep admin review local unless you need hosted admin immediately
- connect Google Sheets webhook before sending paid traffic or broad outreach

## 6. After first push

Use these links in your launch materials:

- `?view=public`
- `?view=public&entry=garage`
- `?view=public&entry=adu`
- `?view=public&entry=legalization`

You can also use the admin `Launch Kit` tab to generate tracked links for:

- WeChat
- agent partners
- social posts
- embedded widget tests
