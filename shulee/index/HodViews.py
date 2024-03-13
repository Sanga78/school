from django.shortcuts import render
from django.http import HttpResponse,HttpResponseRedirect
from index.models import CustomUser
from django.contrib import messages
def admin_home(request):
    return render(request, "hod_templates/home.html")

def add_staff(request):
    return render(request,"hod_templates/add_staff.html")

def add_staff_save(request):
    if request.method!="POST":
        return HttpResponse("Method Not Allowed")
    else:
        first_name = request.POST.get("first_name")
        last_name = request.POST.get("last_name")
        username = request.POST.get("username")
        email = request.POST.get("email") 
        password = request.POST.get("password")
        address = request.POST.get("address")
        try:
            user=CustomUser.create_user(username=username,password=password,email=email,last_name=last_name,first_name=first_name,user_type=2)
            user.staffs.address = address
            user.save()
            messages.success(request,"Successfully added staff")
            return HttpResponseRedirect("/add_staff")
        except:
            messages.error(request,"Failed to add staff")
            return HttpResponseRedirect("/add_staff")
    