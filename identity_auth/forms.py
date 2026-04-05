from django import forms
from django.db.models import ImageField
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User

from home.models import Customer
from home.registration_guards import (
    validate_person_name,
    validate_registration_username,
    validate_registration_email_domain,
    reject_honeypot,
)
from identity_auth.models import SiteCustomerAuthSettings


class CustomerRegistrationForm(UserCreationForm):
    """Форма регистрации заказчика"""

    first_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Имя *'}),
    )
    last_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Фамилия *'}),
    )
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email *'}),
    )
    phone = forms.CharField(
        max_length=20,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Телефон *'}),
    )
    company = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Компания (необязательно)'}),
    )
    position = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Должность (необязательно)'}),
    )
    address = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Адрес (необязательно)'}),
    )
    company_fax = forms.CharField(
        required=False,
        label='',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'autocomplete': 'off',
            'tabindex': '-1',
            'aria-hidden': 'true',
        }),
    )

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'username', 'password1', 'password2']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Логин *'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Пароль *'})
        self.fields['password2'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Подтвердите пароль *'})
        self.fields['company_fax'].required = False

    def clean_first_name(self):
        return validate_person_name(self.cleaned_data.get('first_name'), 'Имя')

    def clean_last_name(self):
        return validate_person_name(self.cleaned_data.get('last_name'), 'Фамилия')

    def clean_username(self):
        u = self.cleaned_data.get('username')
        if u:
            validate_registration_username(u)
        return super().clean_username()

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email:
            validate_registration_email_domain(email)
            if User.objects.filter(email=email).exists():
                raise forms.ValidationError('Пользователь с таким email уже существует.')
        return email

    def clean_company_fax(self):
        reject_honeypot(self.cleaned_data.get('company_fax'))
        return ''

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']

        if commit:
            user.save()
            Customer.objects.create(
                user=user,
                phone=self.cleaned_data['phone'],
                company=self.cleaned_data.get('company', ''),
                position=self.cleaned_data.get('position', ''),
                address=self.cleaned_data.get('address', ''),
            )
        return user


class CustomerLoginForm(AuthenticationForm):
    """Форма входа для заказчика"""

    username = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Логин или Email'}),
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Пароль'}),
    )


_PW = 'w-full rounded-lg border border-gray-300 px-3 py-2 font-mono text-sm text-gray-900'
_IN = {'class': 'w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900'}


class SiteCustomerAuthSettingsForm(forms.ModelForm):
    """Секреты: пустое поле при сохранении = оставить прежнее значение в БД."""

    SECRET_FIELDS = frozenset({
        'vkid_protected_key',
        'vkid_service_key',
        'yandex_oauth_client_secret',
        'google_oauth_client_secret',
        'max_oidc_client_secret',
    })

    class Meta:
        model = SiteCustomerAuthSettings
        fields = [
            'vkid_app_id',
            'vkid_redirect_url',
            'vkid_protected_key',
            'vkid_service_key',
            'yandex_oauth_client_id',
            'yandex_oauth_client_secret',
            'google_oauth_client_id',
            'google_oauth_client_secret',
            'max_oidc_issuer',
            'max_oidc_client_id',
            'max_oidc_client_secret',
            'yandex_oauth_button_icon',
            'google_oauth_button_icon',
            'max_oauth_button_icon',
        ]
        widgets = {
            'vkid_app_id': forms.TextInput(attrs=_IN),
            'vkid_redirect_url': forms.URLInput(attrs=_IN),
            'vkid_protected_key': forms.PasswordInput(render_value=False, attrs={**_IN, 'autocomplete': 'new-password'}),
            'vkid_service_key': forms.PasswordInput(render_value=False, attrs={**_IN, 'autocomplete': 'new-password'}),
            'yandex_oauth_client_id': forms.TextInput(attrs=_IN),
            'yandex_oauth_client_secret': forms.PasswordInput(render_value=False, attrs={**_IN, 'autocomplete': 'new-password'}),
            'google_oauth_client_id': forms.TextInput(attrs=_IN),
            'google_oauth_client_secret': forms.PasswordInput(render_value=False, attrs={**_IN, 'autocomplete': 'new-password'}),
            'max_oidc_issuer': forms.URLInput(attrs=_IN),
            'max_oidc_client_id': forms.TextInput(attrs=_IN),
            'max_oidc_client_secret': forms.PasswordInput(render_value=False, attrs={**_IN, 'autocomplete': 'new-password'}),
            'yandex_oauth_button_icon': forms.FileInput(attrs={'class': 'block w-full text-sm text-gray-600'}),
            'google_oauth_button_icon': forms.FileInput(attrs={'class': 'block w-full text-sm text-gray-600'}),
            'max_oauth_button_icon': forms.FileInput(attrs={'class': 'block w-full text-sm text-gray-600'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in self.SECRET_FIELDS:
            self.fields[name].required = False
        for img in ('yandex_oauth_button_icon', 'google_oauth_button_icon', 'max_oauth_button_icon'):
            self.fields[img].required = False

    def save(self, commit=True):
        instance = self.instance
        cd = self.cleaned_data
        for name in self.Meta.fields:
            if name in self.SECRET_FIELDS:
                if cd.get(name):
                    setattr(instance, name, cd[name])
                continue
            field = self._meta.model._meta.get_field(name)
            if isinstance(field, ImageField):
                f = cd.get(name)
                if f:
                    setattr(instance, name, f)
            else:
                setattr(instance, name, cd[name])
        if commit:
            instance.save()
        return instance
