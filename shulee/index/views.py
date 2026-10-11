from django.shortcuts import render,redirect,reverse, get_object_or_404
from django.http import HttpResponse,HttpResponseRedirect
from django.core.exceptions import PermissionDenied
from django.contrib.auth import login,logout
from index.EmailBackEnd import EmailBackEnd
from django.contrib import  messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils import timezone
from django.db.models import (
    Case,
    CharField,
    DecimalField,
    ExpressionWrapper,
    F,
    Max,
    OuterRef,
    Q,
    Subquery,
    Sum,
    Value,
    When,
)
from django.db.models.functions import Coalesce
from django.db import transaction
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
    SchoolEvent,
    CashPaymentApproval,
    FeeTransaction,
    StudentApplication,
    school_cash_balance,
    SchoolProfile,
    UniformItem,
    Staff,
    Bursar,
    Notification,
    NotificationReadStatus,
)
from django.utils.http import url_has_allowed_host_and_scheme
from .forms import (
    FeePaymentForm,
    FeeStructureForm,
    ExpenseForm,
    SchoolEventForm,
    StudentSignupForm,
)
def _portal_base_template(user):
    return {
        1: 'admin/base.html',
        2: 'teacher/base.html',
        3: 'student_template/base.html',
        4: 'bursar/base.html',
    }.get(user.user_type, 'base.html')


@login_required
def notifications(request):
    read_ids = set(NotificationReadStatus.objects.filter(user=request.user).values_list('notification_id', flat=True))
    items = list(Notification.objects.filter(recipients=request.user).order_by('-created_at')[:100])
    for item in items:
        item.is_read = item.pk in read_ids
    return render(request, 'notifications/inbox.html', {
        'notifications': items,
        'base_template': _portal_base_template(request.user),
    })


@login_required
def open_notification(request, notification_id):
    notification = get_object_or_404(Notification, pk=notification_id, recipients=request.user)
    NotificationReadStatus.objects.get_or_create(notification=notification, user=request.user)
    if notification.link and url_has_allowed_host_and_scheme(notification.link, allowed_hosts={request.get_host()}):
        return redirect(notification.link)
    return redirect('notifications')


@login_required
@require_POST
def mark_notifications_read(request):
    unread = Notification.objects.filter(recipients=request.user).exclude(read_statuses__user=request.user)
    NotificationReadStatus.objects.bulk_create(
        [NotificationReadStatus(notification=n, user=request.user) for n in unread],
        ignore_conflicts=True,
    )
    return redirect('notifications')


# Create your views here.
def public_school_context():
    leaders = []
    for staff in Staff.objects.filter(
        role__in=['DEPUTY_HEADTEACHER', 'BOARDING_MASTER'], user__is_active=True,
    ).select_related('user'):
        leaders.append({
            'name': staff.user.get_full_name() or staff.user.username,
            'title': staff.get_role_display(),
            'photo': staff.user.profile_pic,
            'order': 0 if staff.role == 'DEPUTY_HEADTEACHER' else 1,
        })
    for bursar in Bursar.objects.filter(user__is_active=True).select_related('user')[:1]:
        leaders.append({
            'name': bursar.user.get_full_name() or bursar.user.username,
            'title': 'Bursar',
            'photo': bursar.user.profile_pic,
            'order': 2,
        })
    leaders.sort(key=lambda leader: leader['order'])
    return {
        'school_profile': SchoolProfile.get(),
        'uniform_items': UniformItem.objects.all(),
        'leaders': leaders,
    }


def index(request):
    return render(request, 'dashboard.html', public_school_context())
def about(request):
    return render(request,'about.html')
def academics(request):
    return render(request,'academics.html')
def admissions(request):
    return render(request,'admissions.html')
def results(request):
    return render(request,'results.html')
