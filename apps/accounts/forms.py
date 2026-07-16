from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password

from .models import User
from .services import DuplicateEmailError, SignupPayload, create_client_account, create_photographer_account


class EmailAuthenticationForm(forms.Form):
    email = forms.EmailField(widget=forms.EmailInput(attrs={"class": "form-control", "placeholder": "User Name or E-mail Address"}))
    password = forms.CharField(strip=False, widget=forms.PasswordInput(attrs={"class": "form-control", "placeholder": "Password"}))
    remember = forms.BooleanField(required=False)

    error_messages = {
        "invalid_login": "Please enter a correct email address and password.",
        "inactive": "This account cannot log in. Please contact support.",
    }

    def __init__(self, request=None, *args, **kwargs):
        self.request = request
        self.user_cache = None
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        email = cleaned_data.get("email")
        password = cleaned_data.get("password")
        if email and password:
            self.user_cache = authenticate(self.request, username=User.objects.normalize_email(email), password=password)
            if self.user_cache is None:
                raise forms.ValidationError(self.error_messages["invalid_login"], code="invalid_login")
            if not self.user_cache.can_login:
                raise forms.ValidationError(self.error_messages["inactive"], code="inactive")
        return cleaned_data

    def get_user(self):
        return self.user_cache


class SignupForm(forms.Form):
    duplicate_error = "An account may already exist for this email. Please log in to continue."

    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150)
    email = forms.EmailField()
    password = forms.CharField(strip=False, widget=forms.PasswordInput(render_value=False))
    password_confirmation = forms.CharField(strip=False, widget=forms.PasswordInput(render_value=False))
    accept_terms = forms.BooleanField(required=True, error_messages={"required": "You must accept the terms to continue."})
    accept_privacy = forms.BooleanField(required=True, error_messages={"required": "You must accept the privacy policy to continue."})

    account_type = "client"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        attrs = {
            "first_name": {"class": "form-control", "autocomplete": "given-name"},
            "last_name": {"class": "form-control", "autocomplete": "family-name"},
            "email": {"class": "form-control", "autocomplete": "email"},
            "password": {"class": "form-control", "autocomplete": "new-password"},
            "password_confirmation": {"class": "form-control", "autocomplete": "new-password"},
        }
        labels = {"accept_terms": "I accept the terms", "accept_privacy": "I accept the privacy policy"}
        for name, field in self.fields.items():
            if name in attrs:
                field.widget.attrs.update(attrs[name])
            if name in labels:
                field.label = labels[name]

    def clean_email(self):
        email = User.objects.normalize_email(self.cleaned_data["email"])
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(self.duplicate_error, code="duplicate")
        return email

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirmation = cleaned_data.get("password_confirmation")
        if password and confirmation and password != confirmation:
            self.add_error("password_confirmation", "Passwords do not match.")
        if password:
            validate_password(password)
        return cleaned_data

    def save(self):
        payload = SignupPayload(
            first_name=self.cleaned_data["first_name"].strip(),
            last_name=self.cleaned_data["last_name"].strip(),
            email=self.cleaned_data["email"],
            password=self.cleaned_data["password"],
        )
        try:
            if self.account_type == "photographer":
                return create_photographer_account(payload)
            return create_client_account(payload)
        except DuplicateEmailError:
            self.add_error("email", self.duplicate_error)
            return None


class ClientSignupForm(SignupForm):
    account_type = "client"


class PhotographerSignupForm(SignupForm):
    account_type = "photographer"
