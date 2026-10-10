import json
import re
from decimal import Decimal, InvalidOperation, ROUND_FLOOR
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db import models
from django.db.models import Exists, OuterRef, Sum
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .forms import StudentProfileForm
from .models import (
    AcademicYear,
    CashPaymentApproval,
    FeePayment,
    FeeTransaction,
    Feedback,
    MpesaPayment,
    Notification,
    NotificationReadStatus,
    ResultPublication,
    Student,
    StudentApplication,
    SubjectResult,
)
from .mpesa import MpesaError, initiate_stk_push, query_stk_push


def student_required(view_func):
    @login_required(login_url='show_login')
    @wraps(view_func)
    def wrapped_view(request, *args, **kwargs):
        if request.user.user_type != 3:
            raise PermissionDenied
        student = Student.objects.filter(user_id=request.user.pk).only('id', 'active').first()
        if student is None:
            raise PermissionDenied
        if not student.active:
            if StudentApplication.objects.filter(student_id=student.pk).exists():
                return redirect('student_application_status')
            raise PermissionDenied
        return view_func(request, *args, **kwargs)

    return wrapped_view


@login_required(login_url='show_login')
def student_application_status(request):
    if request.user.user_type != 3:
        raise PermissionDenied
    application = get_object_or_404(
        StudentApplication.objects.select_related(
            'student__user',
            'student__current_class',
            'student__academic_year',
        ),
        student__user_id=request.user.pk,
    )
    student = application.student
    if student.active:
        return redirect('student_home')
    return render(request, 'student_template/application_status.html', {
        'student': student,
        'application': application,
    })


def _student_for_user(user):
    return get_object_or_404(
        Student.objects.select_related(
            'user',
            'current_class',
            'current_class__class_teacher__user',
            'academic_year',
        ),
        user=user,
        active=True,
    )


def _fee_balance(student):
    return student.get_fee_balance()


def _unread_result_notifications(user):
    notifications = list(
        Notification.objects.filter(
            recipients=user,
            title='Results are available online',
        ).exclude(
            read_statuses__user=user,
        ).order_by('-created_at')[:10]
    )
    for notification in notifications:
        NotificationReadStatus.objects.get_or_create(
            notification=notification,
            user=user,
        )
    return notifications


@student_required
def student_home(request):
    student = _student_for_user(request.user)
    approved_publications = ResultPublication.objects.filter(
        class_obj_id=OuterRef('student__current_class_id'),
        academic_year_id=OuterRef('academic_year_id'),
        term=OuterRef('term'),
        status='APPROVED',
    )
    results = list(
        SubjectResult.objects.filter(student=student)
        .filter(Exists(approved_publications))
        .select_related('subject', 'academic_year')
        .order_by('academic_year__start_date', 'term', 'subject__name')
    )
    progress_by_term = {}
    for result in results:
        key = (result.academic_year.name, result.term)
        progress_by_term.setdefault(key, []).append(
            (result.exam_score + result.assignment_score) / Decimal('2')
        )
    term_labels = [f'{year} · {term.replace("_", " ").title()}' for year, term in progress_by_term]
    term_scores = [
        round(float(sum(scores) / len(scores)), 2)
        for scores in progress_by_term.values()
    ]
    term_progress = [
        {'label': label, 'score': score}
        for label, score in zip(term_labels, term_scores)
    ]

    fee_total = FeeTransaction.objects.filter(student=student).aggregate(
        payments=Sum('amount', filter=models.Q(transaction_type='PAYMENT')),
    )
    recent_results = results[-5:][::-1]

    return render(request, 'student_template/student_home.html', {
        'student': student,
        'results': recent_results,
        'result_count': len(results),
        'term_labels': term_labels,
        'term_scores': term_scores,
        'term_progress': term_progress,
        'fee_balance': _fee_balance(student),
        'total_paid': fee_total['payments'] or Decimal('0.00'),
        'teacher': student.current_class.class_teacher if student.current_class else None,
        'result_notifications': _unread_result_notifications(request.user),
        'progress_data': {
            'labels': term_labels,
            'scores': term_scores,
        },
    })


@student_required
def student_feedback(request):
    student = _student_for_user(request.user)
    teacher = student.current_class.class_teacher if student.current_class else None
    return render(request, 'student_template/student_feedback.html', {
        'feedback_data': Feedback.objects.filter(user=request.user).select_related('recipient_staff__user'),
        'class_teacher': teacher,
        'student': student,
    })


@student_required
@require_POST
def student_feedback_save(request):
    student = _student_for_user(request.user)
    teacher = student.current_class.class_teacher if student.current_class else None
    message = request.POST.get('feedback_msg', '').strip()
    if teacher is None:
        messages.error(request, 'Your class does not currently have an assigned teacher.')
    elif not message:
        messages.error(request, 'Enter a message before sending it to your class teacher.')
    else:
        Feedback.objects.create(
            user=request.user,
            recipient_staff=teacher,
            message=message,
        )
        messages.success(request, 'Your message was sent to your class teacher.')
    return redirect('student_feedback')


