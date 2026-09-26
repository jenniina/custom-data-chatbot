# Deploy the Django chatbot

The application uses Django 5.2 LTS, Waitress and WhiteNoise. Start it with `python serve.py` or the supplied Dockerfile. The launcher applies Django migrations, synchronizes the administrator account, removes expired sessions, collects static assets and starts the server.

Readers do not sign in. Administrator pages require a Django staff account. The `ADMIN_USERNAME` and `ADMIN_PASSWORD` settings create/update the administrator account at startup; changing it and restarting invalidates older login sessions.

## Required changes from Streamlit

Keep the existing OpenAI and administrator secrets. Add:

| Setting | Value |
| --- | --- |
| `DJANGO_SECRET_KEY` | A stable random secret of at least 50 characters; store it in Secret Manager |
| `DJANGO_ALLOWED_HOSTS` | Exact hostname(s), comma separated, without scheme or path; e.g. `your-service-123.europe-north1.run.app` |
| `CONTEXT_ME_HOSTED` | `true`; Cloud Run is also detected through `K_SERVICE` |
| `ADMIN_USERNAME` | Your chosen administrator username, other than `admin`; required when using `ADMIN_PASSWORD` |
| `ADMIN_PASSWORD` | Random administrator password, at least 16 characters |
| `DATABASE_URL` | Private PostgreSQL URL; required on Cloud Run, stored as a secret |
| `OPENAI_API_KEY` | Your private OpenAI API key |
| `CONTEXT_ME_DATA_DIR` | Private data directory; Docker defaults to `/data` |

Optional settings: `OPENAI_CHAT_MODEL`, `OPENAI_EMBEDDING_MODEL`, `ONEDRIVE_CLIENT_ID`, `ONEDRIVE_PUBLIC_URL`. `DJANGO_CSRF_TRUSTED_ORIGINS` accepts comma-separated exact HTTPS origins if your proxy architecture requires them. Same-origin Cloud Run forms do not normally need it.

Generate a signing key locally with:

```text
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

Store the generated value privately; never put it in Git. Keep it stable across restarts. Hosted startup refuses missing/short secrets or unrestricted host settings. Debug output is disabled online.

## Cloud Run

1. Build and deploy the supplied Dockerfile instead of using a Streamlit command.
2. Remove any old command/arguments override so the container runs `python serve.py`.
3. Configure the secrets and exact service hostname above.
4. The image defaults to port **8080** and listens on Cloud Run's `PORT` value. If your service still specifies 8501, the injected PORT is honored.
5. Use HTTPS. The launcher trusts the hosting proxy's forwarded protocol, so hosted mode must sit behind a trusted proxy, not directly on an unprotected port.
6. Open the site, select **Menu → Administrator sign-in**, and sign in using your configured `ADMIN_USERNAME` and `ADMIN_PASSWORD`.
7. Convert/import a document, review it and publish it directly to the library.

The public chatbot requires unauthenticated invocation at Cloud Run's service layer; the administrator routes remain protected by Django.

### If Cloud Run reports that the container did not listen on PORT

Use container port **8080** and clear old container command/argument overrides. The image runs `python serve.py`, binds to `0.0.0.0`, and always honors the injected `PORT`. The launcher's 8501 default is only for local desktop use; its hosted default is 8080. Changing `EXPOSE` alone does not start a server or fix an application crash.

The generic Cloud Run port/timeout message can also mean Python exited before opening the socket. Open the failed revision's **Logs** and look for the first Python exception, not just the final health-check message. Startup now logs each phase: configuration, migrations, administrator setup, session cleanup, static files, and server launch.

Common configuration failures in this project:

- `DJANGO_SECRET_KEY`: a random secret of at least 50 characters, supplied to the running revision.
- `ADMIN_USERNAME`: a custom username other than `admin`, supplied to the running revision.
- `ADMIN_PASSWORD`: at least 16 characters, supplied to the running revision.
- `DJANGO_ALLOWED_HOSTS`: the service's exact hostname without `https://`, a path, or a port. Wildcard `*` is rejected.
- `CONTEXT_ME_DATA_DIR`: a writable Linux directory (`/data` in this image), not a Windows path from a local `.env`.

Docker intentionally excludes local `.env` and secret files. Configure the values in Cloud Run's environment/Secret Manager settings; their presence on your laptop does not supply them to the deployed container. Rebuild and deploy a new revision after code changes. Extending the startup timeout does not repair an exception.

