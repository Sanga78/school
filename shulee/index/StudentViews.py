import datetime
from django.contrib import messages
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt

from .forms import FeePaymentForm
from .models import Attendance, AttendanceReport, CustomUser, FeePayment, FeeStructure, LeaveRequest, FeeTransaction, Feedback, Notification, SubjectResult, Student, Subject
from django.contrib.auth.decorators import login_required
from django.db import models
from django.utils import timezone

def student_home(request):
    student_obj=Student.objects.get(admin=request.user.id)
    attendance_total = AttendanceReport.objects.filter(student_id=student_obj).count()
    attendance_present = AttendanceReport.objects.filter(student_id=student_obj,status=True).count()
    attendance_absent = AttendanceReport.objects.filter(student_id=student_obj,status=False).count()
    attendance_absent = AttendanceReport.objects.filter(student_id=student_obj,status=False).count()
    subjects = Subject.objects.count()

    subject_name=[]
    data_present=[]
    data_absent=[]
    subject_data=Subject.objects.all()
    for subject in subject_data:
        attendance=Attendance.objects.filter(subject_id=subject.id)
        attendance_present_count=AttendanceReport.objects.filter(attendance_id__in=attendance,status=True,student_id=student_obj.id).count()
        attendance_absent_count=AttendanceReport.objects.filter(attendance_id__in=attendance,status=False,student_id=student_obj.id).count()
        subject_name.append(subject.subject_name)
        data_present.append(attendance_present_count)
        data_absent.append(attendance_absent_count)

    return render(request, "student_template/student_home.html",{"total_attendance":attendance_total,"attendance_present":attendance_present,"attendance_absent":attendance_absent,"subjects":subjects,"data_name":subject_name,"data1":data_present,"data2":data_absent})

def student_view_attendance(request):
    students=Student.objects.get(admin=request.user.id)
    subjects = Subject.objects.all()
    return render(request,"student_template/student_view_attendance.html",{"subjects":subjects})

def student_view_attendance_post(request):
    subject_id=request.POST.get("subject")
    start_date=request.POST.get("start_date")
    end_date=request.POST.get("end_date")

    start_date_parse=datetime.datetime.strptime(start_date,"%Y-%m-%d").date()
    end_date_parse=datetime.datetime.strptime(end_date,"%Y-%m-%d").date()
    subject_obj=Subject.objects.get(id=subject_id)
    user_obj=CustomUser.objects.get(id=request.user.id)
    stud_obj=Student.objects.get(admin=user_obj)

    attendance=Attendance.objects.filter(attendance_date__range=(start_date_parse,end_date_parse),subject_id=subject_obj)
    attendance_reports=AttendanceReport.objects.filter(attendance_id__in=attendance,student_id=stud_obj)

    return render(request,"student_template/student_attendance_data.html",{"attendance_reports":attendance_reports})

def student_apply_leave(request):
    student_obj = Student.objects.get(admin=request.user.id)
    leave_data =  LeaveRequest.objects.filter(student_id=student_obj)
    return render(request,'student_template/student_apply_leave.html',{"leave_data":leave_data})

def student_apply_leave_save(request):
    if request.method!="POST":
        return HttpResponseRedirect(reverse("student_apply_leave"))
    else:
        leave_date = request.POST.get('leave_date')
        leave_msg = request.POST.get('leave_reason')

        student_obj = Student.objects.get(admin=request.user.id)
        try:
            leave_report = LeaveRequest(student_id=student_obj,leave_date=leave_date,leave_message=leave_msg,leave_status=0)
            leave_report.save()
            messages.success(request,"Successfully Applied for Leave")
            return HttpResponseRedirect(reverse("student_apply_leave"))
        except:
            messages.error(request,"Failed to Apply for Leave")
            return HttpResponseRedirect(reverse("student_apply_leave"))

def student_feedback(request):
    student_obj = Student.objects.get(admin=request.user.id)
    feedback_data = Feedback.objects.filter(student_id=student_obj)
    return render(request,'student_template/student_feedback.html',{"feedback_data":feedback_data})

def student_feedback_save(request):
    if request.method!="POST":
        return HttpResponseRedirect(reverse("student_feedback_save"))
    else:
        feedback_msg = request.POST.get('feedback_msg')

        student_obj =Student.objects.get(admin=request.user.id)
        try:
            feedback = Feedback(student_id=student_obj,feedback=feedback_msg,feedback_reply="")
            feedback.save()
            messages.success(request,"Successfully Sent Feedback")
            return HttpResponseRedirect(reverse("student_feedback"))
        except:
            messages.error(request,"Failed to Send Feedback")
            return HttpResponseRedirect(reverse("student_feedback"))

