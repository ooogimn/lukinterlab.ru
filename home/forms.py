from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User
from .models import Otziv, OtzivComment, Order, OrderQuestionnaire, OrderFile, Customer, OrderComment, LegalInfo, Rabota
from .registration_guards import (
    validate_person_name,
    validate_registration_username,
    validate_registration_email_domain,
    validate_customer_full_name_for_account,
    reject_honeypot,
)


class OtzivForm(forms.ModelForm):
    class Meta:
        model = Otziv
        fields = ['name', 'firma', 'foto', 'body']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ваше имя'}),
            'firma': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Название компании (необязательно)'}),
            'foto': forms.FileInput(attrs={'class': 'form-control'}),
            'body': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Ваш отзыв'}),
        }


class OtzivCommentForm(forms.ModelForm):
    class Meta:
        model = OtzivComment
        fields = ['author_name', 'author_email', 'author_company', 'content']
        widgets = {
            'author_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ваше имя'}),
            'author_email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Ваш email'}),
            'author_company': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Название компании (необязательно)'}),
            'content': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Ваш комментарий'}),
        }

    def __init__(self, *args, **kwargs):
        self.parent_comment = kwargs.pop('parent_comment', None)
        super().__init__(*args, **kwargs)
        
        if self.parent_comment:
            # Если это ответ на комментарий, изменяем placeholder
            self.fields['content'].widget.attrs['placeholder'] = f'Ответ на комментарий от {self.parent_comment.author_name}...'
            # Скрываем поля, которые уже заполнены в родительском комментарии
            self.fields['author_name'].widget.attrs['value'] = self.parent_comment.author_name
            self.fields['author_email'].widget.attrs['value'] = self.parent_comment.author_email
            self.fields['author_company'].widget.attrs['value'] = self.parent_comment.author_company
            self.fields['author_name'].widget.attrs['readonly'] = True
            self.fields['author_email'].widget.attrs['readonly'] = True
            self.fields['author_company'].widget.attrs['readonly'] = True


class ContactForm(forms.Form):
    name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ваше имя *'
        })
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ваш email *'
        })
    )
    phone = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ваш телефон'
        }),
        required=False
    )
    message = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 5,
            'placeholder': 'Ваше сообщение *'
        })
    )


class AddToCartForm(forms.Form):
    """Форма добавления услуги в корзину"""
    service_type = forms.ChoiceField(
        choices=[
            ('service', 'Основная услуга'),
            ('extra_service', 'Дополнительная услуга'),
            ('standalone_extra_service', 'Независимая дополнительная услуга'),
        ],
        widget=forms.HiddenInput()
    )
    service_id = forms.IntegerField(widget=forms.HiddenInput())
    quantity = forms.IntegerField(
        min_value=1,
        initial=1,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'min': '1',
            'style': 'width: 80px;'
        })
    )


class OrderForm(forms.ModelForm):
    """Форма создания заказа с возможностью создания аккаунта"""
    create_account = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-checkbox h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded'
        }),
        label='Создать аккаунт для личного кабинета'
    )
    
    username = forms.CharField(
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Логин для входа в личный кабинет'
        }),
        label='Логин'
    )
    
    password1 = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Пароль'
        }),
        label='Пароль'
    )
    
    password2 = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Подтвердите пароль'
        }),
        label='Подтвердите пароль'
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
        model = Order
        fields = ['customer_name', 'customer_email', 'customer_phone']
        widgets = {
            'customer_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ваше полное имя *'
            }),
            'customer_email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ваш email *'
            }),
            'customer_phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ваш телефон *'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Делаем поля аккаунта необязательными по умолчанию
        self.fields['username'].required = False
        self.fields['password1'].required = False
        self.fields['password2'].required = False
        self.fields['company_fax'].required = False

    def clean_company_fax(self):
        reject_honeypot(self.cleaned_data.get('company_fax'))
        return ''

    def clean(self):
        cleaned_data = super().clean()
        create_account = cleaned_data.get('create_account')
        username = cleaned_data.get('username')
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')
        email = cleaned_data.get('customer_email')
        
        if create_account:
            try:
                validate_customer_full_name_for_account(cleaned_data.get('customer_name'))
            except forms.ValidationError as e:
                self.add_error('customer_name', e)
            if username:
                try:
                    validate_registration_username(username)
                except forms.ValidationError as e:
                    self.add_error('username', e)
            if email:
                try:
                    validate_registration_email_domain(email)
                except forms.ValidationError as e:
                    self.add_error('customer_email', e)
            # Проверяем, что логин указан
            if not username:
                raise forms.ValidationError('При создании аккаунта необходимо указать логин.')
            
            # Проверяем уникальность логина
            if User.objects.filter(username=username).exists():
                raise forms.ValidationError('Пользователь с таким логином уже существует.')
            
            # Проверяем, что пароли указаны
            if not password1:
                raise forms.ValidationError('При создании аккаунта необходимо указать пароль.')
            
            if not password2:
                raise forms.ValidationError('Необходимо подтвердить пароль.')
            
            # Проверяем совпадение паролей
            if password1 != password2:
                raise forms.ValidationError('Пароли не совпадают.')
            
            # Проверяем сложность пароля
            if len(password1) < 8:
                raise forms.ValidationError('Пароль должен содержать минимум 8 символов.')
            
            # Проверяем уникальность email
            if User.objects.filter(email=email).exists():
                raise forms.ValidationError('Пользователь с таким email уже существует.')
        
        return cleaned_data
    
    def save(self, commit=True, total_price=None):
        order = super().save(commit=False)
        if total_price is not None:
            order.total_price = total_price
        if self.cleaned_data.get('create_account'):
            # Создаем пользователя
            user = User.objects.create_user(
                username=self.cleaned_data['username'],
                email=self.cleaned_data['customer_email'],
                password=self.cleaned_data['password1'],
                first_name=self.cleaned_data['customer_name'].split()[0] if self.cleaned_data['customer_name'] else '',
                last_name=' '.join(self.cleaned_data['customer_name'].split()[1:]) if len(self.cleaned_data['customer_name'].split()) > 1 else ''
            )
            # Создаем профиль заказчика
            customer = Customer.objects.create(
                user=user,
                phone=self.cleaned_data['customer_phone']
            )
            # Связываем заказ с заказчиком
            order.customer = customer
        if commit:
            order.save()
        return order


