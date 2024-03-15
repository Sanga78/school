from django.shortcuts import render
from django.http import HttpResponse,HttpResponseRedirect
from index.models import CustomUser,Courses,Subjects,Staffs,Students
from django.contrib import messages
def admin_home(request):
    return render(request, "hod_templates/home.html")

def add_staff(request):
    return render(request,"hod_templates/add_staff.html")

def add_staff_save(request):
    if request.method != "POST":
        return HttpResponse("Method Not Allowed")
    else:
        first_name = request.POST.get("first_name")
        last_name = request.POST.get("last_name")
        username = request.POST.get("username")
        email = request.POST.get("email") 
        password = request.POST.get("password")
        address = request.POST.get("address")
        try:
            user=CustomUser.objects.create_user(username=username,password=password,email=email,last_name=last_name,first_name=first_name,user_type=2)
            user.staffs.address = address
            user.save()
            messages.success(request,"Successfully added staff")
            return HttpResponseRedirect("/add_staff")
        except:
            messages.error(request,"Failed to Add staff")
            return HttpResponseRedirect("/add_staff")
    
def add_course(request):
    return render(request, 'hod_templates/add_course.html')

def add_course_save(request):
    if request.method != 'POST':
        return HttpResponseRedirect("Method Not Allowed")
    else:
        course = request.POST.get("course")
        try:
            course_model = Courses(course_name=course)
            course_model.save()
            messages.success(request,"Successfully added Course")
            return HttpResponseRedirect("/add_course")
        except:
            messages.error(request,"Failed to Add course")
            return HttpResponseRedirect("/add_course")
        
def add_student(request):
    courses= Courses.objects.all()
    return render(request,"hod_templates/add_student.html",{"courses":courses})

def add_student_save(request):
    if request.method != "POST":
        return HttpResponse("Method Not Allowed")
    else:
        first_name = request.POST.get("first_name")
        last_name = request.POST.get("last_name")
        username = request.POST.get("username")
        email = request.POST.get("email") 
        password = request.POST.get("password")
        address = request.POST.get("address")
        session_start = request.POST.get("session_start")
        session_end = request.POST.get("session_end")
        course_id = request.POST.get("course")
        sex = request.POST.get("sex")
        try:
            user=CustomUser.objects.create_user(username=username,password=password,email=email,last_name=last_name,first_name=first_name,user_type=3)
            user.students.address = address
            course_obj = Courses.objects.get(id=course_id)
            user.students.course_id = course_obj
            user.students.session_start_year = session_start
            user.students.session_end_year = session_end
            user.students.gender = sex
            user.students.profile_pic = ""
            user.save()
            messages.success(request,"Successfully added student")
            return HttpResponseRedirect("/add_student")
        except:
            messages.error(request,"Failed to Add student")
            return HttpResponseRedirect("/add_student")
    

def add_subject(request):
    courses = Courses.objects.all()
    staffs = CustomUser.objects.filter(user_type=2)
    return render(request, 'hod_templates/add_subject.html',{"courses":courses,"staffs":staffs})

def add_subject_save(request):
    if request.method != 'POST':
        return HttpResponseRedirect("Method Not Allowed")
    else:
        subject_name = request.POST.get("subject_name")
        course_id = request.POST.get("course")
        course = Courses.objects.get(id=course_id)
        staff_id = request.POST.get("staff")
        staff = CustomUser.objects.get(id=staff_id)
        try:
            subject = Subjects(subject_name=subject_name,course_id=course,staff_id=staff)
            subject.save()
            messages.success(request,"Successfully Added Subject")
            return HttpResponseRedirect("/add_subject")
        except:
            messages.error(request,"Failed to Add Subject")
            return HttpResponseRedirect("/add_subject")
 
def manage_staff(request):
    staffs=Staffs.objects.all()
    return render(request,"hod_templates/manage_staff.html",{"staffs":staffs})

def manage_student(request):
    students=Students.objects.all()
    return render(request,"hod_templates/manage_student.html",{"students":students})

def manage_course(request):
    courses=Courses.objects.all()
    return render(request,"hod_templates/manage_course.html",{"courses":courses})

def manage_subject(request):
    subjects=Subjects.objects.all()
    return render(request,"hod_templates/manage_subjects.html",{"subjects":subjects})
