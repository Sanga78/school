from django.shortcuts import render
from django.http import HttpResponse,HttpResponseRedirect
from index.models import CustomUser,Courses,Subjects,Staffs,Students
from django.contrib import messages
from django.core.files.storage import FileSystemStorage
from .forms import AddStudentForm,EditStudentForm
from django.urls import reverse
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
            return HttpResponseRedirect(reverse("add_staff"))
        except:
            messages.error(request,"Failed to Add staff")
            return HttpResponseRedirect(reverse("add_staff"))
    
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
            return HttpResponseRedirect(reverse("add_course"))
        except:
            messages.error(request,"Failed to Add course")
            return HttpResponseRedirect(reverse("add_course"))
        
def add_student(request):
    form = AddStudentForm()
    return render(request,"hod_templates/add_student.html",{"form":form})

def add_student_save(request):
    if request.method != "POST":
        return HttpResponse("Method Not Allowed")
    else:
        form = AddStudentForm(request.POST,request.FILES)
        if form.is_valid():
            first_name = form.cleaned_data("first_name")
            last_name = form.cleaned_data("last_name")
            username = form.cleaned_data("username")
            email = form.cleaned_data("email") 
            password = form.cleaned_data("password")
            address = form.cleaned_data("address")
            session_start = form.cleaned_data("session_start")
            session_end = form.cleaned_data("session_end")
            course_id = form.cleaned_data("course")
            sex = form.cleaned_data("sex")

            profile_pic = request.FILES['profile_pic']
            fs = FileSystemStorage()
            filename = fs.save(profile_pic.name,profile_pic)
            profile_pic_url = fs.url(filename)

            try:
                user=CustomUser.objects.create_user(username=username,password=password,email=email,last_name=last_name,first_name=first_name,user_type=3)
                user.students.address = address
                course_obj = Courses.objects.get(id=course_id)
                user.students.course_id = course_obj
                user.students.session_start_year = session_start
                user.students.session_end_year = session_end
                user.students.gender = sex
                user.students.profile_pic = profile_pic_url
                user.save()
                messages.success(request,"Successfully added student")
                return HttpResponseRedirect(reverse("add_student"))
            except:
                messages.error(request,"Failed to Add student")
                return HttpResponseRedirect(reverse("add_student"))
        else:
            form=AddStudentForm(request.POS)
            return render(request,"hod_templates/add_student.html",{"form":form})

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
            return HttpResponseRedirect(reverse("add_subject"))
        except:
            messages.error(request,"Failed to Add Subject")
            return HttpResponseRedirect(reverse("add_subject"))
 
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

def edit_staff(request,staff_id):
    staff=Staffs.objects.get(admin=staff_id)
    return render(request,"hod_templates/edit_staff.html",{"staff":staff,"id":staff_id})

def edit_staff_save(request):
    if request.method != "POST":
        return HttpResponse("<h2>Method Not Allowed</h2>")
    else:
        staff_id = request.POST.get("staff_id")
        first_name = request.POST.get("first_name")
        last_name = request.POST.get("last_name")
        username = request.POST.get("username")
        email = request.POST.get("email")
        address = request.POST.get("address")
        try:
            user=CustomUser.objects.get(id=staff_id)
            user.first_name = first_name
            user.last_name = last_name
            user.username = username
            user.email = email
            user.save()

            staff_model = Staffs.objects.get(admin=staff_id)
            staff_model.address=address
            staff_model.save() 
            messages.success(request,"Successfully Edited Staff")
            return HttpResponseRedirect(reverse("edit_staff",kwargs={"staff_id":staff_id}))
        except:
            messages.error(request,"Failed to Edit Staff")
            return HttpResponseRedirect(reverse("edit_staff",kwargs={"staff_id":staff_id}))
    
def edit_student(request,student_id):
    request.session['student_id']=student_id
    student=Students.objects.get(admin=student_id)
    form = EditStudentForm()
    form.fields['email'].initial=student.admin.email
    form.fields['first_name'].initial=student.admin.first_name
    form.fields['last_name'].initial=student.admin.last_name
    form.fields['username'].initial=student.admin.username
    form.fields['address'].initial=student.address
    form.fields['course'].initial=student.course_id.id
    form.fields['sex'].initial=student.gender
    form.fields['session_start'].initial=student.session_start_year
    form.fields['session_end'].initial=student.session_end_year
    return render(request,"hod_templates/edit_student.html",{"form":form,"id":student_id,"username":student.admin.username})

