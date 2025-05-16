from django.shortcuts import render,redirect,reverse
from django.http import HttpResponse,HttpResponseRedirect
from django.contrib.auth import login,logout
from index.EmailBackEnd import EmailBackEnd
from django.contrib import  messages
from django.core.files.storage import FileSystemStorage
from django.contrib.auth.decorators import login_required, user_passes_test
from .models import Student, FeeStructure, FeePayment, Expense,CustomUser, SessionYearModel
from .forms import FeePaymentForm, ExpenseForm
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
    return render(request,'n_log.html')

def Login(request):
    if request.method!="POST":
        return HttpResponse("<h2>Method Not Allowed !</h2>")
    else:
        user = EmailBackEnd.authenticate(request,username=request.POST.get("email"),password=request.POST.get("password"))
        if user != None:
            login(request,user)
            if user.user_type == 1:
                return redirect(reverse("admin_dashboard"))
            elif user.user_type == 2:
                return redirect(reverse("staff_home"))
            elif user.user_type == 3:
                return redirect(reverse("student_home"))
            elif user.user_type == 4:
                return redirect(reverse("bursar_home"))
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
    session_year = SessionYearModel.object.all()
    return render(request,"signup_student.html",{"session_year":session_year})

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

def bursar_check(user):
    return user.is_authenticated and hasattr(user, 'staff_profile') and user.staff_profile.is_bursar

@login_required
@user_passes_test(bursar_check)
def bursar_dashboard(request):
    return render(request, 'bursar/dashboard.html')

@login_required
@user_passes_test(bursar_check)
def fee_records(request):
    students = Student.objects.select_related('current_class').all()
    fee_structures = FeeStructure.objects.filter(is_active=True)
    
    context = {
        'students': students,
        'fee_structures': fee_structures,
    }
    return render(request, 'bursar/fee_records.html', context)

@login_required
@user_passes_test(bursar_check)
def record_payment(request, student_id):
    student = Student.objects.get(id=student_id)
    
    if request.method == 'POST':
        form = FeePaymentForm(request.POST)
        if form.is_valid():
            payment = form.save(commit=False)
            payment.student = student
            payment.received_by = request.user.staff_profile
            payment.save()
            messages.success(request, 'Payment recorded successfully!')
            return redirect('fee_records')
    else:
        form = FeePaymentForm()
    
    payments = FeePayment.objects.filter(student=student).order_by('-payment_date')
    balance = sum(p.amount for p in payments)
    
    context = {
        'student': student,
        'form': form,
        'payments': payments,
        'balance': balance,
    }
    return render(request, 'bursar/record_payment.html', context)

@login_required
@user_passes_test(bursar_check)
def expense_management(request):
    if request.method == 'POST':
        form = ExpenseForm(request.POST)
        if form.is_valid():
            expense = form.save(commit=False)
            expense.bursar = request.user.staff_profile
            expense.save()
            messages.success(request, 'Expense recorded successfully!')
            return redirect('expense_management')
    else:
        form = ExpenseForm()
    
    expenses = Expense.objects.all().order_by('-date')
    
    context = {
        'form': form,
        'expenses': expenses,
    }
    return render(request, 'bursar/expense_management.html', context)

@login_required
@user_passes_test(bursar_check)
def payment_reports(request):
    # Get all payments grouped by class
    payments = FeePayment.objects.select_related('student__current_class').all()
    
    # Calculate totals
    total_paid = sum(p.amount for p in payments)
    total_students = Student.objects.count()
    
    context = {
        'payments': payments,
        'total_paid': total_paid,
        'total_students': total_students,
    }
    return render(request, 'bursar/payment_reports.html', context)