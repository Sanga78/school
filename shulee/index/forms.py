from typing import Any
from django import forms
from django.forms import ChoiceField
from .models import AcademicYear, Bursar, CustomUser, Expense, FeePayment, LeaveRequest, Notification,SessionYearModel, Staff, StaffSubjectAssignment, Student, Subject,SubjectResult,Class
from django.apps import apps
from django.core.validators import FileExtensionValidator
from django.contrib.auth import get_user_model
User = get_user_model()

class ChoiceNoValidation(ChoiceField):
    def validate(self, value):
        pass
    
class DateInput(forms.DateInput):
    input_type = "date"

class EditStudentForm(forms.Form):
    email = forms.EmailField(label="Email",max_length=50,widget=forms.EmailInput(attrs={"class":"form-control"}))
    first_name = forms.CharField(label="First Name",max_length=50,widget=forms.TextInput(attrs={"class":"form-control"}))
    last_name = forms.CharField(label="Last Name",max_length=50,widget=forms.TextInput(attrs={"class":"form-control"}))
    username = forms.CharField(label="Username",max_length=50,widget=forms.TextInput(attrs={"class":"form-control"}))
    address = forms.CharField(label="Address",max_length=50,widget=forms.TextInput(attrs={"class":"form-control"}))
 
    gender_choices=(
        ("Male","Male"),
        ("Female","Female")
    )

    sex = forms.ChoiceField(label="Sex",choices=gender_choices,widget=forms.Select(attrs={"class":"form-control"}))
    session_year_id = forms.ChoiceField(label="Sesssion Year", widget=forms.Select(attrs={"class": "form-control"}))
    profile_pic = forms.FileField(label="Profile Picture",max_length=50,widget=forms.FileInput(attrs={"class":"form-control"}),required=False) 
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        SessionYearModel = apps.get_model('index', 'SessionYearModel')

        session_list = [(session.id, str(session.session_start_year) + " TO " + str(session.session_end_year)) for session in SessionYearModel.object.all()]

        self.fields['session_year_id'].choices = session_list

class EditResultForm(forms.Form):
    def __init__(self,*args,**kwargs):
        self.staff_id=kwargs.pop("staff_id")
        super(EditResultForm,self).__init__(*args,**kwargs)
        subject_list=[]
        try:
            subjects=Subject.objects.filter(staff_id=self.staff_id)
            for subject in subjects:
                subject_single=(subject.id,subject.subject_name)
                subject_list.append(subject_single)
        except:
            subject_list=[]
        self.fields['subject_id'].choices=subject_list

    session_list=[]
    try:
        sessions=SessionYearModel.object.all()
        for session in sessions:
            session_single=(session.id,str(session.session_start_year)+" TO "+str(session.session_end_year))
            session_list.append(session_single)
    except:
        session_list=[]

    subject_id=forms.ChoiceField(label="Subject",widget=forms.Select(attrs={"class":"form-control"}))
    session_id=forms.ChoiceField(label="Session Year",choices=session_list,widget=forms.Select(attrs={"class":"form-control"}))
    student_id=ChoiceNoValidation(label="Student",widget=forms.Select(attrs={"class":"form-control"}))
    assignment_marks=forms.CharField(label="Assignment Marks",widget=forms.TextInput(attrs={"class":"form-control"}))
    exam_marks=forms.CharField(label="Exam Marks",widget=forms.TextInput(attrs={"class":"form-control"}))

class FeePaymentForm(forms.ModelForm):
    class Meta:
        model = FeePayment
        fields = ['amount', 'payment_date', 'payment_method', 'transaction_code', 'notes']
        widgets = {
            'payment_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control'}),
            'payment_method': forms.Select(attrs={'class': 'form-control'}),
            'transaction_code': forms.TextInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

class ResultUploadForm(forms.Form):
    TERM_CHOICES = (
        ('Term 1', 'Term 1'),
        ('Term 2', 'Term 2'),
        ('Term 3', 'Term 3'),
    )
    
    term = forms.ChoiceField(choices=TERM_CHOICES)




class ClassTeacherAssignmentForm(forms.ModelForm):
    class Meta:
        model = Class
        fields = ['name', 'class_teacher']
        widgets = {
            'name': forms.Select(attrs={'class': 'form-control'}),
            'class_teacher': forms.Select(attrs={'class': 'form-control'}),
        }

class ExpenseForm(forms.ModelForm):
    class Meta:
        model = Expense
        fields = ['amount', 'category', 'description', 'date', 'receipt_number']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 3}),
        }
        