class OrderQuestionnaireForm(forms.ModelForm):
    """Форма опросного листа заказа"""
    class Meta:
        model = OrderQuestionnaire
        fields = [
            'project_name', 'project_description', 'target_audience', 'competitors',
            'technical_requirements', 'design_preferences', 'functionality_requirements',
            'deadline', 'budget_range', 'additional_requirements',
            'preferred_contact_method', 'additional_contacts'
        ]
        widgets = {
            'project_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Название вашего проекта'
            }),
            'project_description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Подробное описание проекта, его цели и задачи'
            }),
            'target_audience': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Опишите целевую аудиторию вашего проекта'
            }),
            'competitors': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Укажите основных конкурентов или похожие проекты'
            }),
            'technical_requirements': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Технические требования к проекту (технологии, платформы, интеграции)'
            }),
            'design_preferences': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Ваши предпочтения по дизайну (стиль, цвета, примеры)'
            }),
            'functionality_requirements': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Требуемая функциональность проекта'
            }),
            'deadline': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
                'placeholder': 'Желаемый срок сдачи проекта'
            }),
            'budget_range': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Диапазон бюджета (например: 50,000 - 100,000 ₽)'
            }),
            'additional_requirements': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 5,
                'placeholder': 'Дополнительные требования, пожелания или особые условия'
            }),
            'preferred_contact_method': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Предпочтительный способ связи (телефон, email, мессенджер)'
            }),
            'additional_contacts': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Дополнительные контактные данные'
            }),
        }


class OrderFileForm(forms.ModelForm):
    """Форма загрузки файлов для заказа"""
    class Meta:
        model = OrderFile
        fields = ['file', 'description']
        widgets = {
            'file': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.doc,.docx,.jpg,.jpeg,.png,.gif,.zip,.rar'
            }),
            'description': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Описание файла (необязательно)'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Делаем поле файла необязательным
        self.fields['file'].required = False

    def clean_file(self):
        file = self.cleaned_data.get('file')
        if file:
            # Проверяем размер файла (максимум 10MB)
            if file.size > 10 * 1024 * 1024:
                raise forms.ValidationError('Размер файла не должен превышать 10MB')
            
            # Проверяем расширение файла
            allowed_extensions = ['.pdf', '.doc', '.docx', '.jpg', '.jpeg', '.png', '.gif', '.zip', '.rar']
            file_extension = '.' + file.name.split('.')[-1].lower()
            if file_extension not in allowed_extensions:
                raise forms.ValidationError('Недопустимый тип файла. Разрешены: PDF, DOC, DOCX, JPG, PNG, GIF, ZIP, RAR')
        
        return file


class CustomerRegistrationForm(UserCreationForm):
    """Форма регистрации заказчика"""
    first_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Имя *'
        })
    )
    last_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Фамилия *'
        })
    )
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Email *'
        })
    )
    phone = forms.CharField(
        max_length=20,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Телефон *'
        })
    )
    company = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Компания (необязательно)'
        })
    )
    position = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Должность (необязательно)'
        })
    )
    address = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Адрес (необязательно)'
        })
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
            'username': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Логин *'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Пароль *'
        })
        self.fields['password2'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Подтвердите пароль *'
        })
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
            # Создаем профиль заказчика
            Customer.objects.create(
                user=user,
                phone=self.cleaned_data['phone'],
                company=self.cleaned_data.get('company', ''),
                position=self.cleaned_data.get('position', ''),
                address=self.cleaned_data.get('address', '')
            )
        return user


