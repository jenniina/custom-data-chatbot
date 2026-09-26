import secrets
import time
from hashlib import sha256
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.views import LoginView
from django.contrib.auth.decorators import user_passes_test
from django.core.cache import cache
from django.http import Http404, FileResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST, require_http_methods
from openai import OpenAI

from context_me.access import setting
from context_me.chat import answer
from context_me.documents import convert_docx, dump_document, load_document
from .storage import library
from context_me.onedrive import OneDrive
from context_me.public_onedrive import read_public_document
from .forms import AdminLoginForm, AppearanceForm, DrivePathForm, PublicLinkForm, QuestionForm, UploadForm

admin_required = user_passes_test(lambda u: u.is_authenticated and u.is_active and u.is_staff)

def api_client():
    key = setting("OPENAI_API_KEY").strip()
    if not key or key == "your-api-key-here":
        raise ValueError("Configure OPENAI_API_KEY in the server settings.")
    return OpenAI(api_key=key, timeout=90, max_retries=2)

def limited(request, scope, maximum, seconds):
    # Per-process/IP protection. Put distributed rate limiting at the hosting edge.
    identity = request.META.get("REMOTE_ADDR", "unknown")
    key = scope + ":" + sha256(identity.encode()).hexdigest()
    if cache.add(key, 1, seconds):
        return False
    try:
        return cache.incr(key) > maximum
    except ValueError:
        return False

def error_message(error):
    if isinstance(error, ValueError):
        return str(error)
    return "The operation could not be completed. Check the file, connection, API settings and available storage, then try again."

def page(request, template, **context):
    return render(request, template, {"presentation": library().presentation(), **context})

def csrf_failure(request, reason=""):
    # Do not expose validation details or echo submitted private values.
    return render(request, "403.html", {"presentation": library().presentation()}, status=403)

