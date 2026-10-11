from django.utils import timezone
from django import forms
from django.forms import ChoiceField
from .models import next_admission_number, AcademicYear, Bursar, CustomUser, Expense, FeePayment, FeeStructure, FoodContribution, FoodRequirement, GovernmentGrant, LeaveRequest, Notification, SchoolEvent, SchoolProfile, UniformItem, SessionYearModel, Staff, StaffSubjectAssignment, Student, Subject,SubjectResult,StudentClass
from django.contrib.auth import get_user_model, password_validation
from django.core.exceptions import ValidationError
from django.forms import PasswordInput 
from django.db import transaction # Import transaction for atomic operations
from django.core.files.uploadedfile import InMemoryUploadedFile
from PIL import Image, UnidentifiedImageError
from io import BytesIO
from uuid import uuid4
from .validators import validate_kenyan_birth_certificate

User = get_user_model()


class AdminSignupForm(forms.Form):
    username = forms.CharField(max_length=150)
    email = forms.EmailField()
    password = forms.CharField(strip=False, widget=forms.PasswordInput)

    def clean_username(self):
        username = self.cleaned_data['username']
        if CustomUser.objects.filter(username__iexact=username).exists():
            raise ValidationError('A user with that username already exists.')
        return username

    def clean_password(self):
        password = self.cleaned_data['password']
        password_validation.validate_password(password)
        return password


class StudentSignupForm(forms.Form):
    MAX_PROFILE_IMAGE_BYTES = 5 * 1024 * 1024
    MAX_PROFILE_IMAGE_DIMENSION = 4096
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150)
    username = forms.CharField(max_length=150, required=False)
    parent_email = forms.EmailField()
    address = forms.CharField(required=False, max_length=500)
    academic_year = forms.ModelChoiceField(
        queryset=AcademicYear.objects.filter(is_current=True),
    )
    current_class = forms.ModelChoiceField(
        queryset=StudentClass.objects.filter(academic_year__is_current=True),
    )
    gender = forms.ChoiceField(choices=Student.GENDER_CHOICES)
    MIN_AGE = 5
    MAX_AGE = 18
    date_of_birth = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    birth_certificate_number = forms.CharField(
        max_length=50,
        required=False,
        validators=[validate_kenyan_birth_certificate],
        help_text="Kenyan birth certificate format: XXXXX-XXXXX-XXXXX"
    )
    password = forms.CharField(strip=False, widget=forms.PasswordInput)
    profile_pic = forms.ImageField(required=False)

    def clean_username(self):
        username = self.cleaned_data['username']
        if not username:
            return username
        if CustomUser.objects.filter(username__iexact=username).exists():
            raise ValidationError('A user with that username already exists.')
        return username

    def clean_date_of_birth(self):
        born = self.cleaned_data['date_of_birth']
        today = timezone.localdate()
        age = today.year - born.year - ((today.month, today.day) < (born.month, born.day))
        if born > today:
            raise ValidationError('Date of birth cannot be in the future.')
        if age < self.MIN_AGE:
            raise ValidationError(f'The applicant is too young. The minimum age is {self.MIN_AGE} years.')
        if age > self.MAX_AGE:
            raise ValidationError(f'The applicant is too old. The maximum age is {self.MAX_AGE} years.')
        return born

    def clean_password(self):
        password = self.cleaned_data['password']
        user = CustomUser(username=self.cleaned_data.get('username', ''))
        password_validation.validate_password(password, user=user)
        return password

    def clean_profile_pic(self):
        upload = self.cleaned_data.get('profile_pic')
        if upload is None:
            return None
        if upload.size > self.MAX_PROFILE_IMAGE_BYTES:
            raise ValidationError('Profile images must be no larger than 5 MB.')

        try:
            image = Image.open(upload)
            image_format = image.format
            width, height = image.size
            if image_format not in {'JPEG', 'PNG', 'WEBP'}:
                raise ValidationError('Upload a JPEG, PNG, or WebP image.')
            if width > self.MAX_PROFILE_IMAGE_DIMENSION or height > self.MAX_PROFILE_IMAGE_DIMENSION:
                raise ValidationError('Profile images must be no larger than 4096 by 4096 pixels.')
            image.verify()
            upload.seek(0)
            image = Image.open(upload)
            image.load()
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as error:
            raise ValidationError('The uploaded profile image is invalid.') from error

        if image.mode in {'RGBA', 'LA'} or 'transparency' in image.info:
            rgba_image = image.convert('RGBA')
            background = Image.new('RGB', rgba_image.size, 'white')
            background.paste(rgba_image, mask=rgba_image.getchannel('A'))
            image = background
        else:
            image = image.convert('RGB')

        encoded_image = BytesIO()
        image.save(encoded_image, format='JPEG', quality=85, optimize=True)
        if encoded_image.tell() > self.MAX_PROFILE_IMAGE_BYTES:
            raise ValidationError('The processed profile image exceeds the 5 MB limit.')
        encoded_image.seek(0)
        return InMemoryUploadedFile(
            encoded_image,
            field_name='profile_pic',
            name=f'{uuid4().hex}.jpg',
            content_type='image/jpeg',
            size=encoded_image.getbuffer().nbytes,
            charset=None,
        )

    def clean(self):
        cleaned_data = super().clean()
        academic_year = cleaned_data.get('academic_year')
        current_class = cleaned_data.get('current_class')
        if academic_year and current_class and current_class.academic_year_id != academic_year.pk:
            self.add_error('current_class', 'Choose a class in the selected academic year.')
        return cleaned_data


class StudentProfileForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ['first_name', 'last_name', 'phone', 'address']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'maxlength': 150}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'maxlength': 150}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'maxlength': 20}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'maxlength': 500}),
        }


class StudentApplicationReviewForm(forms.Form):
    action = forms.ChoiceField(choices=(
        ('schedule', 'Schedule interview'),
        ('approve', 'Approve application'),
        ('reject', 'Reject application'),
    ))
    interview_at = forms.DateTimeField(
        required=False,
        input_formats=['%Y-%m-%dT%H:%M'],
        widget=forms.DateTimeInput(
            attrs={'class': 'form-control', 'type': 'datetime-local'},
            format='%Y-%m-%dT%H:%M',
        ),
    )
    review_notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
    )

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('action') == 'schedule':
            interview_at = cleaned_data.get('interview_at')
            if not interview_at:
                self.add_error('interview_at', 'Choose an interview date and time.')
            elif interview_at <= timezone.now():
                self.add_error('interview_at', 'Choose a future interview date and time.')
        return cleaned_data


class ChoiceNoValidation(ChoiceField):
    def validate(self, value):
        pass
    
class DateInput(forms.DateInput):
    input_type = "date"
    
class StudentForm(forms.ModelForm):
    first_name = forms.CharField(
        max_length=150, 
        required=True, 
        widget=forms.TextInput(attrs={'class': 'form-control'}))
    last_name = forms.CharField(
        max_length=150, 
        required=True, 
        widget=forms.TextInput(attrs={'class': 'form-control'}))
    email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={'class': 'form-control'}),
        help_text="Optional, but recommended for communication purposes.")
    parent_email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'class': 'form-control'}),
        help_text="Required contact email for the student's parent or guardian.")
    username = forms.CharField(
        max_length=150, 
        required=False, 
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        help_text="Leave blank for new students: the next sequential admission number (1001, 1002, ...) is assigned automatically.",
        label="Admission Number")
    password = forms.CharField(
        widget=PasswordInput(attrs={'class': 'form-control'}),
        label="Password",
        strip=False, 
        help_text=("Your password must contain at least 8 characters. "
                   "Can't be entirely numeric."),
        required=False)
    confirm_password = forms.CharField(
        widget=PasswordInput(attrs={'class': 'form-control'}),
        label="Confirm Password",
        strip=False,
        help_text="Enter the same password as above, for verification.",
        required=False)

    class Meta:
        model = Student
        fields = [
            'gender', 'date_of_birth', 'current_class',
            'academic_year', 'father_name', 'mother_name', 'parent_email', 'is_boarder', 'active'
        ]
        widgets = {
            'is_boarder': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'gender': forms.Select(attrs={'class': 'form-control'}),
            'date_of_birth': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}), 
            'current_class': forms.Select(attrs={'class': 'form-control'}),
            'academic_year': forms.Select(attrs={'class': 'form-control'}),
            'father_name': forms.TextInput(attrs={'class': 'form-control'}),
            'mother_name': forms.TextInput(attrs={'class': 'form-control'}),
            'parent_email': forms.EmailInput(attrs={'class': 'form-control'}),
            'active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['password'].required = False
            self.fields['confirm_password'].required = False
        else:
            self.fields['password'].required = True
            self.fields['confirm_password'].required = True

    def clean_username(self):
        username = (self.cleaned_data.get('username') or '').strip()
        if self.instance and self.instance.pk:
            if not username:
                raise ValidationError("Admission number is required.")
            if Student.objects.filter(user__username=username).exclude(pk=self.instance.pk).exists():
                raise ValidationError("This username is already taken.")
        else:
            if not username:
                return next_admission_number()
            if CustomUser.objects.filter(username=username).exists():
                raise ValidationError("This username is already taken.")
        return username

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')

        if not self.instance.pk and not password:
            self.add_error('password', "Password is required for new students.")
        
        if password and confirm_password and password != confirm_password:
            self.add_error('confirm_password', "Passwords do not match.")
        
        return cleaned_data

    @transaction.atomic
    def save(self, commit=True):
        student = super().save(commit=False)
        user_data = {
            'first_name': self.cleaned_data['first_name'],
            'last_name': self.cleaned_data['last_name'],
            'email': self.cleaned_data.get('email', ''),
            'username': self.cleaned_data['username'],
            'user_type': 3,  # Student
        }

        if self.instance.pk:
            # Update existing student
            user = self.instance.user
            for attr, value in user_data.items():
                setattr(user, attr, value)
            
            if 'password' in self.cleaned_data and self.cleaned_data['password']:
                user.set_password(self.cleaned_data['password'])
            
            user.save()
            student.user = user
        else:
            # Create new student
            user = CustomUser.objects.create_user(
                password=self.cleaned_data['password'],
                **user_data
            )
            student = user.student_profile
            for field_name in self._meta.fields:
                setattr(student, field_name, getattr(self.instance, field_name))

        if commit:
            student.save()
        
        return student

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