@student_required
def student_profile(request):
    student = _student_for_user(request.user)
    return render(request, 'student_template/student_profile.html', {
        'user': request.user,
        'student': student,
        'form': StudentProfileForm(instance=request.user),
    })


@student_required
@require_POST
def student_profile_save(request):
    form = StudentProfileForm(request.POST, instance=request.user)
    if form.is_valid():
        form.save()
        messages.success(request, 'Your profile was updated.')
    else:
        messages.error(request, 'Please correct the highlighted profile fields.')
    return redirect('student_profile')


@student_required
def student_view_result(request):
    student = _student_for_user(request.user)
    approved_publications = ResultPublication.objects.filter(
        class_obj_id=OuterRef('student__current_class_id'),
        academic_year_id=OuterRef('academic_year_id'),
        term=OuterRef('term'),
        status='APPROVED',
    )
    results = SubjectResult.objects.filter(student=student).select_related(
        'subject',
        'academic_year',
        'created_by__user',
    ).filter(
        Exists(approved_publications),
    ).order_by('-academic_year__start_date', 'term', 'subject__name')
    return render(request, 'student_template/student_result.html', {
        'studentresult': results,
        'student': student,
        'result_notifications': _unread_result_notifications(request.user),
    })


@student_required
def student_fee_statement(request):
    student = _student_for_user(request.user)
    fee_transactions = FeeTransaction.objects.filter(
        student=student,
    ).select_related('fee_structure').order_by('-date', '-created_at')
    return render(request, 'student_template/fee_statement.html', {
        'fee_transactions': fee_transactions,
        'fee_structures': student.get_applicable_fee_structures(),
        'fee_balance': student.get_fee_balance(),
        'total_invoices': student.get_total_invoiced_fees(),
        'total_payments': student.get_total_paid_fees(),
        'current_date': timezone.localdate(),
        'student': student,
    })


@student_required
def student_fee_payments(request):
    student = _student_for_user(request.user)
    mpesa_payments = MpesaPayment.objects.filter(student=student)
    cash_requests = CashPaymentApproval.objects.filter(student=student, status='APPROVED')
    mpesa_receipts = mpesa_payments.filter(
        receipt_number__isnull=False,
    ).exclude(receipt_number='').values_list('receipt_number', flat=True)
    fee_payments = FeePayment.objects.filter(student=student).exclude(
        cash_approval__isnull=False,
    ).exclude(
        payment_method='MPESA',
        transaction_code__in=mpesa_receipts,
    )

    payment_history = [
        {
            'date': payment.payment_date,
            'sort_date': payment.created_at,
            'amount': payment.amount,
            'method': payment.get_payment_method_display(),
            'reference': payment.transaction_code,
            'status': 'Paid',
            'status_class': 'success',
        }
        for payment in fee_payments
    ]
    for payment in mpesa_payments:
        status_classes = {
            'PAID': 'success',
            'PENDING': 'warning',
            'FAILED': 'danger',
        }
        payment_history.append({
            'date': payment.created_at,
            'sort_date': payment.created_at,
            'amount': payment.amount,
            'method': 'M-Pesa',
            'reference': payment.receipt_number,
            'status': payment.get_status_display(),
            'status_class': status_classes[payment.status],
        })
    for payment in cash_requests:
        status_classes = {
            'APPROVED': 'success',
            'PENDING': 'warning',
            'REJECTED': 'danger',
        }
        payment_history.append({
            'date': payment.created_at,
            'sort_date': payment.created_at,
            'amount': payment.amount,
            'method': 'Cash',
            'reference': payment.transaction_code,
            'status': payment.get_status_display(),
            'status_class': status_classes[payment.status],
        })
    payment_history.sort(key=lambda payment: payment['sort_date'], reverse=True)

    return render(request, 'student_template/fee_payments.html', {
        'payment_history': payment_history,
        'fee_balance': _fee_balance(student),
        'student': student,
    })


