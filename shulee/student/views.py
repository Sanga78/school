from django.shortcuts import render,redirect

# Create your views here.
from django.contrib.auth.models import User,auth
from django.contrib import messages
from django.contrib.auth import login, authenticate, logout 
from .models import Student

def register(request):
    if request.method == 'POST':
        fname = request.POST['firstname']
        lname = request.POST['lastname']
        adm_num = request.POST['adm_num']
        image = request.POST['image']
        dob = request.POST['dob']
        password = request.POST['password']
        password2 = request.POST['password2']
    
        if password == password2:
            if User.objects.filter(adm_num=adm_num).exists():
                messages.info(request,'Account Already Exists')
                return redirect('register')
            else:
                user = User.objects.create_user(adm_num=adm_num,password=password)
                user.save()
                print('user created')
                return redirect('login')
        else:
            messages.info(request,'Password Not The Same')
            return redirect('register')
    else:
        return render(request,'register.html')

def login(request):
    if request.method == 'POST':
        adm_num = request.POST['adm_num']
        password = request.POST['password']
        
        user = auth.authenticate(adm_num=adm_num,password=password)
        
        if user is not None:
            auth.login(request, user)
            return redirect('/student/{{student.id}}/')
        else:
            messages.info(request,'Invalid Credentials')
            return redirect('login')
    else:
        return render(request,'login.html') 
    
def logout_request(request):
    logout(request)
    messages.info(request,"Logged out successfully!")
    return redirect('/')

def stude(request,pk):
    student = User.objects.get(pk=id)
    context ={
        "student" : student
    }
    return render(request,'students.html',context)