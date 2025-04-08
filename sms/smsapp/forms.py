from django import forms
from .models import CustomUser

class UserLoginForm(forms.Form):
    username_or_email = forms.CharField(label="Email or Username")
    password = forms.CharField(label="Password", widget=forms.PasswordInput)

CATEGORY_CHOICES = [
    ('marketing', 'Marketing'),
    ('authentication', 'Authentication')
]

TYPE_CHOICES = [
    ('credit', 'Credit'),
    ('debit', 'Debit')
]

class CoinTransactionForm(forms.Form):
    user = forms.ModelChoiceField(queryset=CustomUser.objects.all(), label="Select User")
    category = forms.ChoiceField(choices=CATEGORY_CHOICES)
    transaction_type = forms.ChoiceField(choices=TYPE_CHOICES)
    number_of_coins = forms.IntegerField(min_value=1, label="Number of Coins")