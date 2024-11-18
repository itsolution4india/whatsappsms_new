from django import forms

class UserLoginForm(forms.Form):
    username_or_email = forms.CharField(label="Email or Username")
    password = forms.CharField(label="Password", widget=forms.PasswordInput)
