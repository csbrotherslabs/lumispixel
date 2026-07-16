from django import forms
from django.contrib.auth import authenticate

from .models import User


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
