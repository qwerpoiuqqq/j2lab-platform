import json
from django import forms
from django.contrib.auth.forms import AuthenticationForm

from .models import User

# 역할별 상위 역할 매핑: 해당 역할의 parent는 반드시 이 역할이어야 함
ROLE_PARENT_MAP = {
    'admin': None,          # 총관리자는 상위 없음
    'accountant': 'admin',  # 경리 → 총관리자 소속
    'manager': 'admin',     # 책임자 → 총관리자 소속
    'agency': 'manager',    # 대행사 → 책임자 소속
    'seller': 'agency',     # 셀러 → 대행사 소속
}


class LoginForm(AuthenticationForm):
    username = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'toss-input w-100',
            'placeholder': '아이디를 입력하세요',
        }),
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'toss-input w-100',
            'placeholder': '비밀번호를 입력하세요',
        }),
    )


class UserForm(forms.ModelForm):
    password1 = forms.CharField(
        label='비밀번호',
        widget=forms.PasswordInput(attrs={'class': 'toss-input w-100'}),
        required=False,
    )

    class Meta:
        model = User
        fields = ['username', 'company_name', 'first_name', 'phone', 'role', 'parent', 'is_active']
        labels = {
            'username': '아이디',
            'first_name': '이름/직급',
            'parent': '담당자 (소속)',
        }
        help_texts = {
            'phone': '연락 가능한 담당자 번호 작성 해주세요 *진행 누락 시 다이렉트 넘버',
        }
        widgets = {
            'username': forms.TextInput(attrs={'class': 'toss-input w-100'}),
            'company_name': forms.TextInput(attrs={'class': 'toss-input w-100'}),
            'first_name': forms.TextInput(attrs={'class': 'toss-input w-100'}),
            'phone': forms.TextInput(attrs={'class': 'toss-input w-100', 'placeholder': '연락 가능한 번호'}),
            'role': forms.Select(attrs={'class': 'toss-select w-100', 'id': 'id_role'}),
            'parent': forms.Select(attrs={'class': 'toss-select w-100', 'id': 'id_parent'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        self.request_user = kwargs.pop('request_user', None)
        super().__init__(*args, **kwargs)
        self.order_fields(['username', 'password1', 'company_name', 'first_name', 'phone', 'role', 'parent', 'is_active'])

        if self.request_user:
            if self.request_user.is_manager:
                self.fields['role'].choices = [('agency', '대행사')]
                self.fields.pop('parent')
            elif self.request_user.is_agency:
                self.fields['role'].choices = [('seller', '셀러')]
                self.fields.pop('parent')
            elif self.request_user.is_admin or self.request_user.is_accountant:
                self.fields['role'].choices = [
                    ('', '선택하세요'),
                    ('accountant', '경리'),
                    ('manager', '책임자'),
                    ('agency', '대행사'),
                    ('seller', '셀러'),
                ]

        # parent 필드: 역할별로 분리된 선택지 준비
        if 'parent' in self.fields:
            self.fields['parent'].required = False
            role_labels = dict(User.Role.choices)
            users = User.objects.filter(is_active=True).order_by('company_name', 'username')

            # 역할별 유저 목록 (JS에서 동적 필터링에 사용)
            self._parent_data = {}
            for role_key in ['admin', 'manager', 'agency']:
                self._parent_data[role_key] = [
                    {'id': u.pk, 'label': u.company_name or u.username}
                    for u in users if u.role == role_key
                ]

            # 초기 선택지: 전체를 그룹으로 표시
            grouped = {r: [] for r in ['admin', 'manager', 'agency']}
            for u in users:
                if u.role in grouped:
                    label = u.company_name or u.username
                    grouped[u.role].append((u.pk, label))
            choices = [('', '-- 역할을 먼저 선택하세요 --')]
            for role_key in ['admin', 'manager', 'agency']:
                if grouped[role_key]:
                    choices.append((role_labels.get(role_key, role_key), grouped[role_key]))
            self.fields['parent'].choices = choices

        if self.instance and self.instance.pk:
            self.fields['password1'].help_text = '변경시에만 입력'
            self.fields['username'].disabled = True

    def get_parent_json(self):
        """템플릿에서 JS로 넘길 역할별 상위 유저 데이터"""
        raw = json.dumps(getattr(self, '_parent_data', {}), ensure_ascii=False)
        return raw.replace('&', '\\u0026').replace('<', '\\u003c').replace('>', '\\u003e')

    def clean_password1(self):
        password = self.cleaned_data.get('password1')
        if not self.instance.pk and not password:
            raise forms.ValidationError('신규 계정은 비밀번호를 반드시 입력해야 합니다.')
        return password

    def clean(self):
        cleaned_data = super().clean()
        role = cleaned_data.get('role')
        parent = cleaned_data.get('parent')

        if 'parent' not in self.fields:
            return cleaned_data

        required_parent_role = ROLE_PARENT_MAP.get(role)

        if role == 'admin':
            cleaned_data['parent'] = None
        elif required_parent_role:
            if not parent:
                self.add_error('parent', '담당자(소속)를 반드시 선택해야 합니다.')
            elif parent.role != required_parent_role:
                expected = dict(User.Role.choices).get(required_parent_role, required_parent_role)
                self.add_error('parent', f'{dict(User.Role.choices).get(role)}의 담당자는 {expected}여야 합니다.')

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        pw = self.cleaned_data.get('password1')
        if pw:
            user.set_password(pw)
        if self.request_user and not self.instance.pk:
            if self.request_user.is_manager:
                user.parent = self.request_user
                user.role = User.Role.AGENCY
            elif self.request_user.is_agency:
                user.parent = self.request_user
                user.role = User.Role.SELLER
        if commit:
            user.save()
        return user