class CustomerLoginForm(AuthenticationForm):
    """Форма входа для заказчика"""
    username = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Логин или Email'
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Пароль'
        })
    )


class CustomerProfileForm(forms.ModelForm):
    """Форма редактирования профиля заказчика"""
    first_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Имя *'
        })
    )
    last_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Фамилия *'
        })
    )
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Email *'
        })
    )
    
    class Meta:
        model = Customer
        fields = ['first_name', 'last_name', 'email', 'phone', 'company', 'position', 'address']
        widgets = {
            'first_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Имя *'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Фамилия *'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'Email *'
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Телефон *'
            }),
            'company': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Компания'
            }),
            'position': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Должность'
            }),
            'address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Адрес'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if self.user:
            self.fields['first_name'].initial = self.user.first_name
            self.fields['last_name'].initial = self.user.last_name
            self.fields['email'].initial = self.user.email

    def clean_first_name(self):
        return validate_person_name(self.cleaned_data.get('first_name'), 'Имя')

    def clean_last_name(self):
        return validate_person_name(self.cleaned_data.get('last_name'), 'Фамилия')

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email:
            validate_registration_email_domain(email)
        return email

    def save(self, commit=True):
        customer = super().save(commit=False)
        if self.user:
            self.user.first_name = self.cleaned_data['first_name']
            self.user.last_name = self.cleaned_data['last_name']
            self.user.email = self.cleaned_data['email']
            self.user.save()
        if commit:
            customer.save()
        return customer


class OrderCommentForm(forms.ModelForm):
    """Форма комментария к заказу"""
    class Meta:
        model = OrderComment
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Ваш комментарий...'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        self.order = kwargs.pop('order', None)
        self.is_admin = kwargs.pop('is_admin', False)
        super().__init__(*args, **kwargs)
    
    def save(self, commit=True):
        comment = super().save(commit=False)
        if self.user:
            comment.author = self.user
        if self.order:
            comment.order = self.order
        comment.is_admin_comment = self.is_admin
        if commit:
            comment.save()
        return comment


class LegalInfoForm(forms.ModelForm):
    """Форма для редактирования правовой информации"""
    class Meta:
        model = LegalInfo
        fields = [
            'company_name', 'company_full_name', 'inn', 'kpp', 'ogrn',
            'legal_address', 'actual_address',
            'phone', 'email', 'website',
            'bank_name', 'bank_account', 'correspondent_account', 'bik',
            'about_site', 'about_company', 'terms_of_use', 'privacy_policy',
            'contract_file', 'extract_file', 'certificate_file'
        ]
        widgets = {
            'company_name': forms.TextInput(attrs={'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent'}),
            'company_full_name': forms.TextInput(attrs={'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent'}),
            'inn': forms.TextInput(attrs={'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent'}),
            'kpp': forms.TextInput(attrs={'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent'}),
            'ogrn': forms.TextInput(attrs={'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent'}),
            'legal_address': forms.Textarea(attrs={'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent', 'rows': 2}),
            'actual_address': forms.Textarea(attrs={'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent', 'rows': 2}),
            'phone': forms.TextInput(attrs={'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent'}),
            'email': forms.EmailInput(attrs={'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent'}),
            'website': forms.URLInput(attrs={'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent'}),
            'bank_name': forms.TextInput(attrs={'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent'}),
            'bank_account': forms.TextInput(attrs={'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent'}),
            'correspondent_account': forms.TextInput(attrs={'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent'}),
            'bik': forms.TextInput(attrs={'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent'}),
            'about_site': forms.Textarea(attrs={'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent', 'rows': 5}),
            'about_company': forms.Textarea(attrs={'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent', 'rows': 5}),
            'terms_of_use': forms.Textarea(attrs={'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent', 'rows': 5}),
            'privacy_policy': forms.Textarea(attrs={'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent', 'rows': 10}),
            'contract_file': forms.FileInput(attrs={'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent'}),
            'extract_file': forms.FileInput(attrs={'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent'}),
            'certificate_file': forms.FileInput(attrs={'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent'}),
        }

class RabotaForm(forms.ModelForm):
    """Форма для создания и редактирования работ в портфолио (Дашборд)"""
    class Meta:
        model = Rabota
        fields = [
            'name', 'category', 'status', 'image', 'adres', 'body', 
            'technologies', 'history_text', 'resources_text', 
            'parameters_text', 'instructions_text', 'tariffs_text', 
            'featured', 'order'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Название проекта'}),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'adres': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://example.com'}),
            'body': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Краткое описание'}),
            'technologies': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Например: Python, Django, Tailwind CSS'}),
            'featured': forms.CheckboxInput(attrs={'class': 'form-checkbox h-4 w-4 text-primary-600 border-gray-300 rounded'}),
            'order': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
        }
