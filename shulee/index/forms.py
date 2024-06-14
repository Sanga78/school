from django import forms
from .models import Courses,SessionYearModel

class DateInput(forms.DateInput):
    input_type = "date"

class AddStudentForm(forms.Form):
    email = forms.EmailField(label="Email",max_length=50,widget=forms.EmailInput(attrs={"class":"form-control","autocomplete":"off"}))
    password = forms.CharField(label="Password",max_length=50,widget=forms.PasswordInput(attrs={"class":"form-control"}))
    first_name = forms.CharField(label="First Name",max_length=50,widget=forms.TextInput(attrs={"class":"form-control"}))
    last_name = forms.CharField(label="Last Name",max_length=50,widget=forms.TextInput(attrs={"class":"form-control"}))
    username = forms.CharField(label="Username",max_length=50,widget=forms.TextInput(attrs={"class":"form-control","autocomplete":"off"}))
    address = forms.CharField(label="Address",max_length=50,widget=forms.TextInput(attrs={"class":"form-control"}))
    course_list = []
    try:
        courses = Courses.objects.all()

        for course in courses:
            small_course = (course.id,course.course_name)
            course_list.append(small_course)
    except:
        course_list = []
    
    session_list = []
    sessions = SessionYearModel.object.all()

    for session in sessions:
        small_session = (session.id, str(session.session_start_year)+" TO "+str(session.session_end_year))
        session_list.append(small_session)
    
    gender_choices=(
        ("Male","Male"),
        ("Female","Female")
    )

    course = forms.ChoiceField(label="Course",choices=course_list,widget=forms.Select(attrs={"class":"form-control"}))
    sex = forms.ChoiceField(label="Sex",choices=gender_choices,widget=forms.Select(attrs={"class":"form-control"}))
    session_year_id = forms.ChoiceField(label="Session Year",choices=session_list,widget=forms.Select(attrs={"class":"form-control"}))
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
    
    session_list = []
    try:
        sessions = SessionYearModel.object.all()
        
        for session in sessions:
            small_session = (session.id, str(session.session_start_year)+" TO "+str(session.session_end_year))
            session_list.append(small_session)
    except:
        session_list = []
    gender_choices=(
        ("Male","Male"),
        ("Female","Female")
    )

    course = forms.ChoiceField(label="Course",choices=course_list,widget=forms.Select(attrs={"class":"form-control"}))
    sex = forms.ChoiceField(label="Sex",choices=gender_choices,widget=forms.Select(attrs={"class":"form-control"}))
    session_year_id = forms.ChoiceField(label="Sesssion Year",choices=session_list,widget=forms.Select(attrs={"class":"form-control"}))
    profile_pic = forms.FileField(label="Profile Picture",max_length=50,widget=forms.FileInput(attrs={"class":"form-control"}),required=False) 