@student_required
def make_fee_payment(request):
    student = _student_for_user(request.user)
    if request.method == 'POST':
        amount_raw = request.POST.get('amount', '')
        phone_raw = request.POST.get('phone_number', '').strip()
        try:
            amount = Decimal(amount_raw)
        except (InvalidOperation, TypeError):
            amount = Decimal('0')

        if not amount.is_finite() or amount <= 0:
            messages.error(request, 'Enter a valid payment amount greater than zero.')
        elif amount != amount.to_integral_value():
            messages.error(request, 'M-Pesa STK payments must be in whole Kenyan shillings.')
        else:
            phone = re.sub(r'\D', '', phone_raw)
            if phone.startswith('0') and len(phone) == 10:
                phone = f'254{phone[1:]}'
            elif phone.startswith('7') or phone.startswith('1'):
                phone = f'254{phone}'
            if not re.fullmatch(r'254(?:7|1)\d{8}', phone):
                messages.error(request, 'Enter a valid Kenyan M-Pesa phone number.')
            else:
                with transaction.atomic():
                    student = Student.objects.select_for_update().get(pk=student.pk)
                    available_balance = student.get_available_fee_balance()
                    if amount > available_balance:
                        messages.error(
                            request,
                            'Payment cannot exceed the outstanding balance available after pending payments '
                            f'(Ksh {available_balance:.2f}).',
                        )
                    else:
                        class_name = student.current_class.name if student.current_class else ''
                        account_reference = f'{request.user.get_full_name()} {class_name}'.strip()
                        account_reference = re.sub(r'[^A-Za-z0-9]', '', account_reference)[:12] or 'SCHOOLFEES'
                        try:
                            response = initiate_stk_push(
                                phone_number=phone,
                                amount=int(amount),
                                account_reference=account_reference,
                                transaction_desc=f'School fee {class_name}',
                            )
                        except MpesaError as error:
                            messages.error(request, str(error))
                        else:
                            MpesaPayment.objects.create(
                                student=student,
                                amount=amount,
                                phone_number=phone,
                                account_reference=account_reference,
                                merchant_request_id=response['MerchantRequestID'],
                                checkout_request_id=response['CheckoutRequestID'],
                            )
                            messages.success(request, 'Check your phone and approve the M-Pesa payment prompt. Your balance updates after confirmation.')
                            return redirect('student_fee_payments')

    available_balance = student.get_available_fee_balance()
    return render(request, 'student_template/make_payment.html', {
        'fee_balance': _fee_balance(student),
        'payment_limit': available_balance.to_integral_value(rounding=ROUND_FLOOR),
        'student': student,
        'default_phone': request.user.phone,
    })


@csrf_exempt
@require_POST
def mpesa_stk_callback(request):
    try:
        payload = json.loads(request.body)
        callback = payload['Body']['stkCallback']
        checkout_id = callback['CheckoutRequestID']
        result_code = int(callback['ResultCode'])
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        return JsonResponse({'error': 'Invalid M-Pesa callback.'}, status=400)

    payment = get_object_or_404(MpesaPayment, checkout_request_id=checkout_id)
    if payment.status != 'PENDING':
        return JsonResponse({'ResultCode': 0, 'ResultDesc': 'Callback already processed.'})

    if result_code != 0:
        with transaction.atomic():
            payment = MpesaPayment.objects.select_for_update().get(pk=payment.pk)
            if payment.status == 'PENDING':
                payment.status = 'FAILED'
                payment.result_description = str(
                    callback.get('ResultDesc') or 'M-Pesa payment was not completed.'
                )[:255]
                payment.save(update_fields=['status', 'result_description', 'updated_at'])
        return JsonResponse({'ResultCode': 0, 'ResultDesc': 'No successful payment to record.'})
    if callback.get('MerchantRequestID') != payment.merchant_request_id:
        return JsonResponse({'error': 'M-Pesa request identifiers did not match.'}, status=400)

    try:
        verification = query_stk_push(checkout_id)
    except MpesaError:
        return JsonResponse({'error': 'Payment verification is temporarily unavailable.'}, status=503)
    if str(verification.get('ResultCode')) != '0':
        return JsonResponse({'ResultCode': 0, 'ResultDesc': 'Payment is not yet confirmed.'})

    metadata = callback.get('CallbackMetadata', {}).get('Item', [])
    metadata_values = {
        item.get('Name'): item.get('Value')
        for item in metadata
        if isinstance(item, dict)
    }
    receipt_number = metadata_values.get('MpesaReceiptNumber')
    confirmed_amount = metadata_values.get('Amount')
    try:
        amount_matches = Decimal(str(confirmed_amount)) == payment.amount
    except (InvalidOperation, TypeError, ValueError):
        amount_matches = False
    if not receipt_number or not amount_matches:
        return JsonResponse({'error': 'Provider confirmation did not match the payment.'}, status=400)

    with transaction.atomic():
        payment = MpesaPayment.objects.select_for_update().get(pk=payment.pk)
        if payment.status == 'PAID':
            return JsonResponse({'ResultCode': 0, 'ResultDesc': 'Payment already recorded.'})
        if FeePayment.objects.filter(transaction_code=receipt_number).exists():
            return JsonResponse({'error': 'M-Pesa receipt was already used.'}, status=409)
        student = Student.objects.select_for_update().get(pk=payment.student_id)
        fee_structures = list(student.get_applicable_fee_structures())
        payment_fee_structure = fee_structures[0] if len(fee_structures) == 1 else None
        resulting_balance = student.get_fee_balance() - payment.amount
        fee_payment = FeePayment.objects.create(
            student=student,
            fee_structure=payment_fee_structure,
            amount=payment.amount,
            payment_date=timezone.localdate(),
            payment_method='MPESA',
            transaction_code=receipt_number,
            notes='Confirmed by M-Pesa STK Push.',
        )
        FeeTransaction.objects.create(
            student=student,
            transaction_type='PAYMENT',
            fee_payment=fee_payment,
            amount=payment.amount,
            balance=resulting_balance,
            description=f'Confirmed M-Pesa payment {receipt_number}',
        )
        payment.status = 'PAID'
        payment.receipt_number = receipt_number
        payment.result_description = 'Payment verified with M-Pesa.'
        payment.save(update_fields=['status', 'receipt_number', 'result_description', 'updated_at'])

    return JsonResponse({'ResultCode': 0, 'ResultDesc': 'Payment confirmed and recorded.'})
