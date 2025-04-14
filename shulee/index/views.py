from django.shortcuts import render,redirect,reverse
from django.http import HttpResponse,HttpResponseRedirect
from django.contrib.auth import login,logout
from index.EmailBackEnd import EmailBackEnd
from django.contrib import  messages
from django.core.files.storage import FileSystemStorage

from index.models import Courses, CustomUser, SessionYearModel
# Create your views here.
def index(request):
    return render(request,'dashboard.html')
def about(request):
    return render(request,'about.html')
def academics(request):
    return render(request,'academics.html')
def admissions(request):
    return render(request,'admissions.html')
def results(request):
    return render(request,'results.html')
def events(request):
    return render(request,'events.html')
def contact(request):
    return render(request,'contact.html')
def loginPage(request):
    return render(request,'login.html')

def Login(request):
    if request.method!="POST":
        return HttpResponse("<h2>Method Not Allowed !</h2>")
    else:
        user = EmailBackEnd.authenticate(request,username=request.POST.get("email"),password=request.POST.get("password"))
        if user != None:
            login(request,user)
            if user.user_type == "1":
                return HttpResponseRedirect(reverse("admin_home"))
            elif user.user_type == "2":
                return HttpResponseRedirect(reverse("staff_home"))
            else:
                return HttpResponseRedirect(reverse("student_home"))
        else:
            messages.error(request,"Invalid Login Details")
            return HttpResponseRedirect("/")
        
def GetUserDetails(request):
    if request.user != None:
        return HttpResponse("User : "+request.user.email+ " usertype : "+request.user.user_type)
    else:
        return HttpResponse("Please Login First")
    
def Logout(request):
    logout(request)
    return HttpResponseRedirect("/")

def Testurl(request):
    return HttpResponse("OK")

def signup_admin(request):
    return render(request,"signup_admin.html")

def admin_signup(request):
    if request.method!="POST":
        return HttpResponse("<h2>Method Not Allowed !</h2>")
    else:
        username = request.POST.get("username")
        email = request.POST.get("email")
        password = request.POST.get("password")
        try:
            user = CustomUser.objects.create_user(username=username,password=password,email=email,user_type=1)
            user.save()
            messages.success(request,"Successfully Created Admin")
            return HttpResponseRedirect(reverse("show_login"))
        except:
            messages.error(request,"Failed to Create Admin")
            return HttpResponseRedirect(reverse("signup_admin"))

def signup_staff(request):
    return render(request,"signup_staff.html")

def staff_signup(request):
    if request.method!="POST":
        return HttpResponse("<h2>Method Not Allowed !</h2>")
    else:
        username = request.POST.get("username")
        email = request.POST.get("email")
        password = request.POST.get("password")
        address = request.POST.get("address")
        try:
            user = CustomUser.objects.create_user(username=username,password=password,email=email,user_type=2)
            user.staffs.address=address
            user.save()
            messages.success(request,"Successfully Created  Staff")
            return HttpResponseRedirect(reverse("show_login"))
        except:
            messages.error(request,"Failed to Create Staff")
            return HttpResponseRedirect(reverse("signup_staff"))

def signup_student(request):
    courses = Courses.objects.all()
    session_year = SessionYearModel.object.all()
    return render(request,"signup_student.html",{"courses":courses,"session_year":session_year})

def student_signup(request):
    if request.method!="POST":
        return HttpResponse("<h2>Method Not Allowed !</h2>")
    else:
        first_name = request.POST.get("first_name")
        last_name = request.POST.get("last_name")
        username = request.POST.get("username")
        password = request.POST.get("password")
        email = request.POST.get("email") 
        address = request.POST.get("address")
        session_year_id = request.POST.get("session_year_id")
        course_id = request.POST.get("course")
        sex = request.POST.get("sex")

        profile_pic = request.FILES['profile_pic']

        fs = FileSystemStorage()
        filename = fs.save(profile_pic.name,profile_pic)
        profile_pic_url = fs.url(filename)

        try:
            user=CustomUser.objects.create_user(username=username,password=password,email=email,last_name=last_name,first_name=first_name,user_type=3)
            user.students.address = address
            course_obj = Courses.objects.get(id=course_id)
            user.students.course_id = course_obj
            session_year =SessionYearModel.object.get(id=session_year_id)
            user.students.session_year_id = session_year
            user.students.gender = sex
            user.students.profile_pic = profile_pic_url
            user.save()
            messages.success(request,"Successfully created student")
            return HttpResponseRedirect(reverse("show_login"))
        except:
            messages.error(request,"Failed to Add student")
            return HttpResponseRedirect(reverse("signup_student"))