class FeeStructureForm(forms.ModelForm):
    class Meta:
        model = FeeStructure
        fields = ['name', 'description', 'amount', 'class_obj', 'academic_year', 'category', 'term', 'applies_to', 'due_date', 'is_active']
        widgets = {
            'category': forms.Select(attrs={'class': 'form-select'}),
            'term': forms.Select(attrs={'class': 'form-select'}),
            'applies_to': forms.Select(attrs={'class': 'form-select'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'min': '0.01', 'step': '0.01'}),
            'class_obj': forms.Select(attrs={'class': 'form-select'}),
            'academic_year': forms.Select(attrs={'class': 'form-select'}),
            'due_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

class FoodRequirementForm(forms.ModelForm):
    class Meta:
        model = FoodRequirement
        fields = ['class_obj', 'academic_year', 'item', 'quantity_kg', 'cash_per_kg']
        widgets = {
            'class_obj': forms.Select(attrs={'class': 'form-select'}),
            'academic_year': forms.Select(attrs={'class': 'form-select'}),
            'item': forms.Select(attrs={'class': 'form-select'}),
            'quantity_kg': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0.01'}),
            'cash_per_kg': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0.01'}),
        }

    def clean(self):
        cleaned = super().clean()
        class_obj, year = cleaned.get('class_obj'), cleaned.get('academic_year')
        if class_obj and year and class_obj.academic_year_id != year.pk:
            self.add_error('academic_year', 'The class does not belong to this academic year.')
        return cleaned


class FoodContributionForm(forms.Form):
    requirement = forms.ModelChoiceField(
        queryset=FoodRequirement.objects.none(),
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    method = forms.ChoiceField(
        choices=FoodContribution.METHOD_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    quantity_kg = forms.DecimalField(
        required=False, min_value=0, max_digits=8, decimal_places=2,
        label='Quantity brought (kg)',
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
    )
    amount = forms.DecimalField(
        required=False, min_value=0, max_digits=10, decimal_places=2,
        label='Cash paid (Ksh)',
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
    )
    date = forms.DateField(initial=timezone.localdate, widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}))
    notes = forms.CharField(required=False, max_length=200, widget=forms.TextInput(attrs={'class': 'form-control'}))

    def __init__(self, *args, student=None, **kwargs):
        super().__init__(*args, **kwargs)
        if student is not None:
            self.fields['requirement'].queryset = student.get_food_requirements()

    def clean(self):
        cleaned = super().clean()
        method = cleaned.get('method')
        if method == 'IN_KIND' and not cleaned.get('quantity_kg'):
            self.add_error('quantity_kg', 'Enter the quantity of food brought, in kg.')
        if method == 'CASH' and not cleaned.get('amount'):
            self.add_error('amount', 'Enter the cash amount paid.')
        return cleaned


class GovernmentGrantForm(forms.ModelForm):
    class Meta:
        model = GovernmentGrant
        fields = ['source', 'description', 'amount', 'date', 'reference']
        widgets = {
            'source': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.TextInput(attrs={'class': 'form-control'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0.01'}),
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'reference': forms.TextInput(attrs={'class': 'form-control'}),
        }


class SchoolProfileForm(forms.ModelForm):
    class Meta:
        model = SchoolProfile
        fields = ['school_name', 'school_code', 'uniform_description']
        widgets = {
            'school_name': forms.TextInput(attrs={'class': 'form-control'}),
            'school_code': forms.TextInput(attrs={'class': 'form-control'}),
            'uniform_description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }


class UniformItemForm(forms.ModelForm):
    class Meta:
        model = UniformItem
        fields = ['name', 'description', 'image', 'order']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'image': forms.FileInput(attrs={'class': 'form-control'}),
            'order': forms.NumberInput(attrs={'class': 'form-control'}),
        }


class ResultUploadForm(forms.Form):
    term = forms.ChoiceField(
        choices=SubjectResult.TERM_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )


class TeacherProfileForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ['first_name', 'last_name', 'address']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'autocomplete': 'given-name'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'autocomplete': 'family-name'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'autocomplete': 'street-address'}),
        }



