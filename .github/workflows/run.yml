name: Run Hunter Dog Pipeline

on:
  schedule:
    - cron: "0 6 */2 * *"
  workflow_dispatch:

jobs:
  run-pipeline:
    runs-on: ubuntu-latest
    timeout-minutes: 60

    env:
      GOOGLE_CREDS_JSON: ${{ secrets.GOOGLE_CREDS_JSON }}
      GROQ_API_KEY: ${{ secrets.GROQ_API_KEY }}
      GMAIL_USER: ${{ secrets.GMAIL_USER }}
      GMAIL_APP_PASSWORD: ${{ secrets.GMAIL_APP_PASSWORD }}
      META_ACCESS_TOKEN: ${{ secrets.META_ACCESS_TOKEN }}

    steps:
      - name: Check out repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip

      - name: Set up Node
        uses: actions/setup-node@v4
        with:
          node-version: "20"

      - name: Cache Playwright browsers
        uses: actions/cache@v4
        with:
          path: ~/.cache/ms-playwright
          key: ${{ runner.os }}-playwright-${{ hashFiles('requirements.txt') }}
          restore-keys: |
            ${{ runner.os }}-playwright-

      - name: Cache npm packages
        uses: actions/cache@v4
        with:
          path: ~/.npm
          key: ${{ runner.os }}-npm-lighthouse
          restore-keys: |
            ${{ runner.os }}-npm-

      - name: Install Python dependencies
        run: |
          python -m pip install --upgrade pip
          python -m pip install -r requirements.txt
          python -m pip install \
            gspread \
            google-auth \
            google-auth-oauthlib \
            google-api-python-client \
            playwright

      - name: Install Playwright browser
        run: python -m playwright install --with-deps chromium

      - name: Install Lighthouse
        run: npm install --global lighthouse

      - name: Warm npx Lighthouse cache
        run: npx lighthouse --version

      - name: Run pipeline
        run: python -m hunterdog.pipeline.run_pipeline