class ClassForm(forms.ModelForm):
    class Meta:
        model = Class
        fields = ['name', 'academic_year', 'class_teacher']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'E.g., Form 1, Grade 5, etc.'
            }),
            'academic_year': forms.Select(attrs={
                'class': 'form-select'
            }),
            'class_teacher': forms.Select(attrs={
                'class': 'form-select'
            }),
        }
        labels = {
            'name': 'Class Name',
            'academic_year': 'Academic Year',
            'class_teacher': 'Class Teacher'
        }
        help_texts = {
            'name': 'Enter the name of the class (e.g., Grade 1, Grade 9)',
            'class_teacher': 'Select the teacher responsible for this class'
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)       
        # Only show active academic years
        self.fields['academic_year'].queryset = AcademicYear.objects.filter(is_current=True)        
        # Only show teachers (staff with user_type=2)
        self.fields['class_teacher'].queryset = Staff.objects.filter(
            user__user_type=2
        ).select_related('user')        
        # Add empty label for dropdowns
        self.fields['academic_year'].empty_label = 'Select Academic Year'
        self.fields['class_teacher'].empty_label = 'Select Class Teacher'
    def clean_name(self):
        name = self.cleaned_data.get('name')
        academic_year = self.cleaned_data.get('academic_year')       
        # Check if class with this name already exists in the same academic year
        if Class.objects.filter(
            name__iexact=name, 
            academic_year=academic_year
        ).exclude(pk=self.instance.pk if self.instance else None).exists():
            raise forms.ValidationError(
                'A class with this name already exists for the selected academic year.'
            )        
        return name


