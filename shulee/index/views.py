from django.shortcuts import render,redirect,reverse, get_object_or_404
from django.http import HttpResponse,HttpResponseRedirect
from django.core.exceptions import PermissionDenied
from django.contrib.auth import login,logout
from index.EmailBackEnd import EmailBackEnd
from django.contrib import  messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils import timezone
from django.db import transaction
from django.db.models import Max, Q, Sum
from decimal import Decimal
from django.views.decorators.http import require_POST
from .models import (
    AcademicYear,
    Student,
    StudentClass,
    FeeStructure,
    FeePayment,
    Expense,
    CustomUser,
    SessionYearModel,
    SchoolEvent,
)
from .forms import (
    AdminSignupForm,
    FeePaymentForm,
    FeeStructureForm,
    ExpenseForm,
    SchoolEventForm,
    StudentSignupForm,
)
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
    is_admin = request.user.is_authenticated and request.user.user_type == 1
    is_active_student = (
        request.user.is_authenticated
        and request.user.user_type == 3
        and Student.objects.filter(user=request.user, active=True).exists()
    )
    calendar_events = SchoolEvent.objects.filter(
        is_published=True,
        starts_at__gte=timezone.now(),
    ) if is_admin or is_active_student else SchoolEvent.objects.none()
    return render(request, 'events.html', {
        'calendar_events': calendar_events,
        'can_view_calendar': is_admin or is_active_student,
        'can_manage_events': is_admin,
    })

def _require_calendar_admin(request):
    if request.user.user_type != 1:
        raise PermissionDenied

@login_required
def manage_events(request):
    _require_calendar_admin(request)
    if request.method == 'POST':
        form = SchoolEventForm(request.POST)
        if form.is_valid():
            event = form.save(commit=False)
            event.created_by = request.user
            event.save()
            messages.success(request, 'School event saved to the calendar.')
            return redirect('manage_events')
    else:
        form = SchoolEventForm()
    return render(request, 'admin/manage_events.html', {
        'calendar_events': SchoolEvent.objects.filter(
            is_published=True,
            starts_at__gte=timezone.now(),
        ),
        'managed_events': SchoolEvent.objects.all(),
        'event_form': form,
        'can_view_calendar': True,
        'can_manage_events': True,
        'management_mode': True,
    })

@login_required
def edit_school_event(request, event_id):
    _require_calendar_admin(request)
    event = get_object_or_404(SchoolEvent, pk=event_id)
    if request.method == 'POST':
        form = SchoolEventForm(request.POST, instance=event)
        if form.is_valid():
            form.save()
            messages.success(request, 'School event updated.')
            return redirect('manage_events')
    else:
        form = SchoolEventForm(instance=event)
    return render(request, 'admin/manage_events.html', {
        'calendar_events': SchoolEvent.objects.filter(
            is_published=True,
            starts_at__gte=timezone.now(),
        ),
        'managed_events': SchoolEvent.objects.all(),
        'event_form': form,
        'editing_event': event,
        'can_view_calendar': True,
        'can_manage_events': True,
        'management_mode': True,
    })

@login_required
@require_POST
def delete_school_event(request, event_id):
    _require_calendar_admin(request)
    event = get_object_or_404(SchoolEvent, pk=event_id)
    event.delete()
    messages.success(request, 'School event removed from the calendar.')
    return redirect('manage_events')

def contact(request):
    return render(request,'contact.html')
def loginPage(request):
    return render(request,'login.html')
def home(request):
    return render(request,'home.html')
def apply(request):
    return render(request,'apply.html')

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
                return redirect(reverse("teacher_dashboard"))
            elif user.user_type == 3:
                student = get_object_or_404(Student, user=user)
                student.active = True
                student.save()
                return redirect(reverse("student_home"))
            elif user.user_type == 4:
                return redirect(reverse("bursar_dashboard"))
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

@login_required(login_url='show_login')
def signup_admin(request):
    _require_calendar_admin(request)
    return render(request,"signup_admin.html")