def edit_student_save(request):
    if request.method != "POST":
        return HttpResponse("<h2>Method Not Allowed</h2>")
    else:
        student_id = request.session.get("student_id")
        if student_id == None:
            return HttpResponseRedirect(reverse("manage_student"))
        form = EditStudentForm(request.POST,request.FILES)
        if form.is_valid():
            first_name = form.cleaned_data("first_name")
            last_name = form.cleaned_data("last_name")
            username = form.cleaned_data("username")
            email = form.cleaned_data("email") 
            address = form.cleaned_data("address")
            session_start = form.cleaned_data("session_start")
            session_end = form.cleaned_data("session_end")
            course_id = form.cleaned_data("course")
            sex = form.cleaned_data("sex")

            if request.FILES.get['profile_pic',False]:
                profile_pic = request.FILES['profile_pic']
                fs = FileSystemStorage()
                filename = fs.save(profile_pic.name,profile_pic)
                profile_pic_url = fs.url(filename)
            else:
                profile_pic_url = None 

            try:
                user=CustomUser.objects.get(id=student_id)
                user.first_name = first_name
                user.last_name = last_name
                user.username = username
                user.email = email
                user.save()

                student = Students.objects.get(admin=student_id)
                student.address=address
                student.session_start_year=session_start
                student.session_end_year=session_end
                student.gender=sex

                course = Courses.objects.get(id=course_id)
                student.course_id = course
                if profile_pic_url != None:
                    student.profile_pic = profile_pic_url
                student.save() 
                del request.session['student_id']
                messages.success(request,"Successfully Edited Student")
                return HttpResponseRedirect(reverse("edit_student",kwargs={"student_id":student_id}))
            except:
                messages.error(request,"Failed to Edit Student")
                return HttpResponseRedirect(reverse("edit_student",kwargs={"student_id":student_id}))
        else:
            form = EditStudentForm(request.POST)
            student = Students.objects.get(admin=student_id)
            return render(request,"hod_templates/edit_student.html",{"form":form,"id":student_id,"username":student.admin.username})
        
def edit_course(request,course_id):
    course=Courses.objects.get(id=course_id)
    return render(request,"hod_templates/edit_course.html",{"course":course,"id":course_id})

def edit_course_save(request):
    if request.method != 'POST':
        return HttpResponseRedirect("Method Not Allowed")
    else:
        course_id = request.POST.get("course_id")
        course_name = request.POST.get("course_name")
        try:
            course = Courses.objects.get(id=course_id)
            course.course_name = course_name
            course.save()
            messages.success(request,"Successfully Edited Course")
            return HttpResponseRedirect(reverse("edit_course",kwargs={"course_id":course_id}))
        except:
            messages.error(request,"Failed to Edit course")
            return HttpResponseRedirect(reverse("edit_course",kwargs={"course_id":course_id}))

def edit_subject(request,subject_id):
    subject=Subjects.objects.get(id=subject_id)
    courses=Courses.objects.all()
    staffs = CustomUser.objects.filter(user_type=2)
    return render(request,"hod_templates/edit_subject.html",{"subject":subject,"staffs":staffs,"courses":courses,"id":subject_id})

def edit_subject_save(request):
    if request.method != 'POST':
        return HttpResponseRedirect("Method Not Allowed")
    else:
        subject_id = request.POST.get("subject_id")
        subject_name = request.POST.get("subject_name")
        course_id = request.POST.get("course")
        staff_id = request.POST.get("staff")
        try:
            subject = Subjects.objects.get(id=subject_id)
            staff = CustomUser.objects.get(id=staff_id)
            course = Courses.objects.get(id=course_id)
            subject.staff_id = staff
            subject.course_id = course
            subject.subject_name = subject_name
            subject.save()
            messages.success(request,"Successfully Edited Subject")
            return HttpResponseRedirect(reverse("edit_subject",kwargs={"subject_id":subject_id}))
        except:
            messages.error(request,"Failed to Edit Subject")
            return HttpResponseRedirect(reverse("edit_subject",kwargs={"subject_id":subject_id}))

