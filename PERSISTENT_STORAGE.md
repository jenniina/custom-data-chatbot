# Persistent storage on a small budget

The app can stay on Cloud Run while its data lives in a private PostgreSQL database. No document data or credentials need to go into GitHub.

## Create the database

1. Create an account at https://neon.com and choose the **Free** plan. Create a project for this chatbot in a nearby EU region, such as Frankfurt if available.
2. In the project, open **Connect**, select the production branch/database, and enable connection pooling. Copy the PostgreSQL connection URL, including its SSL options. Copy only the URL, not a surrounding `psql` command or shell quotes.
3. Treat that URL as a password. Do not paste it into chat, source code, GitHub or screenshots.
4. In Google Secret Manager, save it as a new secret. Give the Cloud Run service account access to this secret. In the new Cloud Run revision, expose the secret as the environment variable **`DATABASE_URL`**. You can also use a private environment variable, but Secret Manager is preferable for credentials.
5. Keep the existing `DJANGO_SECRET_KEY`, `ADMIN_USERNAME`, `ADMIN_PASSWORD` and `OPENAI_API_KEY`. Rebuild and deploy the updated image and route all traffic to it. Do not enable `ALLOW_TEMPORARY_DATABASE`.
6. Sign in and import/publish the original DOCX or JSON once. Both its text and generated embeddings are now saved in PostgreSQL. Normal restarts do not call OpenAI to rebuild embeddings.
7. Change an appearance setting, then deploy another revision with the same database secret. Verify that the documents and appearance remain present. The app's local persistence smoke test covers this using disposable PostgreSQL, but your deployed database connection should also be checked.

The Free plan currently includes 0.5 GB database storage and 100 CU-hours per project per month (checked 2026-09-26). It scales down while idle without deleting the data. This is a starting option for a small, lightly used chatbot, not a guarantee that all traffic will fit. Check usage in Neon. Free-plan limits, recovery windows and availability differ from paid plans; keep your original DOCX/JSON and private backups. Cloud Run, network transfer and OpenAI remain separate costs.

Pricing: https://neon.com/pricing
Django setup: https://neon.com/docs/guides/django

## Reuse an existing local library without re-embedding

If you still have a populated local `data/library.sqlite3`, you can copy its saved text, embeddings and appearance into an **empty** PostgreSQL library. This never writes to the SQLite source. It refuses a populated destination, so it cannot overwrite published cloud data.

1. Back up your local library privately. Stop the local app.
2. Install the updated requirements.
3. Add the same private `DATABASE_URL` to your ignored `.env`. Be aware that running the local app with this setting will access the production database.
4. Run:

```text
python manage.py import_library data/library.sqlite3
```

No OpenAI API calls are made by this command. Cloud Run startup initializes the Django account/session tables and synchronizes your configured administrator. Old local account/session records are not copied; sign in again. Remove `DATABASE_URL` from local configuration afterwards if you want the desktop app to keep using its local database.

If the Cloud Run instance holding the only uploaded copy has already stopped, there is no local database to recover from. Reimport the original document once after connecting PostgreSQL.

## Maintenance and checks

- Keep all future revisions pointed at the same database. A different database or branch will have different data.
- Database outages raise errors; the app never falls back to an empty local library.
- Use the provider's private backup/export tools. Do not commit database dumps.
- The existing per-process login/chat rate limits have not been changed by this storage fix.
- Run `python tests/postgres_smoke.py` with Docker running to test storage across separate app processes and empty local directories, without real API calls or personal documents.
