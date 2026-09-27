from django import forms

from .models import Department, EmployeeProfile, InternalRole


class EmployeeCreateForm(forms.Form):
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150)
    email = forms.EmailField()
    employee_id = forms.CharField(max_length=32, help_text="Unique internal identifier, for example LP-00124.")
    title = forms.CharField(max_length=120, required=False)
    department = forms.ModelChoiceField(queryset=Department.objects.none(), required=False)
    role = forms.ModelChoiceField(queryset=InternalRole.objects.none(), required=False)
    manager = forms.ModelChoiceField(queryset=EmployeeProfile.objects.none(), required=False)
    hire_date = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["department"].queryset = Department.objects.filter(is_active=True).order_by("name")
        self.fields["role"].queryset = InternalRole.objects.filter(is_active=True).select_related("department").order_by("department__name", "name")
        self.fields["manager"].queryset = EmployeeProfile.objects.filter(status=EmployeeProfile.Status.ACTIVE).select_related("user").order_by("user__last_name", "user__first_name", "user__email")
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "emp-field")

    def clean_employee_id(self):
        value = self.cleaned_data["employee_id"].strip().upper()
        if EmployeeProfile.objects.filter(employee_id__iexact=value).exists():
            raise forms.ValidationError("That employee ID is already in use.")
        return value

    def clean(self):
        cleaned = super().clean()
        department = cleaned.get("department")
        role = cleaned.get("role")
        if role and role.department_id and role.department_id != getattr(department, "pk", None):
            self.add_error("role", "This role belongs to a different department.")
        return cleaned


class EmployeeUpdateForm(forms.Form):
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150)
    title = forms.CharField(max_length=120, required=False)
    department = forms.ModelChoiceField(queryset=Department.objects.none(), required=False)
    role = forms.ModelChoiceField(queryset=InternalRole.objects.none(), required=False)
    manager = forms.ModelChoiceField(queryset=EmployeeProfile.objects.none(), required=False)
    status = forms.ChoiceField(choices=EmployeeProfile.Status.choices)
    hire_date = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    reason = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), help_text="Required for the employee audit trail.")

    def __init__(self, *args, employee=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.employee = employee
        self.fields["department"].queryset = Department.objects.filter(is_active=True).order_by("name")
        self.fields["role"].queryset = InternalRole.objects.filter(is_active=True).select_related("department").order_by("department__name", "name")
        managers = EmployeeProfile.objects.filter(status=EmployeeProfile.Status.ACTIVE).select_related("user")
        if employee:
            managers = managers.exclude(pk=employee.pk)
        self.fields["manager"].queryset = managers.order_by("user__last_name", "user__first_name", "user__email")
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "emp-field")

    def clean(self):
        cleaned = super().clean()
        department = cleaned.get("department")
        role = cleaned.get("role")
        if role and role.department_id and role.department_id != getattr(department, "pk", None):
            self.add_error("role", "This role belongs to a different department.")
        return cleaned