class ClassTeacherAssignmentForm(forms.ModelForm):
    class Meta:
        model = StudentClass
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
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'min': '0.01', 'step': '0.01'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'description': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'receipt_number': forms.TextInput(attrs={'class': 'form-control'}),
        }
        
class ClassForm(forms.ModelForm):
    class Meta:
        model = StudentClass
        fields = ['class_teacher']
        widgets = {
            'class_teacher': forms.Select(attrs={
                'class': 'form-select'
            }),
        }
        help_texts = {
            'class_teacher': 'Select the teacher responsible for this class'
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['class_teacher'].queryset = Staff.objects.filter(
            user__user_type=2
        ).select_related('user')
        self.fields['class_teacher'].empty_label = 'Select Class Teacher'

class SystemSettingsForm(forms.ModelForm):
    class Meta:
        model = SchoolProfile
        fields = [
            'school_name', 'logo', 'address', 'contact_email', 'contact_phone', 'website',
            'applications_open',
            'term_1_start', 'term_1_end', 'term_2_start', 'term_2_end', 'term_3_start', 'term_3_end',
        ]
        widgets = {
            'school_name': forms.TextInput(attrs={'class': 'form-control'}),
            'logo': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'contact_email': forms.EmailInput(attrs={'class': 'form-control'}),
            'contact_phone': forms.TextInput(attrs={'class': 'form-control'}),
            'website': forms.URLInput(attrs={'class': 'form-control'}),
            'applications_open': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            **{
                f'term_{n}_{edge}': forms.DateInput(
                    attrs={'type': 'date', 'class': 'form-control'}, format='%Y-%m-%d',
                )
                for n in (1, 2, 3) for edge in ('start', 'end')
            },
        }
        labels = {
            'school_name': 'School name',
            'logo': 'School logo',
            'contact_email': 'Contact email',
            'contact_phone': 'Contact phone',
            'applications_open': 'Accept online applications',
        }

    def clean_logo(self):
        logo = self.cleaned_data.get('logo')
        if logo and hasattr(logo, 'size'):
            if logo.size > 2 * 1024 * 1024:
                raise forms.ValidationError("Logo image too large (max 2MB)")
            name = logo.name.lower()
            if not name.endswith(('.jpg', '.jpeg', '.png', '.gif')):
                raise forms.ValidationError("Upload a JPG, PNG or GIF image.")
        return logo

    def clean(self):
        cleaned = super().clean()
        for n in (1, 2, 3):
            start, end = cleaned.get(f'term_{n}_start'), cleaned.get(f'term_{n}_end')
            if start and end and end < start:
                self.add_error(f'term_{n}_end', 'End date cannot be before the start date.')
        return cleaned

class LeaveResponseForm(forms.ModelForm):
    class Meta:
        model = LeaveRequest
        fields = ['status', 'review_notes']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-select'}),
            'review_notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Enter any additional notes for the applicant',
            }),
        }
        labels = {
            'status': 'Decision',
            'review_notes': 'Response Notes',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['status'].choices = [
            (0, 'Pending'),
            (1, 'Approve'),
            (2, 'Reject')
        ]
        self.fields['review_notes'].required = False

    def clean(self):
        cleaned_data = super().clean()
        status = cleaned_data.get('status')
        notes = cleaned_data.get('review_notes')

        if status == 2 and not notes:
            self.add_error('review_notes', 'Please provide a reason for rejection')

        return cleaned_data

# Teacher Management Forms
class StaffForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        required=False,
        label="Password"
    )

    role = forms.ChoiceField(
        choices=Staff.ROLE_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    employment_type = forms.ChoiceField(
        choices=Staff.EMPLOYMENT_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text='BOM staff are paid through school payroll; TSC staff are tracked for records only.',
    )
    monthly_salary = forms.DecimalField(
        required=False, min_value=0, max_digits=10, decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        help_text='Required for BOM staff.',
    )

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('employment_type') == 'BOM':
            salary = cleaned.get('monthly_salary')
            if not salary or salary <= 0:
                self.add_error('monthly_salary', 'Enter the agreed monthly salary for BOM staff.')
        elif cleaned.get('employment_type') == 'TSC':
            cleaned['monthly_salary'] = None
        return cleaned

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
            staff.date_of_joining = self.cleaned_data.get('date_of_joining') or staff.date_of_joining or timezone.localdate()
            staff.role = self.cleaned_data['role']
            staff.employment_type = self.cleaned_data['employment_type']
            staff.monthly_salary = self.cleaned_data.get('monthly_salary')
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
        current_year = AcademicYear.objects.filter(is_current=True).first()
        self.fields['academic_year'].queryset = (
            AcademicYear.objects.filter(pk=current_year.pk)
            if current_year else AcademicYear.objects.none()
        )
        if current_year:
            self.fields['academic_year'].initial = current_year
        if staff and current_year:
            self.fields['classes'].queryset = StudentClass.objects.filter(
                academic_year=current_year
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
            bursar.date_of_joining = self.cleaned_data['date_of_joining'] or timezone.localdate()
            bursar.save()
        return user

class EditBursarForm(AddBursarForm):
    is_active = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )

    def save(self, commit=True):
        if commit:
            self.instance.is_active = self.cleaned_data['is_active']
        return super().save(commit=commit)

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


class ClassEventForm(forms.ModelForm):
    """Class teacher's targeted event: the whole class or chosen students."""
    send_to = forms.ChoiceField(
        choices=[('all', 'All students in the class'), ('selected', 'Only the students I select')],
        initial='all',
        widget=forms.RadioSelect,
    )
    recipients = forms.ModelMultipleChoiceField(
        queryset=Student.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = SchoolEvent
        fields = ['title', 'description', 'starts_at', 'ends_at', 'location']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'maxlength': 200}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'starts_at': forms.DateTimeInput(
                format='%Y-%m-%dT%H:%M', attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'ends_at': forms.DateTimeInput(
                format='%Y-%m-%dT%H:%M', attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'location': forms.TextInput(attrs={'class': 'form-control', 'maxlength': 200}),
        }

    def __init__(self, *args, class_obj, **kwargs):
        super().__init__(*args, **kwargs)
        self.class_obj = class_obj
        self.fields['recipients'].queryset = Student.objects.filter(
            current_class=class_obj, active=True,
        ).select_related('user').order_by('user__last_name', 'user__first_name')
        self.fields['recipients'].label_from_instance = (
            lambda s: f'{s.user.get_full_name() or s.user.username} ({s.admission_number})'
        )

    def clean(self):
        cleaned = super().clean()
        starts_at, ends_at = cleaned.get('starts_at'), cleaned.get('ends_at')
        if starts_at and ends_at and ends_at < starts_at:
            self.add_error('ends_at', 'The end time must be after the start time.')
        if cleaned.get('send_to') == 'selected' and not cleaned.get('recipients'):
            self.add_error('recipients', 'Select at least one student.')
        return cleaned

    def save(self, commit=True):
        event = super().save(commit=False)
        event.audience_class = self.class_obj
        event.is_published = True
        if commit:
            event.save()
            event.recipients.set(
                self.cleaned_data['recipients'] if self.cleaned_data['send_to'] == 'selected' else []
            )
        return event


class SchoolEventForm(forms.ModelForm):
    class Meta:
        model = SchoolEvent
        fields = ['title', 'description', 'starts_at', 'ends_at', 'location', 'is_published']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'calendar-form__input',
                'autocomplete': 'off',
                'maxlength': 200,
            }),
            'description': forms.Textarea(attrs={
                'class': 'calendar-form__input',
                'rows': 4,
            }),
            'starts_at': forms.DateTimeInput(
                format='%Y-%m-%dT%H:%M',
                attrs={'class': 'calendar-form__input', 'type': 'datetime-local'},
            ),
            'ends_at': forms.DateTimeInput(
                format='%Y-%m-%dT%H:%M',
                attrs={'class': 'calendar-form__input', 'type': 'datetime-local'},
            ),
            'location': forms.TextInput(attrs={
                'class': 'calendar-form__input',
                'autocomplete': 'off',
                'maxlength': 200,
            }),
            'is_published': forms.CheckboxInput(attrs={'class': 'calendar-form__checkbox'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        starts_at = cleaned_data.get('starts_at')
        ends_at = cleaned_data.get('ends_at')
        if starts_at and ends_at and ends_at < starts_at:
            self.add_error('ends_at', 'The end time must be after the start time.')
        return cleaned_data
        labels = {
            'priority': 'Priority Level'
        }

# class StudentForm(forms.ModelForm):
#     first_name = forms.CharField(
#         max_length=150, 
#         required=True, 
#         widget=forms.TextInput(attrs={'class': 'form-control'})
#     )
#     last_name = forms.CharField(
#         max_length=150, 
#         required=True, 
#         widget=forms.TextInput(attrs={'class': 'form-control'})
#     )
#     email = forms.EmailField(
#         required=False,
#         widget=forms.EmailInput(attrs={'class': 'form-control'}),
#         help_text="Optional, but recommended for user communication."
#     )
#     username = forms.CharField(
#         max_length=150, 
#         required=True, 
#         widget=forms.TextInput(attrs={'class': 'form-control'}),
#         help_text="Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only."
#     )
#     profile_pic = forms.ImageField(
#         required=False, 
#         widget=forms.FileInput(attrs={'class': 'form-control-file'}),
#         help_text="Optional. Upload a profile picture for the student."
#     )
#     phone = forms.CharField(
#         max_length=20, 
#         required=False, 
#         widget=forms.TextInput(attrs={'class': 'form-control'}),
#         help_text="Optional. Student's contact phone number."
#     )
#     address = forms.CharField(
#         widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}), 
#         required=False,
#         help_text="Optional. Student's residential address."
#     )
#     password = forms.CharField(
#         widget=PasswordInput(attrs={'class': 'form-control'}),
#         label="Password",
#         strip=False, 
#         help_text=("Your password must contain at least 8 characters. "
#                    "Can't be entirely numeric."),
#         required=False 
#     )
#     confirm_password = forms.CharField(
#         widget=PasswordInput(attrs={'class': 'form-control'}),
#         label="Confirm Password",
#         strip=False,
#         help_text="Enter the same password as above, for verification.",
#         required=False 
#     )
#     class Meta:
#         model = Student
#         fields = [
#             'admission_number', 'gender', 'date_of_birth',
#             'current_class', 'academic_year', 'father_name',
#             'mother_name', 'active'
#         ]     
#         widgets = {
#             'admission_number': forms.TextInput(attrs={'class': 'form-control'}),
#             'gender': forms.Select(attrs={'class': 'form-control'}),
#             'date_of_birth': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}), 
#             'current_class': forms.Select(attrs={'class': 'form-control'}),
#             'academic_year': forms.Select(attrs={'class': 'form-control'}),
#             'father_name': forms.TextInput(attrs={'class': 'form-control'}),
#             'mother_name': forms.TextInput(attrs={'class': 'form-control'}),
#             'active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
#         }       
#         labels = {
#             'admission_number': 'Admission Number',
#             'gender': 'Gender',
#             'date_of_birth': 'Date of Birth',
#             'current_class': 'Current Class',
#             'academic_year': 'Academic Year',
#             'father_name': 'Father\'s Name',
#             'mother_name': 'Mother\'s Name',
#             'active': 'Is Active?',
#         }

#     def __init__(self, *args, **kwargs):
#         self.student_instance = kwargs.get('instance')
#         self.user_instance = self.student_instance.user if self.student_instance else None

#         super().__init__(*args, **kwargs)

#         if self.user_instance:
#             self.fields['first_name'].initial = self.user_instance.first_name
#             self.fields['last_name'].initial = self.user_instance.last_name
#             self.fields['email'].initial = self.user_instance.email
#             self.fields['username'].initial = self.user_instance.username
#             self.fields['profile_pic'].initial = self.user_instance.profile_pic
#             self.fields['phone'].initial = self.user_instance.phone
#             self.fields['address'].initial = self.user_instance.address

#             self.fields['password'].required = False
#             self.fields['password'].help_text = "Leave blank if you don't want to change the password."
#             self.fields['confirm_password'].required = False
#             self.fields['confirm_password'].help_text = "" 
#         else:
#             self.fields['password'].required = True
#             self.fields['confirm_password'].required = True
            
#         for field_name, field in self.fields.items():
#             if isinstance(field.widget, (forms.TextInput, forms.EmailInput, 
#                                         forms.Textarea, forms.DateInput, 
#                                         forms.Select, forms.PasswordInput)):
#                 field.widget.attrs['class'] = 'form-control'
#             elif isinstance(field.widget, forms.FileInput):
#                 field.widget.attrs['class'] = 'form-control-file'
#             elif isinstance(field.widget, forms.CheckboxInput):
#                 field.widget.attrs['class'] = 'form-check-input'

#     def clean_username(self):
#         username = self.cleaned_data['username']
#         if self.user_instance and self.user_instance.username == username:
#             return username

#         existing_user = CustomUser.objects.filter(username=username).first()
#         if existing_user:
#             if hasattr(existing_user, 'student_profile'):
#                 raise ValidationError("This username is already taken and belongs to an existing student. Please choose a different username.")
#             else:
#                 raise ValidationError("This username is already taken by another user. Please choose a different username.")
#         return username

#     def clean_email(self):
#         email = self.cleaned_data['email']
#         if not email:
#             return email
        
#         if self.user_instance and self.user_instance.email == email:
#             return email

#         existing_user = CustomUser.objects.filter(email=email).first()
#         if existing_user:
#             if hasattr(existing_user, 'student_profile'):
#                 raise ValidationError("This email address is already in use and belongs to an existing student. Please use a different one.")
#             else:
#                 raise ValidationError("This email address is already in use by another user. Please use a different one.")
#         return email

#     def clean_admission_number(self):
#         admission_number = self.cleaned_data['admission_number']
#         if self.instance and self.instance.admission_number == admission_number:
#             return admission_number
#         if Student.objects.filter(admission_number=admission_number).exists():
#             raise ValidationError("This admission number is already taken. Please choose a unique one.")
#         return admission_number

#     def clean(self):
#         cleaned_data = super().clean()
#         password = cleaned_data.get('password')
#         confirm_password = cleaned_data.get('confirm_password')

#         if not self.user_instance:
#             if not password:
#                 self.add_error('password', "Password is required for new students.")
#             if not confirm_password:
#                 self.add_error('confirm_password', "Confirm Password is required for new students.")
        
#         if password and confirm_password and password != confirm_password:
#             self.add_error('confirm_password', "Passwords do not match.")
        
#         return cleaned_data

#     @transaction.atomic
#     def save(self, commit=True):
#         first_name = self.cleaned_data['first_name']
#         last_name = self.cleaned_data['last_name']
#         email = self.cleaned_data['email']
#         username = self.cleaned_data['username']
#         profile_pic = self.cleaned_data.get('profile_pic')
#         phone = self.cleaned_data['phone']
#         address = self.cleaned_data['address']
#         password = self.cleaned_data.get('password')

#         if self.user_instance:
#             user = self.user_instance
#             user.first_name = first_name
#             user.last_name = last_name
#             user.email = email
#             user.username = username
#             user.phone = phone
#             user.address = address

#             if 'profile_pic' in self.changed_data:
#                 user.profile_pic = profile_pic
#             elif 'profile_pic' in self.fields and not profile_pic and user.profile_pic: 
#                  user.profile_pic.delete(save=False)
#                  user.profile_pic = None
                 
#             if password: 
#                 user.set_password(password)
#             user.save()
            
#             student = super().save(commit=False) 
#             student.user = user 

#         else:
#             user = CustomUser.objects.create_user(
#                 username=username,
#                 email=email,
#                 password=password,
#                 first_name=first_name,
#                 last_name=last_name,
#                 user_type=3, 
#                 phone=phone,
#                 address=address,
#             )
#             if profile_pic:
#                 user.profile_pic = profile_pic
#             user.save()

#             student = super().save(commit=False)
#             student.user = user 
        
#         if commit:
#             student.save()
#         return student
    
# Add these forms if they are missing from your forms.py, as indicated by your traceback
# class FeePaymentForm(forms.ModelForm):
#     class Meta:
#         model = FeePayment
#         fields = '__all__' # Or specify your fields
#         widgets = {
#             'payment_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
#             'student': forms.Select(attrs={'class': 'form-control'}),
#             'fee_structure': forms.Select(attrs={'class': 'form-control'}),
#             'amount': forms.NumberInput(attrs={'class': 'form-control'}),
#             'payment_method': forms.Select(attrs={'class': 'form-control'}),
#             'transaction_code': forms.TextInput(attrs={'class': 'form-control'}),
#             'received_by': forms.Select(attrs={'class': 'form-control'}),
#             'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
#         }

# class ExpenseForm(forms.ModelForm):
#     class Meta:
#         model = Expense
#         fields = '__all__' # Or specify your fields
#         widgets = {
#             'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
#             'bursar': forms.Select(attrs={'class': 'form-control'}),
#             'amount': forms.NumberInput(attrs={'class': 'form-control'}),
#             'category': forms.Select(attrs={'class': 'form-control'}),
#             'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
#             'receipt_number': forms.TextInput(attrs={'class': 'form-control'}),
#             'approved_by': forms.Select(attrs={'class': 'form-control'}),
#         }