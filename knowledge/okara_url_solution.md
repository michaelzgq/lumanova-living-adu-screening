# Okara URL Solution

## Why the raw Streamlit URL can fail in third-party tools

Some AI tools handle regular public web pages better than dynamic `streamlit.app` pages.
The most reliable pattern is:

1. Give the third-party tool a normal public landing page URL
2. Let that landing page describe the product in plain text
3. Redirect or link users to the live Streamlit intake

## Recommended setup

Use a static URL such as:

- `https://michaelzgq.github.io/lumanova-living-adu-screening/`

And let that page send users to:

- `https://lumanova-living-adu-screening-fzcdyrfu9pakal7eelwwzj.streamlit.app/`

## What exists in this repo now

A static landing page is now available at:

- `docs/index.html`

## Fastest publish method

### GitHub Pages

1. Open the GitHub repo settings
2. Open `Pages`
3. Set source to `Deploy from a branch`
4. Set branch to `main`
5. Set folder to `/docs`
6. Save

GitHub Pages should give you a URL like:

- `https://michaelzgq.github.io/lumanova-living-adu-screening/`

## Recommended use

### For Okara

Use the static GitHub Pages URL.

### For customers

Continue using the Streamlit URL directly.