class AdminLoginView(LoginView):
    template_name = "login.html"
    authentication_form = AdminLoginForm
    redirect_authenticated_user = False

    def post(self, request, *args, **kwargs):
        if limited(request, "login", 10, 300):
            form = self.get_form()
            form.add_error(None, "Too many sign-in attempts. Please wait five minutes and try again.")
            return self.form_invalid(form)
        return super().post(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        return {**super().get_context_data(**kwargs), "presentation": library().presentation()}

@require_POST
def logout(request):
    auth_logout(request)  # Flushes preview data, conversation and Microsoft tokens too.
    return redirect("chat")

@require_http_methods(["GET", "POST"])
def chat(request):
    store = library()
    form = QuestionForm(request.POST if request.method == "POST" else None,
                        initial={"language": request.session.get("language", "en")})
    history = request.session.get("conversation", [])
    if request.method == "POST" and form.is_valid():
        if limited(request, "chat", 20, 60):
            form.add_error(None, "Please wait a minute before sending another question.")
        elif not store.documents():
            form.add_error(None, "The administrator has not added any documents yet.")
        else:
            question = form.cleaned_data["question"]
            lang = form.cleaned_data["language"]
            try:
                reply, sources = answer(question, history, store, api_client(),
                                        setting("OPENAI_CHAT_MODEL", "gpt-6-astra"))
                history += [{"role": "user", "content": question, "language": lang},
                            {"role": "assistant", "content": reply, "language": lang,
                             "sources": sources if request.user.is_staff else []}]
                request.session["conversation"] = history[-40:]
                request.session["language"] = lang
                return redirect(reverse("chat") + "#latest-answer")
            except Exception:
                form.add_error(None, "Chat is temporarily unavailable. Please try again later or contact the administrator. Your question has been kept below.")
    # Never send raw retrieved passages to public templates, even after privilege changes.
    display = [{k: v for k, v in entry.items() if k != "sources" or request.user.is_staff} for entry in history]
    return page(request, "chat.html", form=form, history=display, has_documents=bool(store.documents()))

@require_POST
def clear_chat(request):
    request.session.pop("conversation", None)
    return redirect("chat")

@admin_required
@require_http_methods(["GET", "POST"])
def convert(request):
    upload = UploadForm(request.POST if request.method == "POST" and request.POST.get("action") == "upload" else None,
                        request.FILES if request.method == "POST" else None)
    link = PublicLinkForm(request.POST if request.method == "POST" and request.POST.get("action") == "link" else None,
                          initial={"url": setting("ONEDRIVE_PUBLIC_URL")})
    if request.method == "POST":
        action = request.POST.get("action")
        form = upload if action == "upload" else link
        if action in ("upload", "link") and form.is_valid():
            try:
                if action == "upload":
                    file = upload.cleaned_data["document"]
                    raw = file.read()
                    document = convert_docx(raw, file.name) if file.name.lower().endswith(".docx") else load_document(raw)
                else:
                    document = read_public_document(**link.cleaned_data)
                set_preview(request, document)
                return redirect("preview")
            except Exception as error:
                form.add_error(None, error_message(error))
    return page(request, "convert.html", upload_form=upload, link_form=link,
                private_drive_enabled=bool(setting("ONEDRIVE_CLIENT_ID")))

def set_preview(request, document):
    request.session["preview"] = document
    request.session["preview_id"] = secrets.token_urlsafe(24)

def checked_preview(request, token):
    document = request.session.get("preview")
    if not document or not secrets.compare_digest(token, request.session.get("preview_id", "")):
        raise Http404("This preview has expired. Please load the document again.")
    return document

@admin_required
@require_http_methods(["GET", "POST"])
def preview(request):
    if request.method == "POST":
        document = checked_preview(request, request.POST.get("preview_id", ""))
        try:
            added = library().add(document, api_client(), setting("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"))
            request.session.pop("conversation", None)
            messages.success(request, "Document added to the chatbot library." if added else "This document is already in the library.")
            # Keep preview available for optional download, but use PRG to avoid re-index on refresh.
            return redirect("library")
        except Exception as error:
            messages.error(request, error_message(error))
    document = request.session.get("preview")
    if not document:
        return redirect("convert")
    return page(request, "preview.html", document=document, preview_id=request.session["preview_id"])

@admin_required
def download(request, token):
    document = checked_preview(request, token)
    from io import BytesIO
    filename = Path(document["source"].replace("\\", "/")).stem + ".json"
    return FileResponse(BytesIO(dump_document(document).encode("utf-8")), as_attachment=True,
                        filename=filename, content_type="application/json")

@admin_required
def library_page(request):
    return page(request, "library.html", documents=library().documents())

@admin_required
@require_http_methods(["GET", "POST"])
def remove(request, document_id):
    store = library()
    document = next((d for d in store.documents() if d[0] == document_id), None)
    if document is None:
        raise Http404("Document not found.")
    if request.method == "POST":
        store.remove(document_id)
        request.session.pop("conversation", None)
        messages.success(request, "Document removed from future searches.")
        return redirect("library")
    return page(request, "remove.html", document=document)

@admin_required
@require_http_methods(["GET", "POST"])
def appearance(request):
    store = library()
    form = AppearanceForm(request.POST if request.method == "POST" else None, initial=store.presentation())
    if request.method == "POST" and form.is_valid():
        store.save_presentation(**form.cleaned_data)
        messages.success(request, "Appearance saved.")
        return redirect("appearance")
    return page(request, "appearance.html", form=form)

def drive_connection(request):
    return OneDrive(setting("ONEDRIVE_CLIENT_ID"), request.session.get("drive_cache"))

@admin_required
@require_http_methods(["GET", "POST"])
def onedrive(request):
    form = DrivePathForm(request.POST if request.method == "POST" and request.POST.get("action") == "load" else None)
    if request.method == "POST":
        action = request.POST.get("action")
        try:
            if action == "disconnect":
                for key in list(request.session.keys()):
                    if key.startswith("drive_"):
                        del request.session[key]
                request.session.pop("preview", None)
                request.session.pop("preview_id", None)
                messages.success(request, "OneDrive disconnected.")
            elif action == "connect":
                drive = OneDrive(setting("ONEDRIVE_CLIENT_ID"))
                request.session["drive_flow"] = drive.begin_sign_in()
                request.session["drive_cache"] = drive.serialize_cache()
                request.session["drive_ready"] = False
            elif action == "poll":
                flow = request.session.get("drive_flow")
                if not flow:
                    raise ValueError("Start a new OneDrive connection.")
                if time.time() < request.session.get("drive_poll_after", 0):
                    raise ValueError("Please wait a few seconds before checking again.")
                request.session["drive_poll_after"] = time.time() + flow.get("interval", 5)
                drive = drive_connection(request)
                if drive.finish_sign_in(flow):
                    request.session["drive_ready"] = True
                    request.session.pop("drive_flow", None)
                    messages.success(request, "OneDrive connected.")
                else:
                    messages.info(request, "Microsoft sign-in is still pending. Finish sign-in and check again.")
                request.session["drive_cache"] = drive.serialize_cache()
            elif action == "load" and form.is_valid():
                if not request.session.get("drive_ready"):
                    raise ValueError("Connect OneDrive first.")
                drive = drive_connection(request)
                set_preview(request, drive.read_document(form.cleaned_data["path"]))
                request.session["drive_cache"] = drive.serialize_cache()
                return redirect("preview")
            if action != "load" or form.is_valid():
                return redirect("onedrive")
        except Exception as error:
            form.add_error(None, error_message(error))
    return page(request, "onedrive.html", form=form, enabled=bool(setting("ONEDRIVE_CLIENT_ID")),
                flow=request.session.get("drive_flow"), connected=request.session.get("drive_ready", False))