@login_required(login_url='show_login')
@require_POST
def admin_signup(request):
    _require_calendar_admin(request)
    form = AdminSignupForm(request.POST)
    if not form.is_valid():
        return render(request, 'signup_admin.html', {'form': form}, status=400)
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
            return HttpResponseRedirect(reverse("manage_administrators"))
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
    form = StudentSignupForm()
    return render(request, 'signup_student.html', {
        'form': form,
        'academic_years': form.fields['academic_year'].queryset,
        'classes': form.fields['current_class'].queryset,
    })

def _legacy_student_signup(request):
    raise PermissionDenied
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
            session_year = SessionYearModel.objects.get(id=session_year_id)
            user.students.session_year_id = session_year
            user.students.gender = sex
            user.students.profile_pic = profile_pic_url
            user.save()
            messages.success(request,"Successfully created student")
            return HttpResponseRedirect(reverse("show_login"))
        except:
            messages.error(request,"Failed to Add student")
            return HttpResponseRedirect(reverse("signup_student"))

@require_POST
def student_signup(request):
    form = StudentSignupForm(request.POST, request.FILES)
    context = {
        'form': form,
        'academic_years': form.fields['academic_year'].queryset,
        'classes': form.fields['current_class'].queryset,
    }
    if not form.is_valid():
        return render(request, 'signup_student.html', context, status=400)

    with transaction.atomic():
        user = CustomUser.objects.create_user(
            username=form.cleaned_data['username'],
            email=form.cleaned_data['email'],
            password=form.cleaned_data['password'],
            first_name=form.cleaned_data['first_name'],
            last_name=form.cleaned_data['last_name'],
            address=form.cleaned_data['address'],
            user_type=3,
        )
        student = user.student_profile
        student.current_class = form.cleaned_data['current_class']
        student.academic_year = form.cleaned_data['academic_year']
        student.gender = form.cleaned_data['gender']
        student.save()

        profile_image = form.cleaned_data['profile_pic']
        if profile_image:
            user.profile_pic = profile_image
            user.save(update_fields=['profile_pic'])

    messages.success(request, 'Your student account was created. You can now sign in.')
    return redirect('show_login')


def bursar_check(user):
    return (
        user.is_authenticated
        and user.is_active
        and user.user_type == 4
        and hasattr(user, 'bursar_profile')
    )

@login_required
@user_passes_test(bursar_check)
def bursar_dashboard(request):
    total_paid = FeePayment.objects.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    total_expenses = Expense.objects.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    recent_payments = FeePayment.objects.select_related(
        'student__user',
    ).order_by('-payment_date', '-created_at')[:5]
    recent_expenses = Expense.objects.order_by('-date', '-created_at')[:5]
    return render(request, 'bursar/dashboard.html', {
        'total_paid': total_paid,
        'total_expenses': total_expenses,
        'balance': total_paid - total_expenses,
        'recent_payments': recent_payments,
        'recent_expenses': recent_expenses,
    })

