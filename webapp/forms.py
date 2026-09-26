from django import forms
from django.contrib.auth.forms import AuthenticationForm
from context_me.documents import MAX_FILE_BYTES

class AdminLoginForm(AuthenticationForm):
    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if not user.is_staff:
            raise forms.ValidationError("This account does not have administrator access.")

class QuestionForm(forms.Form):
    question = forms.CharField(label="What would you like to know?", max_length=8000,
                               widget=forms.Textarea(attrs={"rows": 3, "aria-describedby": "question-help"}))
    language = forms.ChoiceField(label="Conversation language", choices=[("en", "English"), ("fi", "Suomi")],
                                help_text="Choose the language you are writing in so screen readers pronounce the conversation correctly.")

class UploadForm(forms.Form):
    document = forms.FileField(label="Word document or converted JSON", help_text="Choose one .docx or .json file, up to 20 MB.",
                               widget=forms.ClearableFileInput(attrs={"accept": ".docx,.json"}))
    def clean_document(self):
        upload = self.cleaned_data["document"]
        if upload.size > MAX_FILE_BYTES:
            raise forms.ValidationError("The file exceeds the 20 MB limit.")
        if not upload.name.lower().endswith((".docx", ".json")):
            raise forms.ValidationError("Choose a .docx or converter-produced .json file.")
        return upload

class PublicLinkForm(forms.Form):
    url = forms.URLField(label="Public OneDrive sharing link", max_length=8192)
    source_name = forms.CharField(label="Document name (optional)", required=False, max_length=200)

class DrivePathForm(forms.Form):
    path = forms.CharField(label="File path within OneDrive", max_length=1000, help_text="For example: ContextMe/profile.docx")

class AppearanceForm(forms.Form):
    title = forms.CharField(label="Title", max_length=120)
    caption = forms.CharField(label="Caption", max_length=500, required=False, widget=forms.Textarea(attrs={"rows": 2}))
    explanation = forms.CharField(label="Explanation", max_length=3000, required=False, widget=forms.Textarea(attrs={"rows": 5}))