class SystemSettingsForm(forms.Form):
    school_name = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter school name'
        }),
        label="School Name",
        required=True
    )
    
    logo = forms.ImageField(
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': 'image/*'
        }),
        label="School Logo",
        required=False,
        validators=[FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png', 'gif'])]
    )
    
    address = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Enter school physical address'
        }),
        label="School Address",
        required=False
    )
    
    contact_email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter official school email'
        }),
        label="Contact Email",
        required=False
    )
    
    contact_phone = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter school phone number'
        }),
        label="Contact Phone",
        required=False
    )
    
    website = forms.URLField(
        widget=forms.URLInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter school website URL'
        }),
        label="Website",
        required=False
    )
    
    def clean_logo(self):
        logo = self.cleaned_data.get('logo')
        if logo and logo.size > 2*1024*1024: 
            raise forms.ValidationError("Logo image too large (max 2MB)")
        return logo

class LeaveResponseForm(forms.ModelForm):
    notes = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Enter any additional notes for the applicant'
        }),
        required=False,
        label="Response Notes"
    )
    
    class Meta:
        model = LeaveRequest
        fields = ['status', 'notes']
        widgets = {
            'status': forms.Select(attrs={
                'class': 'form-select',
                'onchange': 'toggleNotesField(this)'
            }),
        }
        labels = {
            'status': 'Decision'
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Customize status choices (you can modify this based on your needs)
        self.fields['status'].choices = [
            (0, 'Pending'),
            (1, 'Approve'),
            (2, 'Reject')
        ]
        
        # Add custom classes based on status
        if self.instance and self.instance.status:
            self.fields['status'].initial = self.instance.status
    
    def clean(self):
        cleaned_data = super().clean()
        status = cleaned_data.get('status')
        notes = cleaned_data.get('notes')
        
        if status == 2 and not notes:  # If rejected, require notes
            self.add_error('notes', 'Please provide a reason for rejection')
        
        return cleaned_data

class AddSubjectForm(forms.ModelForm):
    class Meta:
        model = Subject
        fields = ['name', 'code', 'description']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'E.g., Mathematics, Biology'
            }),
            'code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'E.g., MATH101, BIO201'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Subject description (optional)'
            }),
        }
        labels = {
            'code': 'Subject Code'
        }

    def clean_code(self):
        code = self.cleaned_data.get('code')
        if Subject.objects.filter(code__iexact=code).exists():
            raise forms.ValidationError("A subject with this code already exists.")
        return code.upper()

class AddStudentForm(forms.ModelForm):
    # Fields from CustomUser
    first_name = forms.CharField(max_length=50)
    last_name = forms.CharField(max_length=50)
    email = forms.EmailField()
    phone = forms.CharField(max_length=20, required=False)
    address = forms.CharField(widget=forms.Textarea(attrs={'rows': 2}), required=False)
    profile_pic = forms.ImageField(required=False)

    class Meta:
        model = Student
        fields = [
            'admission_number', 'gender', 'date_of_birth',
            'current_class', 'academic_year',
            'father_name', 'mother_name',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Check if editing (instance exists)
        self.user_instance = getattr(self.instance, 'user', None)

        # Populate initial values for user fields if editing
        if self.user_instance:
            self.fields['first_name'].initial = self.user_instance.first_name
            self.fields['last_name'].initial = self.user_instance.last_name
            self.fields['email'].initial = self.user_instance.email
            self.fields['phone'].initial = self.user_instance.phone
            self.fields['address'].initial = self.user_instance.address
            self.fields['profile_pic'].initial = self.user_instance.profile_pic

        # Limit class/year querysets
        self.fields['current_class'].queryset = Class.objects.all()
        self.fields['academic_year'].queryset = AcademicYear.objects.all()

        # Set date input
        self.fields['date_of_birth'].widget.attrs.update({'type': 'date'})

    def clean_admission_number(self):
        admission_number = self.cleaned_data['admission_number']
        qs = Student.objects.filter(admission_number=admission_number)

        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)

        if qs.exists():
            raise forms.ValidationError("This admission number already exists.")
        return admission_number

    def clean(self):
        cleaned_data = super().clean()
        admission_number = cleaned_data.get('admission_number')

        if not admission_number:
            return

        username_conflict = CustomUser.objects.filter(username=admission_number)
        if self.user_instance:
            username_conflict = username_conflict.exclude(pk=self.user_instance.pk)

        if username_conflict.exists():
            self.add_error('admission_number', "This admission number is already used as a username.")
        return cleaned_data

    def save(self, commit=True):
        student = super().save(commit=False)

        # New user
        if not self.user_instance:
            user = CustomUser.objects.create_user(
                username=self.cleaned_data['admission_number'],
                password='default1234',
                email=self.cleaned_data['email'],
                first_name=self.cleaned_data['first_name'],
                last_name=self.cleaned_data['last_name'],
                user_type=3
            )
        else:
            user = self.user_instance
            user.first_name = self.cleaned_data['first_name']
            user.last_name = self.cleaned_data['last_name']
            user.email = self.cleaned_data['email']

        # Common user fields
        user.phone = self.cleaned_data.get('phone', '')
        user.address = self.cleaned_data.get('address', '')
        profile_pic = self.cleaned_data.get('profile_pic')
        if profile_pic:
            user.profile_pic = profile_pic

        if commit:
            user.save()
            student.user = user
            student.save()

        return student
# Teacher Management Forms
class StaffForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        required=False,
        label="Password"
    )
    
    qualification = forms.CharField(
        max_length=100, 
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    
    date_of_joining = forms.DateField(
        widget=DateInput(attrs={'class': 'form-control'}),
        required=False
    )

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'username', 'profile_pic', 'phone', 'address']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'profile_pic': forms.FileInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password'].required = not self.instance.pk

    def save(self, commit=True):
        user = super().save(commit=False)
        if self.cleaned_data['password']:
            user.set_password(self.cleaned_data['password'])
        user.user_type = 2  # Staff user type
        
        if commit:
            user.save()
            staff, created = Staff.objects.get_or_create(user=user)
            staff.qualification = self.cleaned_data.get('qualification', '')
            staff.date_of_joining = self.cleaned_data.get('date_of_joining')
            staff.save()
        return user

class StaffSubjectAssignmentForm(forms.ModelForm):
    class Meta:
        model = StaffSubjectAssignment
        fields = ['subject', 'classes', 'academic_year']
        widgets = {
            'subject': forms.Select(attrs={'class': 'form-select'}),
            'classes': forms.SelectMultiple(attrs={'class': 'form-select'}),
            'academic_year': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        staff = kwargs.pop('staff', None)
        super().__init__(*args, **kwargs)
        if staff:
            self.fields['classes'].queryset = Class.objects.filter(
                academic_year__is_current=True
            )

class AddAdministratorForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        label="Temporary Password"
    )
    
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'phone', 'profile_pic']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'profile_pic': forms.FileInput(attrs={'class': 'form-control'}),
        }

class AddBursarForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        required=False,
        label="Password"
    )
    
    GENDER_CHOICES = [
        ('M', 'Male'),
        ('F', 'Female'),
        ('O', 'Other'),
    ]
    
    gender = forms.ChoiceField(
        choices=GENDER_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    qualification = forms.CharField(
        max_length=100, 
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    
    date_of_joining = forms.DateField(
        widget=DateInput(attrs={'class': 'form-control'}),
        required=False
    )

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'username', 'profile_pic', 'phone', 'address']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'profile_pic': forms.FileInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password'].required = not self.instance.pk
        if self.instance.pk:
            try:
                bursar = self.instance.bursar_profile
                self.fields['gender'].initial = bursar.gender
                self.fields['qualification'].initial = bursar.qualification
                self.fields['date_of_joining'].initial = bursar.date_of_joining
            except Bursar.DoesNotExist:
                pass

    def save(self, commit=True):
        user = super().save(commit=False)
        if self.cleaned_data['password']:
            user.set_password(self.cleaned_data['password'])
        user.user_type = 4  # Bursar user type
        
        if commit:
            user.save()
            bursar, created = Bursar.objects.get_or_create(user=user)
            bursar.gender = self.cleaned_data['gender']
            bursar.qualification = self.cleaned_data['qualification']
            bursar.date_of_joining = self.cleaned_data['date_of_joining']
            bursar.save()
        return user

class NotificationForm(forms.ModelForm):
    recipients = forms.ModelMultipleChoiceField(
        queryset=CustomUser.objects.all(),
        widget=forms.SelectMultiple(attrs={'class': 'form-select'}),
        required=True
    )
    
    class Meta:
        model = Notification
        fields = ['title', 'message', 'recipients', 'priority']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter notification title'
            }),
            'message': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Enter your message here...'
            }),
            'priority': forms.Select(attrs={
                'class': 'form-select'
            }),
        }
        labels = {
            'priority': 'Priority Level'
        }