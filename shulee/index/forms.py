from typing import Any
from django import forms
from django.forms import ChoiceField
from .models import Courses,SessionYearModel, Subjects
from django.apps import apps

class ChoiceNoValidation(ChoiceField):
    def validate(self, value):
        pass
    
class DateInput(forms.DateInput):
    input_type = "date"

class AddStudentForm(forms.Form):
    email = forms.EmailField(label="Email",max_length=50,widget=forms.EmailInput(attrs={"class":"form-control","autocomplete":"off"}))
    password = forms.CharField(label="Password",max_length=50,widget=forms.PasswordInput(attrs={"class":"form-control"}))
    first_name = forms.CharField(label="First Name",max_length=50,widget=forms.TextInput(attrs={"class":"form-control"}))
    last_name = forms.CharField(label="Last Name",max_length=50,widget=forms.TextInput(attrs={"class":"form-control"}))
    username = forms.CharField(label="Username",max_length=50,widget=forms.TextInput(attrs={"class":"form-control","autocomplete":"off"}))
    address = forms.CharField(label="Address",max_length=50,widget=forms.TextInput(attrs={"class":"form-control"}))

    
    gender_choices=(
        ("Male","Male"),
        ("Female","Female")
    )

    course = forms.ChoiceField(label="Course", widget=forms.Select(attrs={"class": "form-control"}))
    sex = forms.ChoiceField(label="Sex",choices=gender_choices,widget=forms.Select(attrs={"class":"form-control"}))
    session_year_id = forms.ChoiceField(label="Session Year", widget=forms.Select(attrs={"class": "form-control"}))
    profile_pic = forms.FileField(label="Profile Picture",max_length=50,widget=forms.FileInput(attrs={"class":"form-control"})) 
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        CourseModel = apps.get_model('index', 'Courses')
        SessionYearModel = apps.get_model('index', 'SessionYearModel')

        course_list = [(course.id, course.course_name) for course in CourseModel.objects.all()]
        session_list = [(session.id, str(session.session_start_year) + " TO " + str(session.session_end_year)) for session in SessionYearModel.objects.all()]

        self.fields['course'].choices = course_list
        self.fields['session_year_id'].choices = session_list

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

    course = forms.ChoiceField(label="Course", widget=forms.Select(attrs={"class": "form-control"}))
    sex = forms.ChoiceField(label="Sex",choices=gender_choices,widget=forms.Select(attrs={"class":"form-control"}))
    session_year_id = forms.ChoiceField(label="Sesssion Year", widget=forms.Select(attrs={"class": "form-control"}))
    profile_pic = forms.FileField(label="Profile Picture",max_length=50,widget=forms.FileInput(attrs={"class":"form-control"}),required=False) 
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        CourseModel = apps.get_model('index', 'Courses')
        SessionYearModel = apps.get_model('index', 'SessionYearModel')

        course_list = [(course.id, course.course_name) for course in CourseModel.objects.all()]
        session_list = [(session.id, str(session.session_start_year) + " TO " + str(session.session_end_year)) for session in SessionYearModel.objects.all()]

        self.fields['course'].choices = course_list
        self.fields['session_year_id'].choices = session_list

class EditResultForm(forms.Form):
    def __init__(self,*args,**kwargs):
        self.staff_id=kwargs.pop("staff_id")
        super(EditResultForm,self).__init__(*args,**kwargs)
        subject_list=[]
        try:
            subjects=Subjects.objects.filter(staff_id=self.staff_id)
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

