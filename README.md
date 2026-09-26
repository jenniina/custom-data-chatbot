# Context Me

A Django application that converts Word documents into searchable data and answers questions using OpenAI. Readers can chat without an account. Document management, conversion, OneDrive imports and appearance settings require administrator sign-in.

The interface uses project-owned HTML templates, native controls and a small optional script for progress feedback and keyboard shortcuts. There is no Streamlit dependency or markup-repair adapter. See [ACCESSIBILITY.md](ACCESSIBILITY.md) for testing and remaining manual checks.

## Start on Windows

1. Install Python 3.11 or newer and run **Setup.bat**.
2. Keep your existing private `.env` or copy `.env.example` to `.env`. Set `OPENAI_API_KEY`, a custom `ADMIN_USERNAME` (other than `admin`), and a random `ADMIN_PASSWORD` of at least 16 characters.
3. Run **Start Chatbot.bat**, then open [the local app](http://127.0.0.1:8501).
4. Open **Menu → Administrator sign-in**. Sign in using your `ADMIN_USERNAME` and `ADMIN_PASSWORD`.
5. Choose **Convert or import**, select your DOCX, review it and choose **Add to chatbot library**. JSON download is optional.

The menu starts closed. Keep the launcher window open while using the app; Ctrl+C stops it. **Start Converter.bat** runs the same application; the converter is at `/admin/convert/`. If the chatbot is already running, use its converter page instead of starting another server.

There is no automatic administrator access, even locally. If you prefer not to set `ADMIN_PASSWORD` locally, run `python manage.py migrate` and `python manage.py createsuperuser` to create an account interactively. Hosted deployments require the administrator secret.

Existing `.streamlit/secrets.toml` values are read as a migration fallback. Environment variables and `.env` take precedence. New deployments should use environment secrets. The old Streamlit configuration file is no longer used.

## Persistent cloud storage

Cloud Run requires a private `DATABASE_URL` for PostgreSQL. This stores documents, embeddings, appearance, accounts and sessions outside the temporary container. See [PERSISTENT_STORAGE.md](PERSISTENT_STORAGE.md) for a low-cost Neon setup. Desktop use without that setting continues to use local SQLite.

## Migrating the existing app

- Keep the same `CONTEXT_ME_DATA_DIR`. The existing `library.sqlite3`, its embeddings and appearance settings are reused without reindexing.
- Django creates a separate `web.sqlite3` for hashed administrator passwords and private server sessions. Existing Streamlit login/chat sessions are not migrated.
- Local setup creates a random Django signing key in the ignored data directory. Online hosting requires a stable `DJANGO_SECRET_KEY` and exact `DJANGO_ALLOWED_HOSTS`.
- Update dependencies and the Cloud Run image/command. Streamlit launch commands and Streamlit Community Cloud are no longer supported.
- No data or secrets need to be committed. See [DEPLOYMENT.md](DEPLOYMENT.md) before redeploying.

## Features and data

**Appearance:** Administrators can change the title, caption and explanation under **Menu → Appearance**. These are plain display text; they do not change chatbot instructions.

**Conversion:** DOCX body paragraphs and tables are read on the server without an API call. Plain English, plain Finnish and bilingual documents work without a special heading layout. Older `.doc` files must be saved as `.docx` first. Images, text boxes, headers, footers, footnotes, comments and nested tables are not extracted. Resolve tracked changes before conversion.

**Bilingual JSON:** Schema version 2 keeps `en`, `fi`, `shared`, `key`, `original_text`, `section` and `location` fields in source records. Explicit EN:/FI: pairs are separated, for example:

```text
EN: I live in Helsinki.
FI: Asun Helsingissä.
```

Single-language prose stays in shared/unlabelled content. No translation is generated or guessed. Search passages contain both languages and shared content. Version 1 JSON and existing indexes still work. Version 2 imports validate that the passages match their records.

**Publishing:** Adding a document sends its text to OpenAI for embeddings, then saves text and embeddings in the private library database. Identical reimports are skipped. An edited Word document has a new identity; remove its older version if replacing it. Failed indexing leaves the previous saved document intact.

**Questions:** The app retrieves six matching passages, then sends them and up to eight recent messages to OpenAI. Broad summaries may omit information. Answers follow the question's language; select the matching conversation language for screen-reader pronunciation. Retrieved source panels are administrator-only, but public answers can disclose facts from the indexed documents.

**Sessions:** Conversations, previews and optional Microsoft tokens are stored in Django's server-side database, not browser cookies. Cookies contain an opaque session identifier. Sessions expire one hour after their last modification and browser cookies expire at browser close. Clear conversation removes current chat history; signing out flushes the current session. Run `python manage.py clearsessions` regularly to delete expired database rows; the launcher also does this at startup. Expiry is not secure erasure of database remnants or backups.

**Configuration:** API keys are server-side only. Set `OPENAI_CHAT_MODEL` to a Responses-compatible model enabled for your account (existing default: `gpt-6-astra`). Embeddings default to `text-embedding-3-small`; remove/rebuild indexed documents before changing `OPENAI_EMBEDDING_MODEL`. OpenAI API billing is separate from ChatGPT. Responses use `store=False`, which does not override other API retention policies.

**OneDrive:** Public sharing links and optional private Microsoft connections are supported. Imports are manual. OneDrive source edits do not automatically update the chatbot. See [ONEDRIVE.md](ONEDRIVE.md).

## Commands

From the project folder, with the virtual environment active:

```text
python serve.py
python convert.py path/to/profile.docx -o profile.json
python run_tests.py
```

The command-line converter makes no API calls and refuses to overwrite a file unless `--force` is supplied. `app.py` and `converter_app.py` remain compatibility launchers for Django.

Tests use temporary data and mocked OpenAI. For browser/accessibility checks, install `requirements-dev.txt` and follow [ACCESSIBILITY.md](ACCESSIBILITY.md).

The repository ignores data, DOCX/JSON files, databases and secrets. Docker uses a source-code allowlist. See [DEPLOYMENT.md](DEPLOYMENT.md) for Cloud Run's storage limitations and deployment settings.