def events(request):
    user = request.user
    is_admin = user.is_authenticated and user.user_type == 1
    upcoming = SchoolEvent.objects.filter(
        is_published=True,
        starts_at__gte=timezone.now(),
    ).select_related('audience_class')
    if is_admin:
        calendar_events = upcoming
    else:
        visible = Q(audience_class__isnull=True)
        if user.is_authenticated and user.user_type == 3:
            student = Student.objects.filter(user=user, active=True).first()
            if student is not None:
                visible |= Q(pk__in=student.targeted_events.values('pk')) | Q(
                    audience_class_id=student.current_class_id,
                    pk__in=SchoolEvent.objects.filter(recipients__isnull=True).values('pk'),
                )
        elif user.is_authenticated and user.user_type == 2:
            visible |= Q(created_by=user)
        calendar_events = upcoming.filter(visible).distinct()
    return render(request, 'events.html', {
        'calendar_events': calendar_events,
        'can_view_calendar': True,
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
    return render(request, 'home.html', public_school_context())
def _application_context(form):
    today = timezone.localdate()
    max_age, min_age = form.MAX_AGE, form.MIN_AGE
    return {
        'form': form,
        'academic_years': form.fields['academic_year'].queryset,
        'classes': form.fields['current_class'].queryset,
        'min_age': min_age,
        'max_age': max_age,
        'latest_birth_date': today.replace(year=today.year - min_age, day=min(today.day, 28)),
        'earliest_birth_date': today.replace(year=today.year - max_age - 1, day=min(today.day, 28)),
    }


def apply(request):
    return render(request, 'apply.html', _application_context(StudentSignupForm()))

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
                if student.active:
                    return redirect("student_home")
                if hasattr(student, 'application'):
                    return redirect("student_application_status")
                logout(request)
                messages.error(request, "Your student account is inactive. Contact the school office for assistance.")
                return redirect("show_login")
            elif user.user_type == 4:
                return redirect(reverse("bursar_dashboard"))
        else:
            messages.error(request,"Invalid Login Details")
            return redirect("show_login")
        
def GetUserDetails(request):
    if request.user != None:
        return HttpResponse("User : "+request.user.email+ " usertype : "+request.user.user_type)
    else:
        return HttpResponse("Please Login First")
    
def Logout(request):
    logout(request)
    return HttpResponseRedirect("/")

def signup_student(request):
    return redirect('apply')

def _temporary_application_username():
    count = StudentApplication.objects.count() + 1
    while CustomUser.objects.filter(username=f'APP{count:06d}').exists():
        count += 1
    return f'APP{count:06d}'


@require_POST
def student_signup(request):
    form = StudentSignupForm(request.POST, request.FILES)
    context = _application_context(form)
    if not form.is_valid():
        return render(request, 'apply.html', context, status=400)

    username = form.cleaned_data.get('username') or _temporary_application_username()
    with transaction.atomic():
        user = CustomUser.objects.create_user(
            username=username,
            email=form.cleaned_data.get('email') or '',
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
        student.date_of_birth = form.cleaned_data.get('date_of_birth')
        student.birth_certificate_number = form.cleaned_data.get('birth_certificate_number') or None
        student.parent_email = form.cleaned_data['parent_email']
        student.active = False
        student.save()
        application = StudentApplication.objects.create(student=student)

        profile_image = form.cleaned_data['profile_pic']
        if profile_image:
            user.profile_pic = profile_image
            user.save(update_fields=['profile_pic'])

    return redirect('application_confirmation', application_id=application.id)


def application_confirmation(request, application_id):
    try:
        application = StudentApplication.objects.select_related('student__user', 'student__current_class', 'student__academic_year').get(id=application_id)
    except StudentApplication.DoesNotExist:
        messages.error(request, 'Application not found.')
        return redirect('home')
    
    context = {
        'application': application,
        'student': application.student,
    }
    return render(request, 'confirmation_letter.html', context)


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
        'balance': school_cash_balance(),
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

    money_field = DecimalField(max_digits=12, decimal_places=2)
    structure_totals = FeeStructure.objects.filter(
        Q(applies_to='ALL') | Q(applies_to=OuterRef('boarder_type')),
        class_obj_id=OuterRef('current_class_id'),
        academic_year_id=OuterRef('current_class__academic_year_id'),
        is_active=True,
    ).order_by().values('class_obj_id').annotate(
        total=Sum('amount'),
    ).values('total')[:1]
    legacy_invoice_totals = FeeTransaction.objects.filter(
        student_id=OuterRef('pk'),
        transaction_type='INVOICE',
    ).order_by().values('student_id').annotate(
        total=Sum('amount'),
    ).values('total')[:1]
    student_payment_totals = FeePayment.objects.filter(
        student_id=OuterRef('pk'),
    ).order_by().values('student_id').annotate(
        total=Sum('amount'),
    ).values('total')[:1]
    unlinked_payment_totals = FeeTransaction.objects.filter(
        student_id=OuterRef('pk'),
        transaction_type='PAYMENT',
        fee_payment__isnull=True,
    ).order_by().values('student_id').annotate(
        total=Sum('amount'),
    ).values('total')[:1]
    students = Student.objects.select_related(
        'user', 'current_class', 'academic_year',
    ).annotate(
        boarder_type=Case(
            When(is_boarder=True, then=Value('BOARDER')),
            default=Value('DAY'),
            output_field=CharField(),
        ),
    ).annotate(
        total_fee_due=Coalesce(
            Subquery(structure_totals, output_field=money_field),
            Subquery(legacy_invoice_totals, output_field=money_field),
            Value(Decimal('0.00')),
            output_field=money_field,
        ),
        total_paid=(
            Coalesce(
                Subquery(student_payment_totals, output_field=money_field),
                Value(Decimal('0.00')),
                output_field=money_field,
            ) + Coalesce(
                Subquery(unlinked_payment_totals, output_field=money_field),
                Value(Decimal('0.00')),
                output_field=money_field,
            )
        ),
        last_payment_date=Max('payments__payment_date'),
    ).annotate(
        fee_balance=ExpressionWrapper(
            F('total_fee_due') - F('total_paid'),
            output_field=money_field,
        ),
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
        form = FeePaymentForm(request.POST)
        if form.is_valid():
            payment_data = form.cleaned_data
            with transaction.atomic():
                student = Student.objects.select_for_update().select_related(
                    'current_class',
                ).get(pk=student.pk)
                applicable_fee_structures = list(
                    student.get_applicable_fee_structures(),
                )
                if not applicable_fee_structures and student.get_fee_balance() <= 0:
                    form.add_error(
                        None,
                        'No active fee structure is configured for this studentâ€™s class and academic year.',
                    )
                    return render(request, 'bursar/record_payment.html', {
                        'student': student,
                        'form': form,
                        'payments': FeePayment.objects.filter(
                            student=student,
                        ).select_related('fee_structure', 'recorded_by_bursar__user'),
                        'total_paid': student.get_total_paid_fees(),
                        'total_fee_due': student.get_total_invoiced_fees(),
                        'fee_balance': student.get_fee_balance(),
                        'fee_structures': applicable_fee_structures,
                    })
                payment_fee_structure = (
                    applicable_fee_structures[0]
                    if len(applicable_fee_structures) == 1
                    else None
                )
                if payment_data['amount'] <= 0:
                    form.add_error('amount', 'Payment amount must be greater than zero.')
                elif payment_data['amount'] > student.get_fee_balance():
                    form.add_error('amount', 'Payment cannot exceed the outstanding balance.')
                elif payment_data['payment_method'] == 'CASH':
                    CashPaymentApproval.objects.create(
                        student=student,
                        amount=payment_data['amount'],
                        payment_date=payment_data['payment_date'],
                        transaction_code=payment_data['transaction_code'],
                        notes=payment_data['notes'],
                        fee_structure=payment_fee_structure,
                        recorded_by=request.user.bursar_profile,
                    )
                    messages.success(request, 'Cash payment submitted for headteacher approval. The student balance has not changed yet.')
                    return redirect('fee_records')
                else:
                    resulting_balance = student.get_fee_balance() - payment_data['amount']
                    payment = FeePayment.objects.create(
                        student=student,
                        fee_structure=payment_fee_structure,
                        amount=payment_data['amount'],
                        payment_date=payment_data['payment_date'],
                        payment_method=payment_data['payment_method'],
                        transaction_code=payment_data['transaction_code'],
                        recorded_by_bursar=request.user.bursar_profile,
                        notes=payment_data['notes'],
                    )
                    FeeTransaction.objects.create(
                        student=student,
                        transaction_type='PAYMENT',
                        fee_payment=payment,
                        amount=payment.amount,
                        balance=resulting_balance,
                        description=f"Payment recorded by bursar via {payment.get_payment_method_display()}",
                        date=payment.payment_date,
                    )
                    messages.success(request, 'Payment recorded successfully.')
                    return redirect('fee_records')
    else:
        form = FeePaymentForm()
    
    payments = FeePayment.objects.filter(student=student).select_related(
        'fee_structure', 'recorded_by_bursar__user',
    )
    total_paid = payments.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    
    context = {
        'student': student,
        'form': form,
        'payments': payments,
        'total_paid': total_paid,
        'total_fee_due': student.get_total_invoiced_fees(),
        'fee_balance': student.get_fee_balance(),
        'fee_structures': student.get_applicable_fee_structures(),
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
        'balance': school_cash_balance(),
        'total_students': total_students,
    }
    return render(request, 'bursar/payment_reports.html', context)