def student_profile(request):
    user = CustomUser.objects.get(id=request.user.id)
    student =Student.objects.get(admin=user)
    return render(request,"student_template/student_profile.html",{"user":user,"student":student})

def student_profile_save(request):
    if request.method != "POST":
        return HttpResponseRedirect(reverse("student_profile"))
    else:
        first_name=request.POST.get("first_name")
        last_name=request.POST.get("last_name")
        address=request.POST.get("address")
        password=request.POST.get("password")
        try:
            customuser=CustomUser.objects.get(id=request.user.id)
            customuser.first_name=first_name
            customuser.last_name=last_name
            if password!=None and password!="":
                customuser.set_password(password)
            customuser.save()

            student=Student.objects.get(admin=customuser)
            student.address = address
            student.save()
            messages.success(request,"Successfully Updated Profile")
            return HttpResponseRedirect(reverse("student_profile"))
        except:
            messages.error(request,"Failed to Update Profile")
            return HttpResponseRedirect(reverse("student_profile"))

@csrf_exempt        
def student_fcmtoken_save(request):
    token = request.POST.get("token")
    try:
        student=Student.objects.get(admin=request.user.id)
        student.fcm_token=token
        student.save()
        return HttpResponse("True")
    except:
        return HttpResponse("False")
    
def student_all_notifications(request):
    student =Student.objects.get(admin=request.user.id)
    notifications = Notification.objects.filter(student_id=student.id)
    return render(request,'student_template/all_notifications.html',{"notifications":notifications})

def student_view_result(request):
    student =Student.objects.get(admin=request.user.id)
    studentresult = SubjectResult.objects.all()
    return render(request,"student_template/student_result.html",{"studentresult":studentresult})

@login_required
def student_fee_statement(request):
    # Get the logged in student
    student = request.user.students
    
    # Get all fee transactions for this student
    fee_transactions = FeeTransaction.objects.filter(student_id=student).order_by('-date', '-created_at')
    
    # Calculate summary statistics
    total_invoices = fee_transactions.filter(transaction_type='INVOICE').aggregate(
        total=models.Sum('amount')
    )['total'] or 0
    
    total_payments = fee_transactions.filter(transaction_type='PAYMENT').aggregate(
        total=models.Sum('amount')
    )['total'] or 0
    
    context = {
        'fee_transactions': fee_transactions,
        'fee_balance': student.get_fee_balance(),
        'total_invoices': total_invoices,
        'total_payments': total_payments,
        'current_date': timezone.now().date(),
    }
    return render(request, 'student_template/fee_statement.html', context)

@login_required
def student_fee_payments(request):
    student = request.user.students
    
    # Get all payments for this student
    fee_payments = FeePayment.objects.filter(student_id=student).order_by('-payment_date')
    
    context = {
        'fee_payments': fee_payments,
        'fee_balance': student.get_fee_balance(),
    }
    return render(request, 'student_template/fee_payments.html', context)

@login_required
def student_fee_balance(request):
    student = request.user.students
    
    # Get fee balance and recent transactions
    recent_transactions = FeeTransaction.objects.filter(
        student_id=student
    ).order_by('-date', '-created_at')[:5]
    
    # Get upcoming fee dues
    upcoming_fees = FeeStructure.objects.filter(
        session_year_id=student.session_year_id,
        is_active=True,
        due_date__gte=timezone.now().date()
    ).order_by('due_date')
    
    context = {
        'fee_balance': student.get_fee_balance(),
        'recent_transactions': recent_transactions,
        'upcoming_fees': upcoming_fees,
    }
    return render(request, 'student_template/fee_balance.html', context)

@login_required
def make_fee_payment(request):
    student = request.user.students
    
    if request.method == 'POST':
        form = FeePaymentForm(request.POST)
        if form.is_valid():
            payment = form.save(commit=False)
            payment.student_id = student
            payment.save()
            
            # Create corresponding transaction
            current_balance = student.get_fee_balance()
            new_balance = current_balance - payment.amount
            
            FeeTransaction.objects.create(
                student_id=student,
                transaction_type='PAYMENT',
                fee_payment_id=payment,
                amount=payment.amount,
                balance=new_balance,
                description=f"Payment via {payment.get_payment_method_display()}",
                date=payment.payment_date
            )
            
            messages.success(request, 'Payment recorded successfully!')
            return HttpResponseRedirect('student_fee_payments')
    else:
        form = FeePaymentForm()
    
    context = {
        'form': form,
        'fee_balance': student.get_fee_balance(),
    }
    return render(request, 'student_template/make_payment.html', context)