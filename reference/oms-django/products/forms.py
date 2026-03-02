from django import forms
from .models import Product, PricePolicy, Category
import json


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name', 'icon', 'display_order', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'toss-input w-100'}),
            'icon': forms.TextInput(attrs={'class': 'toss-input w-100', 'placeholder': 'bi-grid'}),
            'display_order': forms.NumberInput(attrs={'class': 'toss-input w-100', 'min': 0}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class ProductForm(forms.ModelForm):
    schema_text = forms.CharField(
        widget=forms.HiddenInput(),
        required=False,
        label='입력 스키마',
    )

    class Meta:
        model = Product
        fields = ['category', 'name', 'description', 'cost_price', 'base_price', 'reduction_rate', 'min_work_days', 'max_work_days', 'is_active']
        widgets = {
            'category': forms.Select(attrs={'class': 'toss-select w-100'}),
            'name': forms.TextInput(attrs={'class': 'toss-input w-100'}),
            'description': forms.Textarea(attrs={'class': 'toss-input w-100', 'rows': 3}),
            'cost_price': forms.NumberInput(attrs={'class': 'toss-input w-100'}),
            'base_price': forms.NumberInput(attrs={'class': 'toss-input w-100'}),
            'reduction_rate': forms.NumberInput(attrs={'class': 'toss-input w-100', 'min': 0, 'max': 100, 'placeholder': '예: 30'}),
            'min_work_days': forms.NumberInput(attrs={'class': 'toss-input w-100', 'min': 1}),
            'max_work_days': forms.NumberInput(attrs={'class': 'toss-input w-100', 'min': 1}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['schema_text'].initial = json.dumps(self.instance.schema, ensure_ascii=False)

    def save(self, commit=True):
        product = super().save(commit=False)
        schema_text = self.cleaned_data.get('schema_text', '[]')
        try:
            product.schema = json.loads(schema_text) if schema_text else []
        except json.JSONDecodeError:
            product.schema = []
        if commit:
            product.save()
        return product


class PricePolicyForm(forms.ModelForm):
    class Meta:
        model = PricePolicy
        fields = ['product', 'user', 'price']
        widgets = {
            'product': forms.Select(attrs={'class': 'toss-select w-100'}),
            'user': forms.Select(attrs={'class': 'toss-select w-100'}),
            'price': forms.NumberInput(attrs={'class': 'toss-input w-100'}),
        }