@login_required
@user_passes_test(bursar_check)
def fee_records(request):
    if request.method == 'POST':
        fee_structure_form = FeeStructureForm(request.POST)
        if fee_structure_form.is_valid():
            fee_structure_form.save()
            messages.success(request, 'Fee structure added successfully.')
            return redirect('fee_records')
    else:
        fee_structure_form = FeeStructureForm()

    students = Student.objects.select_related(
        'user', 'current_class', 'academic_year',
    ).annotate(
        total_paid=Sum('payments__amount'),
        last_payment_date=Max('payments__payment_date'),
    )
    search = request.GET.get('q', '').strip()
    if search:
        students = students.filter(
            Q(user__first_name__icontains=search)
            | Q(user__last_name__icontains=search)
            | Q(user__username__icontains=search)
        )

    class_id = request.GET.get('class', '')
    if class_id.isdecimal():
        students = students.filter(current_class_id=int(class_id))
    else:
        class_id = ''

    academic_year_id = request.GET.get('academic_year', '')
    if academic_year_id.isdecimal():
        students = students.filter(academic_year_id=int(academic_year_id))
    else:
        academic_year_id = ''

    status = request.GET.get('status', '')
    if status == 'active':
        students = students.filter(active=True)
    elif status == 'inactive':
        students = students.filter(active=False)
    else:
        status = ''

    ordering_options = {
        'name': ('user__last_name', 'user__first_name', 'user__username'),
        '-name': ('-user__last_name', '-user__first_name', 'user__username'),
        'class': ('current_class__name', 'user__last_name', 'user__first_name'),
        '-class': ('-current_class__name', 'user__last_name', 'user__first_name'),
        'paid': ('total_paid', 'user__last_name', 'user__first_name'),
        '-paid': ('-total_paid', 'user__last_name', 'user__first_name'),
        'last_payment': ('last_payment_date', 'user__last_name', 'user__first_name'),
        '-last_payment': ('-last_payment_date', 'user__last_name', 'user__first_name'),
    }
    sort = request.GET.get('sort', 'name')
    if sort not in ordering_options:
        sort = 'name'
    students = students.order_by(*ordering_options[sort])

    context = {
        'students': students,
        'classes': StudentClass.objects.select_related('academic_year').order_by(
            'academic_year__start_date', 'name',
        ),
        'academic_years': AcademicYear.objects.order_by('-start_date'),
        'fee_structures': FeeStructure.objects.filter(is_active=True).select_related(
            'class_obj', 'academic_year',
        ),
        'fee_structure_form': fee_structure_form,
        'search': search,
        'class_filter': class_id,
        'academic_year_filter': academic_year_id,
        'status_filter': status,
        'sort': sort,
    }
    return render(request, 'bursar/fee_records.html', context)

@login_required
@user_passes_test(bursar_check)
def record_payment(request, student_id):
    student = get_object_or_404(
        Student.objects.select_related('user', 'current_class'),
        id=student_id,
    )
    
    if request.method == 'POST':
        form = FeePaymentForm(request.POST, student=student)
        if form.is_valid():
            payment = form.save(commit=False)
            payment.student = student
            payment.recorded_by_bursar = request.user.bursar_profile
            payment.save()
            messages.success(request, 'Payment recorded successfully!')
            return redirect('fee_records')
    else:
        form = FeePaymentForm(student=student)
    
    payments = FeePayment.objects.filter(student=student).select_related(
        'fee_structure', 'recorded_by_bursar__user',
    )
    total_paid = payments.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    
    context = {
        'student': student,
        'form': form,
        'payments': payments,
        'total_paid': total_paid,
    }
    return render(request, 'bursar/record_payment.html', context)

@login_required
@user_passes_test(bursar_check)
def expense_management(request):
    if request.method == 'POST':
        form = ExpenseForm(request.POST)
        if form.is_valid():
            expense = form.save(commit=False)
            expense.recorded_by_bursar = request.user.bursar_profile
            expense.save()
            messages.success(request, 'Expense recorded successfully!')
            return redirect('expense_management')
    else:
        form = ExpenseForm()
    
    expenses = Expense.objects.select_related('recorded_by_bursar__user').all()
    total_expenses = expenses.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    
    context = {
        'form': form,
        'expenses': expenses,
        'total_expenses': total_expenses,
    }
    return render(request, 'bursar/expense_management.html', context)

@login_required
@user_passes_test(bursar_check)
def payment_reports(request):
    # Get all payments grouped by class
    payments = FeePayment.objects.select_related(
        'student__user', 'student__current_class', 'fee_structure',
        'recorded_by_bursar__user',
    ).all()
    expenses = Expense.objects.select_related('recorded_by_bursar__user').all()
    total_paid = payments.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    total_expenses = expenses.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    total_students = Student.objects.count()
    
    context = {
        'payments': payments,
        'expenses': expenses,
        'total_paid': total_paid,
        'total_expenses': total_expenses,
        'balance': total_paid - total_expenses,
        'total_students': total_students,
    }
    return render(request, 'bursar/payment_reports.html', context)