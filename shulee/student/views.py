from django.shortcuts import render,redirect

# Create your views here.
from django.contrib.auth.models import User,auth
from django.contrib import messages


def register(request):
    if request.method == 'POST':
        username = request.POST['username']
        email = request.POST['email']
        image = request.POST['image']
        dob = request.POST['dob']
        password = request.POST['password']
        password2 = request.POST['password2']
    
        if password == password2:
            if User.objects.filter(email=email).exists():
                messages.info(request,'Email Already Exists')
                return redirect('register')
            elif User.objects.filter(username=username).exists():
                messages.info(request,'Username Already Exists')
                return redirect('register')
            else:
                user = User.objects.create_user(username=username,email=email,password=password)
                user.save()
                print('user created')
                return redirect('login')
        else:
            messages.info(request,'Password Not The Same')
            return redirect('register')
    else:
        return render(request,'index.html')

def login(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        
        user = auth.authenticate(username=username,password=password)
        
        if user is not None:
            auth.login(request, user)
            return redirect('services')
        else:
            messages.info(request,'Invalid Credentials')
            return redirect('login')
    else:
        return render(request,'student.html') 