Google's [startup troubleshooting guide](https://cloud.google.com/run/docs/troubleshooting#container-failed-to-start) explains the required port/interface and checking application logs.

### Persistent storage for Cloud Run

Set `DATABASE_URL` to a private PostgreSQL connection URL. Both Django accounts/sessions and the document library (text, embeddings and appearance) use that database. Cloud Run instances can be replaced without losing this data. Without `DATABASE_URL`, Cloud Run startup now fails with a clear message rather than creating an empty temporary library. Never set `ALLOW_TEMPORARY_DATABASE=true` in production; that override exists only for disposable container tests.

For a low-cost setup, follow [the Neon setup guide](PERSISTENT_STORAGE.md). Other compatible PostgreSQL providers work too. Keep `DJANGO_SECRET_KEY`, `ADMIN_USERNAME` and `ADMIN_PASSWORD` consistent between revisions.

Desktop use without `DATABASE_URL` still keeps `library.sqlite3` and `web.sqlite3` under `CONTEXT_ME_DATA_DIR`. With PostgreSQL, that local directory is used for temporary/static files only. Do not mount SQLite on a Cloud Storage FUSE or OneDrive-synced directory.

The startup script serializes database setup across instances and creates all required tables. Do not send traffic to an older SQLite revision after switching storage. Changing storage does not recover files from terminated Cloud Run instances; import the original DOCX/JSON once, or use the saved-library import described in the setup guide.

## Updating an existing library

Preserve the existing `library.sqlite3` in the same data directory. No format change or re-embedding is required. Django creates `web.sqlite3` alongside it. The old Streamlit sessions are discarded; users sign in again.

The new interface replaces tabs/sidebar widgets with ordinary pages and a collapsed Menu. Appearance remains editable. The converter accepts DOCX and existing JSON and publishes without a download/re-upload step.

## Operations

- Run `python manage.py check --deploy` with hosted environment settings before publishing.
- Run `python manage.py clearsessions` periodically for long-running servers; expired data remains physically stored until cleanup. Startup also runs cleanup.
- Keep the data directory and its backups private. Session data includes conversation text, document previews and optional Microsoft tokens; it is not encrypted by the application.
- The app has per-process/IP limits for login attempts and questions. These are not distributed protection; proxy addressing can also group readers under one IP. Configure hosting-edge limits and OpenAI project spending controls for public use.
- Keep Django security updates within the supported 5.2 series current. Rerun functional and browser audits after dependency changes.
- Do not use Django's development server for production.

See Django's [deployment checklist](https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/).

## Git and Docker

Only application code belongs in GitHub. `.env`, legacy `.streamlit/secrets.toml`, data directories, JSON, Word files and databases are ignored. The Docker build context has an explicit allowlist containing only code, templates, static assets and dependencies. Do not force-add personal files.

No deployment or repository publication is performed by the setup scripts.

## Docker verification

The Django image was built and tested locally on 2026-09-25. Its runtime smoke test verifies startup, static assets, HTTPS proxy handling, CSRF protection, administrator login, DOCX conversion and bilingual JSON download using disposable credentials and fictional data. It also checks that the application runs as a non-root user and that personal data and secret files are absent from the image's application directory.

To repeat the build and runtime checks, with Docker running and the Python environment active:

```text
docker build -t context-me:django-test .
python tests/docker_smoke.py
```

The smoke test removes its container afterward and makes no OpenAI API calls. It does not publish the image or deploy to Cloud Run.

## Changing the administrator username

Set `ADMIN_USERNAME` privately in your local `.env` and in the Cloud Run revision configuration before deploying this update. There is no default username. Choose your own value; do not copy a public example.

On startup, an existing superuser named `admin` is renamed to your chosen username, keeping its database identity and invalidating its previous login sessions. With a fresh database, the configured account is created directly. Restarting with the same settings preserves the account. Conflicting existing accounts cause a clear startup error instead of silently granting access or leaving the old login active.

For a later rename from a custom username, also set `ADMIN_PREVIOUS_USERNAME` to the old username for the rollout. Remove that setting once the rename has completed on your persistent database. Keep `ADMIN_USERNAME` set to the new value.

A custom username reduces attempts against the common `admin` login, but does not replace a strong password or login rate limits.
