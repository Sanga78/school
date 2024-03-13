from django.shortcuts import render
from django.http import HttpResponse,HttpResponseRedirect
from index.models import CustomUser,Courses
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
    return render(request,"hod_templates/add_student.html")

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
        try:
            user=CustomUser.objects.create_user(username=username,password=password,email=email,last_name=last_name,first_name=first_name,user_type=2)
            user.staffs.address = address
            user.save()
            messages.success(request,"Successfully added staff")
            return HttpResponseRedirect("/add_staff")
        except:
            messages.error(request,"Failed to Add staff")
            return HttpResponseRedirect("/add_staff")
    