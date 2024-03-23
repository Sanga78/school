from django import forms
from .models import Courses

class DateInput(forms.DateInput):
    input_type = "date"

class AddStudentForm(forms.Form):
    email = forms.EmailField(label="Email",max_length=50,widget=forms.EmailInput(attrs={"class":"form-control"}))
    password = forms.CharField(label="Password",max_length=50,widget=forms.PasswordInput(attrs={"class":"form-control"}))
    first_name = forms.CharField(label="First Name",max_length=50,widget=forms.TextInput(attrs={"class":"form-control"}))
    last_name = forms.CharField(label="Last Name",max_length=50,widget=forms.TextInput(attrs={"class":"form-control"}))
    username = forms.CharField(label="Username",max_length=50,widget=forms.TextInput(attrs={"class":"form-control"}))
    address = forms.CharField(label="Address",max_length=50,widget=forms.TextInput(attrs={"class":"form-control"}))
    course_list = []
    
    try:
        courses = Courses.objects.all()
        for course in courses:
            small_course = (course.id,course.course_name)
            course_list.append(small_course)
    except:
        course_list = []
    gender_choices=(
        ("Male","Male"),
        ("Female","Female")
    )

    course = forms.ChoiceField(label="Course",choices=course_list,widget=forms.Select(attrs={"class":"form-control"}))
    sex = forms.ChoiceField(label="Sex",choices=gender_choices,widget=forms.Select(attrs={"class":"form-control"}))
    session_start = forms.DateField(label="Session Start",widget=DateInput(attrs={"class":"form-control"}))
    session_end = forms.DateField(label="Session End",widget=DateInput(attrs={"class":"form-control"}))
    profile_pic = forms.FileField(label="Profile Picture",max_length=50,widget=forms.FileInput(attrs={"class":"form-control"})) 

class EditStudentForm(forms.Form):
    email = forms.EmailField(label="Email",max_length=50,widget=forms.EmailInput(attrs={"class":"form-control"}))
    first_name = forms.CharField(label="First Name",max_length=50,widget=forms.TextInput(attrs={"class":"form-control"}))
    last_name = forms.CharField(label="Last Name",max_length=50,widget=forms.TextInput(attrs={"class":"form-control"}))
    username = forms.CharField(label="Username",max_length=50,widget=forms.TextInput(attrs={"class":"form-control"}))
    address = forms.CharField(label="Address",max_length=50,widget=forms.TextInput(attrs={"class":"form-control"}))

    course_list = []
    try:
        courses = Courses.objects.all()
        for course in courses:
            small_course = (course.id,course.course_name)
            course_list.append(small_course)
    except:
        course_list = []
    gender_choices=(
        ("Male","Male"),
        ("Female","Female")
    )

    course = forms.ChoiceField(label="Course",choices=course_list,widget=forms.Select(attrs={"class":"form-control"}))
    sex = forms.ChoiceField(label="Sex",choices=gender_choices,widget=forms.Select(attrs={"class":"form-control"}))
    session_start = forms.DateField(label="Session Start",widget=DateInput(attrs={"class":"form-control"}))
    session_end = forms.DateField(label="Session End",widget=DateInput(attrs={"class":"form-control"}))
    profile_pic = forms.FileField(label="Profile Picture",max_length=50,widget=forms.FileInput(attrs={"class":"form-control"}),required=False) 