import json
from functools import wraps
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from django.core.exceptions import PermissionDenied
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse,HttpResponseRedirect, JsonResponse
from django.contrib import messages
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.db.models import Q, Count, Sum
from django.contrib.auth import get_user_model
from django.template.loader import render_to_string
from django.utils import timezone
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
from reportlab.lib import colors
from django.db import IntegrityError, transaction # For atomic operations
import csv
import os
from xhtml2pdf import pisa
from datetime import datetime

from .models import (
    Bursar, CashPaymentApproval, StudentApplication, StudentClass,CustomUser, Expense, FeePayment, FeeTransaction, Notification, Subject, Staff, Student, STANDARD_CLASS_NAMES,
    Attendance, AttendanceReport, 
    LeaveRequest, Feedback,SessionYearModel,
    AcademicYear,StaffSubjectAssignment, SystemLog, ResultPublication,
    SubjectResult, SubjectResultSubmission,
)
from .forms import (
    StudentForm,
    EditBursarForm,
    SystemSettingsForm,
    LeaveResponseForm, 
    AddAdministratorForm, AddBursarForm,
    NotificationForm, StaffForm,
    StaffSubjectAssignmentForm, ClassTeacherAssignmentForm, ClassForm,
    StudentApplicationReviewForm,
)

User = get_user_model()
# Helper function to check if user is admin
def is_admin(user):
    return user.is_authenticated and user.user_type == 1


def is_bursar(user):
    return (
        user.is_authenticated
        and user.is_active
        and user.user_type == 4
        and hasattr(user, 'bursar_profile')
    )


def bursar_required(view_func):
    @login_required
    @wraps(view_func)
    def wrapped_view(request, *args, **kwargs):
        if not is_bursar(request.user):
            raise PermissionDenied
        return view_func(request, *args, **kwargs)
    return wrapped_view

@login_required
@user_passes_test(is_admin)
def manage_teachers(request):
    teachers = Staff.objects.select_related('user').order_by(
        'user__last_name', 'user__first_name',
    )
    context = {
        'teachers': teachers,
    }
    return render(request, 'admin/manage_teachers.html', context)

@login_required
@user_passes_test(is_admin)
def add_teacher(request):
    if request.method == 'POST':
        form = StaffForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, 'Teacher added successfully!')
            return redirect('manage_teachers')
    else:
        form = StaffForm()
    return render(request, 'admin/add_edit_teacher.html', {'form': form})

@login_required
@user_passes_test(is_admin)
def assign_subjects(request, teacher_id):
    teacher = get_object_or_404(Staff, id=teacher_id)
    
    if request.method == 'POST':
        form = StaffSubjectAssignmentForm(request.POST, staff=teacher)
        if form.is_valid():
            assignment = form.save(commit=False)
            assignment.staff = teacher
            assignment.save()
            form.save_m2m()  # Save the many-to-many relationship for classes
            messages.success(request, 'Subject assignment added successfully!')
            return redirect('teacher_subjects', teacher_id=teacher.id)
    else:
        form = StaffSubjectAssignmentForm(staff=teacher)
    
    current_assignments = teacher.staffsubjectassignment_set.all()
    
    context = {
        'teacher': teacher,
        'form': form,
        'current_assignments': current_assignments,
    }
    return render(request, 'admin/assign_subjects.html', context)

@login_required
@user_passes_test(is_admin)
def teacher_subjects(request, teacher_id):
    teacher = get_object_or_404(Staff, id=teacher_id)
    assignments = teacher.staffsubjectassignment_set.select_related(
        'subject', 'academic_year',
    ).prefetch_related('classes')
    
    context = {
        'teacher': teacher,
        'assignments': assignments,
    }
    return render(request, 'admin/teacher_subjects.html', context)

@login_required
@user_passes_test(is_admin)
def assign_class_teachers(request):
    classes = StudentClass.objects.all()
    
    if request.method == 'POST':
        form = ClassTeacherAssignmentForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Class teacher assigned successfully!')
            return redirect('assign_class_teachers')
    else:
        form = ClassTeacherAssignmentForm()
    
    context = {
        'classes': classes,
        'form': form,
    }
    return render(request, 'admin/assign_class_teachers.html', context)

@login_required
@user_passes_test(is_admin)
@require_POST
def remove_subject_assignment(request, assignment_id):
    assignment = get_object_or_404(StaffSubjectAssignment, id=assignment_id)
    teacher_id = assignment.staff.id
    assignment.delete()
    messages.success(request, 'Subject assignment removed successfully!')
    return redirect('teacher_subjects', teacher_id=teacher_id)

@login_required
@user_passes_test(is_admin)
def admin_home(request):
    return redirect('admin_dashboard')

@login_required
@user_passes_test(is_admin)
def add_staff(request):
    return render(request,"hod_templates/add_staff.html")

@login_required
@user_passes_test(is_admin)
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
    
@login_required
@user_passes_test(is_admin)
def manage_staff(request):
    staffs=Staff.objects.all()
    return render(request,"hod_templates/manage_staff.html",{"staffs":staffs})

# def manage_student(request):
#     students=Student.objects.all()
#     return render(request,"hod_templates/manage_student.html",{"students":students})


@login_required
@user_passes_test(is_admin)
def edit_staff(request,staff_id):
    staff=Staff.objects.get(admin=staff_id)
    return render(request,"hod_templates/edit_staff.html",{"staff":staff,"id":staff_id})

@login_required
@user_passes_test(is_admin)
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

            staff_model = Staff.objects.get(admin=staff_id)
            staff_model.address=address
            staff_model.save() 
            messages.success(request,"Successfully Edited Staff")
            return HttpResponseRedirect(reverse("edit_staff",kwargs={"staff_id":staff_id}))
        except:
            messages.error(request,"Failed to Edit Staff")
            return HttpResponseRedirect(reverse("edit_staff",kwargs={"staff_id":staff_id}))

@login_required
@user_passes_test(is_admin)
def manage_session(request):
   return render(request,"hod_templates/manage_session.html")

@login_required
@user_passes_test(is_admin)
def add_session_save(request):
    if request.method != 'POST':
        return HttpResponseRedirect(reverse("manage_session"))
    else:
        session_start_year = request.POST.get("session_start")
        session_end_year = request.POST.get("session_end")

        try:
            sessionyear = SessionYearModel(session_start_year=session_start_year,session_end_year=session_end_year)
            sessionyear.save()
            messages.success(request,"Successfully Added Session")
            return HttpResponseRedirect(reverse("manage_session"))
        except:
            messages.error(request,"Failed to Add session")
            return HttpResponseRedirect(reverse("manage_session"))

@login_required
@user_passes_test(is_admin)
@csrf_exempt
def check_email_exist(request):
    email=request.POST.get("email")
    user_obj=CustomUser.objects.filter(email=email).exists()
    if user_obj:
        return HttpResponse(True)
    else:
        return HttpResponse(False)
    
@login_required
@user_passes_test(is_admin)
@csrf_exempt
def check_username_exist(request):
    username=request.POST.get("username")
    user_obj=CustomUser.objects.filter(username=username).exists()
    if user_obj:
        return HttpResponse(True)
    else:
        return HttpResponse(False)
    
@login_required
@user_passes_test(is_admin)
def staff_feedback_message(request):
    feedbacks=Feedback.objects.all()
    return render(request,"hod_templates/staff_feedback.html",{"feedbacks":feedbacks})

@login_required
@user_passes_test(is_admin)
@csrf_exempt
def staff_feedback_message_replied(request):
    feedback_id = request.POST.get("id")
    feedback_message = request.POST.get("message")
    
    try:
        feedback = Feedback.objects.get(id=feedback_id)
        feedback.feedback_reply = feedback_message
        feedback.save()
        return HttpResponse("True")
    except:
        return HttpResponse("False")
    
@login_required
@user_passes_test(is_admin)
def student_feedback_message(request):
    feedbacks=Feedback.objects.all()
    return render(request,"hod_templates/student_feedback.html",{"feedbacks":feedbacks})

@login_required
@user_passes_test(is_admin)
@csrf_exempt
def student_feedback_message_replied(request):
    feedback_id = request.POST.get("id")
    feedback_message = request.POST.get("message")
    
    try:
        feedback = Feedback.objects.get(id=feedback_id)
        feedback.feedback_reply = feedback_message
        feedback.save()
        return HttpResponse("True")
    except:
        return HttpResponse("False")
    
@login_required
@user_passes_test(is_admin)
def student_leave_view(request):
    leaves =  LeaveRequest.objects.all()
    return render(request,"hod_templates/student_leave_view.html",{"leaves":leaves})

@login_required
@user_passes_test(is_admin)
def student_approve_leave(request,leave_id):
    leave= LeaveRequest.objects.get(id=leave_id)
    leave.leave_status=1
    leave.save()
    return HttpResponseRedirect(reverse("student_leave_view"))

@login_required
@user_passes_test(is_admin)
def student_disapprove_leave(request,leave_id):
    leave= LeaveRequest.objects.get(id=leave_id)
    leave.leave_status=2
    leave.save()
    return HttpResponseRedirect(reverse("student_leave_view"))

@login_required
@user_passes_test(is_admin)
def staff_leave_view(request):
    leaves =  LeaveRequest.objects.all()
    return render(request,"hod_templates/staff_leave_view.html",{"leaves":leaves})

@login_required
@user_passes_test(is_admin)
def staff_approve_leave(request,leave_id):
    leave= LeaveRequest.objects.get(id=leave_id)
    leave.leave_status=1
    leave.save()
    return HttpResponseRedirect(reverse("staff_leave_view"))

@login_required
@user_passes_test(is_admin)
def staff_disapprove_leave(request,leave_id):
    leave= LeaveRequest.objects.get(id=leave_id)
    leave.leave_status=2
    leave.save()    
    return HttpResponseRedirect(reverse("staff_leave_view"))

@login_required
@user_passes_test(is_admin)
def admin_view_atendance(request):
    subjects = Subject.objects.all()
    session_year_id = SessionYearModel.object.all()
    return render(request,"hod_templates/admin_view_attendance.html",{"subjects":subjects,"session_year_id":session_year_id})


@login_required
@user_passes_test(is_admin)
@csrf_exempt
def admin_get_attendance_dates(request):
    subject = request.POST.get("subject")
    session_year_id = request.POST.get("session_year_id")
    subject_obj = Subject.objects.get(id=subject)
    session_year_obj = SessionYearModel.object.get(id=session_year_id)
    attendance = Attendance.objects.filter(subject_id=subject_obj,session_year_id=session_year_obj)
    attendance_obj=[]
    for attendance_single in attendance:
        data={"id":attendance_single.id,"attendance_date":str(attendance_single.attendance_date),"session_year_id":attendance_single.session_year_id.id}
        attendance_obj.append(data)

    return JsonResponse(json.dumps(attendance_obj),safe=False)

@login_required
@user_passes_test(is_admin)
@csrf_exempt
def admin_get_attendance_student(request):
    attendance_date = request.POST.get("attendance_date")
    attendace = Attendance.objects.get(id=attendance_date)

    attendance_data = AttendanceReport.objects.filter(attendance_id=attendace)

    list_data=[]

    for student in attendance_data:
        data_small = {"id":student.student_id.admin.id,"name":student.student_id.admin.first_name+" "+student.student_id.admin.last_name,"status":student.status}
        list_data.append(data_small)
    return JsonResponse(json.dumps(list_data),content_type="application/json",safe=False)

@login_required
@user_passes_test(is_admin)
def admin_profile(request):
    user = CustomUser.objects.get(id=request.user.id)
    return render(request,"hod_templates/admin_profile.html",{"user":user})

@login_required
@user_passes_test(is_admin)
def admin_profile_save(request):
    if request.method != "POST":
        return HttpResponseRedirect(reverse("admin_profile"))
    else:
        first_name=request.POST.get("first_name")
        last_name=request.POST.get("last_name")
        password=request.POST.get("password")
        try:
            customuser=CustomUser.objects.get(id=request.user.id)
            customuser.first_name=first_name
            customuser.last_name=last_name
            if password!=None and password!="":
                customuser.set_password(password)
            customuser.save()
            messages.success(request,"Successfully Updated Profile")
            return HttpResponseRedirect(reverse("admin_profile"))
        except:
            messages.error(request,"Failed to Update Profile")
            return HttpResponseRedirect(reverse("admin_profile"))



@login_required
@user_passes_test(is_admin)
def manage_classes(request):
    classes = StudentClass.objects.select_related(
        'academic_year', 'class_teacher__user',
    ).annotate(student_count=Count('students')).order_by(
        'academic_year__start_date', 'name',
    )
    return render(request, 'admin/manage_classes.html', {'classes': classes})

@login_required
@user_passes_test(is_admin)
def edit_class(request, class_id):
    class_obj = get_object_or_404(StudentClass, id=class_id)
    if request.method == 'POST':
        form = ClassForm(request.POST, instance=class_obj)
        if form.is_valid():
            form.save()
            return redirect('manage_classes')
    else:
        form = ClassForm(instance=class_obj)
    return render(request, 'admin/add_edit_class.html', {'form': form, 'class': class_obj})

@login_required
@user_passes_test(is_admin)
def admin_dashboard(request):
    current_year = AcademicYear.objects.filter(is_current=True).first()
    stats = {
        'students_count': Student.objects.filter(active=True).count(),
        'pending_applications': StudentApplication.objects.filter(status='PENDING').count(),
        'pending_cash_payments': CashPaymentApproval.objects.filter(status='PENDING').count(),
        'interviews_scheduled': StudentApplication.objects.filter(status='INTERVIEW').count(),
        'classes_count': StudentClass.objects.filter(academic_year=current_year).count()
            if current_year else 0,
    }

    context = {
        'stats': stats,
        'current_year': current_year,
    }
    return render(request, 'admin/admin_dashboard.html', context)

# Attendance Management
@login_required
@user_passes_test(is_admin)
def manage_attendance(request):
    classes = StudentClass.objects.all()
    attendance_list = []
    search_query = ""
    
    if request.method == 'GET':
        class_id = request.GET.get('class_id')
        student_id = request.GET.get('student_id')
        date_from = request.GET.get('date_from')
        date_to = request.GET.get('date_to')
        
        filters = Q()
        
        if class_id:
            filters &= Q(class_obj_id=class_id)
        if student_id:
            filters &= Q(attendancereport__student_id=student_id)
        if date_from and date_to:
            filters &= Q(attendance_date__range=[date_from, date_to])
        
        attendance_list = Attendance.objects.filter(filters).select_related(
            'class_obj', 'subject', 'created_by'
        ).distinct().order_by('-attendance_date')
        
        if 'search' in request.GET:
            search_query = request.GET.get('search', '').strip()
            attendance_list = attendance_list.filter(
                Q(class_obj__name__icontains=search_query) |
                Q(subject__name__icontains=search_query) |
                Q(attendancereport__student__user__first_name__icontains=search_query) |
                Q(attendancereport__student__user__last_name__icontains=search_query)
            ).distinct()
    
    students = Student.objects.all() if not request.GET.get('class_id') else Student.objects.filter(
        current_class_id=request.GET.get('class_id'))
    
    context = {
        'classes': classes,
        'students': students,
        'attendance_list': attendance_list,
        'search_query': search_query,
    }
    return render(request, 'admin/manage_attendance.html', context)

@login_required
@user_passes_test(is_admin)
def view_attendance(request, attendance_id):
    attendance = get_object_or_404(Attendance, id=attendance_id)
    reports = AttendanceReport.objects.filter(attendance=attendance).select_related('student', 'student__user')
    
    context = {
        'attendance': attendance,
        'reports': reports
    }
    return render(request, 'admin/view_attendance.html', context)

# Leave Management
@login_required
@user_passes_test(is_admin)
def manage_leaves(request):
    leaves = LeaveRequest.objects.select_related(
        'applicant', 'approved_by'
    ).order_by('-start_date')
    
    status_filter = request.GET.get('status')
    if status_filter:
        leaves = leaves.filter(status=status_filter)
    
    context = {
        'leaves': leaves,
        'status_filter': status_filter
    }
    return render(request, 'admin/manage_leaves.html', context)

@login_required
@user_passes_test(is_admin)
def respond_leave(request, leave_id):
    leave = get_object_or_404(LeaveRequest, id=leave_id)
    
    if request.method == 'POST':
        form = LeaveResponseForm(request.POST, instance=leave)
        if form.is_valid():
            leave = form.save(commit=False)
            leave.approved_by = request.user
            leave.save()
            messages.success(request, 'Leave request updated successfully!')
            return redirect('manage_leaves')
    else:
        form = LeaveResponseForm(instance=leave)
    
    context = {
        'leave': leave,
        'form': form
    }
    return render(request, 'admin/respond_leave.html', context)

# Feedback Management
@login_required
@user_passes_test(is_admin)
def manage_feedback(request):
    feedback_list = Feedback.objects.select_related('user').order_by('-created_at')
    
    replied_filter = request.GET.get('replied')
    if replied_filter == '1':
        feedback_list = feedback_list.exclude(reply='')
    elif replied_filter == '0':
        feedback_list = feedback_list.filter(reply='')
    
    context = {
        'feedback_list': feedback_list,
        'replied_filter': replied_filter
    }
    return render(request, 'admin/manage_feedback.html', context)

@login_required
@user_passes_test(is_admin)
def respond_feedback(request, feedback_id):
    feedback = get_object_or_404(Feedback, id=feedback_id)
    
    if request.method == 'POST':
        reply = request.POST.get('reply')
        feedback.reply = reply
        feedback.save()
        messages.success(request, 'Reply sent successfully!')
        return redirect('manage_feedback')
    
    context = {
        'feedback': feedback
    }
    return render(request, 'admin/respond_feedback.html', context)

# Settings
@login_required
@user_passes_test(is_admin)
def settings(request):
    academic_years = AcademicYear.objects.all()
    
    if request.method == 'POST':
        if 'set_current_year' in request.POST:
            year_id = request.POST.get('academic_year')
            AcademicYear.objects.update(is_current=False)
            year = AcademicYear.objects.get(id=year_id)
            year.is_current = True
            year.save()
            messages.success(request, f'{year.name} set as current academic year!')
            return redirect('settings')
        
        form = SystemSettingsForm(request.POST, request.FILES)
        if form.is_valid():
            messages.success(request, 'Settings updated successfully!')
            return redirect('settings')
    else:
        form = SystemSettingsForm()
    
    context = {
        'academic_years': academic_years,
        'form': form
    }
    return render(request, 'admin/settings.html', context)

@login_required
@user_passes_test(is_admin)
def manage_students(request):
    students = Student.objects.select_related(
        'user', 'current_class', 'academic_year'
    ).order_by('current_class__name', 'user__last_name')
    
    class_filter = request.GET.get('class', '')
    if class_filter.isdecimal():
        class_filter = int(class_filter)
        students = students.filter(current_class_id=class_filter)
    else:
        class_filter = ''
    
    search_query = request.GET.get('search', '').strip()
    if search_query:
        students = students.filter(
            Q(user__first_name__icontains=search_query) |
            Q(user__last_name__icontains=search_query) |
            Q(user__username__icontains=search_query)
        )
    
    classes = StudentClass.objects.all()
    
    context = {
        'students': students,
        'classes': classes,
        'class_filter': class_filter,
        'search_query': search_query
    }
    return render(request, 'admin/manage_students.html', context)

@login_required
@user_passes_test(is_admin)
def view_student(request, student_id):
    student = get_object_or_404(
        Student.objects.select_related('user', 'current_class', 'academic_year'),
        id=student_id,
    )
    return render(request, 'admin/view_student.html', {'student': student})

@login_required
@user_passes_test(is_admin)
def add_student(request):
    if request.method == 'POST':
        form = StudentForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                with transaction.atomic():
                    form.save()
                messages.success(request, "Student added successfully!")
                return redirect('manage_students')
            except IntegrityError:
                messages.error(request, "Could not add the student because an account with those details already exists.")
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = StudentForm()
    context = {'form': form}
    return render(request, 'admin/add_edit_student.html', context) 

@login_required
@user_passes_test(is_admin)
def edit_student(request, student_id):
    student = get_object_or_404(Student, id=student_id)
    if request.method == 'POST':
        form = StudentForm(request.POST, request.FILES, instance=student)
        if form.is_valid():
            try:
                with transaction.atomic():
                    form.save()
                messages.success(request, "Student updated successfully!")
                return redirect('manage_students')
            except Exception as e:
                messages.error(request, f"Error updating student: {e}")
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = StudentForm(instance=student)

    context = {'form': form, 'student': student}
    return render(request, 'admin/add_edit_student.html', context)

@login_required
@user_passes_test(is_admin)
def delete_student(request, student_id):
    student = get_object_or_404(Student, id=student_id)
    if request.method == 'POST':
        try:
            user = student.user
            admission_number = user.username
            student.delete()
            user.delete()
            messages.success(request, 'Student deleted successfully!')
            SystemLog.create_log(
                action='DELETE',
                details=f'Deleted student: {user.get_full_name()} ({admission_number})',
                user=request.user,
                affected_model='Student',
                object_id=student_id
            )
        except Exception as e:
            messages.error(request, f'Error deleting student: {str(e)}')
        return redirect('manage_students')
    
    context = {
        'student': student
    }
    return render(request, 'admin/confirm_delete_student.html', context)

@login_required
@user_passes_test(is_admin)
@require_POST
def activate_student(request, student_id):
    student = get_object_or_404(Student, id=student_id)
    student.active = True
    student.save()
    messages.success(request, 'Student activated successfully!')
    return redirect('manage_students')

@login_required
@user_passes_test(is_admin)
@require_POST
def deactivate_student(request, student_id):
    student = get_object_or_404(Student, id=student_id)
    student.active = False
    student.save()
    messages.success(request, 'Student deactivated successfully!')
    return redirect('manage_students')

@bursar_required
def manage_finance(request):
    return redirect('bursar_dashboard')


@login_required
@user_passes_test(is_admin)
def review_student_applications(request):
    applications = StudentApplication.objects.select_related(
        'student__user',
        'student__current_class',
        'student__academic_year',
    ).order_by('status', '-submitted_at')
    return render(request, 'admin/student_applications.html', {
        'applications': applications,
        'review_form': StudentApplicationReviewForm(),
    })


@login_required
@user_passes_test(is_admin)
@require_POST
def review_student_application(request, application_id):
    form = StudentApplicationReviewForm(request.POST)
    if not form.is_valid():
        messages.error(request, 'Choose a valid application action and provide an interview time when scheduling.')
        return redirect('review_student_applications')

    with transaction.atomic():
        application = get_object_or_404(
            StudentApplication.objects.select_for_update().select_related('student'),
            pk=application_id,
        )
        if application.status in {'APPROVED', 'REJECTED'}:
            messages.error(request, 'This application has already received a final decision.')
            return redirect('review_student_applications')

        action = form.cleaned_data['action']
        application.review_notes = form.cleaned_data['review_notes']
        if action == 'schedule':
            application.status = 'INTERVIEW'
            application.interview_at = form.cleaned_data['interview_at']
            success_message = 'Interview scheduled for this applicant.'
        elif action == 'approve':
            application.status = 'APPROVED'
            application.student.active = True
            application.student.save(update_fields=['active'])
            success_message = 'Application approved. The student portal is now available to the applicant.'
        else:
            application.status = 'REJECTED'
            application.student.active = False
            application.student.save(update_fields=['active'])
            success_message = 'Application declined.'

        application.save(update_fields=[
            'status',
            'interview_at',
            'review_notes',
            'updated_at',
        ])

    messages.success(request, success_message)
    return redirect('review_student_applications')


@login_required
@user_passes_test(is_admin)
def review_cash_payments(request):
    pending_approvals = CashPaymentApproval.objects.filter(
        status='PENDING',
    ).select_related('student__user', 'student__current_class', 'recorded_by__user')
    reviewed_approvals = CashPaymentApproval.objects.exclude(
        status='PENDING',
    ).select_related('student__user', 'reviewed_by', 'recorded_by__user')
    return render(request, 'admin/review_cash_payments.html', {
        'pending_approvals': pending_approvals,
        'reviewed_approvals': reviewed_approvals,
        'pending_cash_payments_count': pending_approvals.count(),
    })


@login_required
@user_passes_test(is_admin)
def review_results(request):
    publications = ResultPublication.objects.filter(
        status='SUBMITTED',
    ).select_related(
        'class_obj',
        'academic_year',
        'submitted_by__user',
    ).prefetch_related('class_obj__subject_assignments__subject')
    result_notifications = Notification.objects.filter(
        title__icontains='results',
        recipients=request.user,
    ).select_related('sender').order_by('-created_at')[:20]
    return render(request, 'admin/review_results.html', {
        'publications': publications,
        'result_notifications': result_notifications,
    })


@login_required
@user_passes_test(is_admin)
@require_POST
def review_result_publication(request, publication_id):
    decision = request.POST.get('decision')
    if decision not in {'approve', 'reject'}:
        messages.error(request, 'Choose whether to publish or return these results.')
        return redirect('review_results')

    with transaction.atomic():
        publication = get_object_or_404(
            ResultPublication.objects.select_for_update().select_related(
                'class_obj',
                'academic_year',
                'submitted_by__user',
            ),
            pk=publication_id,
            status='SUBMITTED',
        )
        students = list(Student.objects.filter(
            current_class=publication.class_obj,
            academic_year=publication.academic_year,
            active=True,
        ).select_related('user'))
        required_subject_ids = set(StaffSubjectAssignment.objects.filter(
            academic_year=publication.academic_year,
            classes=publication.class_obj,
        ).values_list('subject_id', flat=True).distinct())
        submitted_subject_ids = set(SubjectResultSubmission.objects.filter(
            class_obj=publication.class_obj,
            academic_year=publication.academic_year,
            term=publication.term,
        ).values_list('subject_id', flat=True))
        complete_subject_ids = set(
            SubjectResult.objects.filter(
                student__in=students,
                academic_year=publication.academic_year,
                term=publication.term,
                subject_id__in=required_subject_ids,
            ).values('subject_id').annotate(
                student_count=Count('student_id', distinct=True),
            ).filter(student_count=len(students)).values_list('subject_id', flat=True)
        )
        complete = bool(
            students
            and required_subject_ids
            and required_subject_ids == submitted_subject_ids
            and required_subject_ids == complete_subject_ids
        )
        if decision == 'approve' and not complete:
            messages.error(
                request,
                'These results cannot be published: at least one assigned subject or active student result is missing.',
            )
            return redirect('review_results')

        publication.reviewed_by = request.user
        publication.review_note = request.POST.get('review_note', '').strip()[:255]
        publication.reviewed_at = timezone.now()
        publication.status = 'APPROVED' if decision == 'approve' else 'REJECTED'
        publication.save(update_fields=[
            'status',
            'reviewed_by',
            'review_note',
            'reviewed_at',
            'updated_at',
        ])

        if decision == 'approve':
            if students:
                notification = Notification.objects.create(
                    title='Results are available online',
                    message=(
                        f'Your {publication.get_term_display()} results for '
                        f'{publication.academic_year.name} are now available in the student portal.'
                    ),
                    sender=request.user,
                    priority='HIGH',
                )
                notification.recipients.add(*(student.user for student in students))
            messages.success(
                request,
                f'{publication.class_obj.name} results approved and published to students.',
            )
        else:
            SubjectResultSubmission.objects.filter(
                class_obj=publication.class_obj,
                academic_year=publication.academic_year,
                term=publication.term,
            ).delete()
            teacher_notification = Notification.objects.create(
                title='Class results returned for correction',
                message=(
                    f'{publication.class_obj.name} {publication.get_term_display()} results were returned '
                    f'by the headteacher. {publication.review_note}'.strip()
                ),
                sender=request.user,
                priority='HIGH',
            )
            teacher_notification.recipients.add(publication.submitted_by.user)
            messages.success(request, 'Results were returned to the class teacher for correction.')
    return redirect('review_results')


@login_required
@user_passes_test(is_admin)
@require_POST
def decide_cash_payment(request, approval_id):
    decision = request.POST.get('decision')
    if decision not in {'approve', 'reject'}:
        messages.error(request, 'Choose approve or reject.')
        return redirect('review_cash_payments')

    with transaction.atomic():
        approval = get_object_or_404(
            CashPaymentApproval.objects.select_for_update().select_related('student'),
            pk=approval_id,
            status='PENDING',
        )
        student = Student.objects.select_for_update().get(pk=approval.student_id)
        review_note = request.POST.get('review_note', '').strip()[:255]
        if decision == 'approve':
            if approval.amount > student.get_available_fee_balance(
                exclude_cash_approval_id=approval.pk,
            ):
                messages.error(request, 'This cash payment now exceeds the student balance. Reconcile the account before approving it.')
                return redirect('review_cash_payments')
            if approval.transaction_code and FeePayment.objects.filter(
                transaction_code=approval.transaction_code,
            ).exists():
                messages.error(request, 'That payment reference has already been recorded.')
                return redirect('review_cash_payments')
            resulting_balance = student.get_fee_balance() - approval.amount
            payment = FeePayment.objects.create(
                student=student,
                fee_structure=approval.fee_structure,
                amount=approval.amount,
                payment_date=approval.payment_date,
                payment_method='CASH',
                transaction_code=approval.transaction_code,
                recorded_by_bursar=approval.recorded_by,
                notes=approval.notes,
            )
            FeeTransaction.objects.create(
                student=student,
                transaction_type='PAYMENT',
                fee_payment=payment,
                amount=approval.amount,
                balance=resulting_balance,
                description=f'Cash payment approved by {request.user.get_full_name() or request.user.username}',
                date=approval.payment_date,
            )
            approval.fee_payment = payment
            approval.status = 'APPROVED'
            messages.success(request, 'Cash payment approved and added to the student ledger.')
        else:
            approval.status = 'REJECTED'
            messages.success(request, 'Cash payment request rejected.')
        approval.reviewed_by = request.user
        approval.review_note = review_note
        approval.save(update_fields=[
            'fee_payment',
            'status',
            'reviewed_by',
            'review_note',
            'updated_at',
        ])
    return redirect('review_cash_payments')

@bursar_required
def fee_payments(request):
    return redirect('payment_reports')

@bursar_required
def expenses(request):
    return redirect('expense_management')

# Administrator Management
@login_required
@user_passes_test(is_admin)
def manage_administrators(request):
    admins = User.objects.filter(user_type=1).order_by('last_name')
    context = {'admins': admins}
    return render(request, 'admin/manage_administrators.html', context)

@login_required
@user_passes_test(is_admin)
def add_administrator(request):
    if request.method == 'POST':
        form = AddAdministratorForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save(commit=False)
            user.user_type = 1  # Admin
            user.set_password(form.cleaned_data['password'])
            user.save()
            messages.success(request, 'Administrator added successfully!')
            return redirect('manage_administrators')
    else:
        form = AddAdministratorForm()
    
    context = {'form': form}
    return render(request, 'admin/add_administrator.html', context)

# Bursar Management
@login_required
@user_passes_test(is_admin)
def manage_bursars(request):
    bursars = Bursar.objects.select_related('user').order_by(
        'user__last_name', 'user__first_name',
    )
    status = request.GET.get('status')
    if status == 'active':
        bursars = bursars.filter(user__is_active=True)
    elif status == 'inactive':
        bursars = bursars.filter(user__is_active=False)
    bursars = Paginator(bursars, 20).get_page(request.GET.get('page'))
    context = {'bursars': bursars}
    return render(request, 'admin/manage_bursars.html', context)

@login_required
@user_passes_test(is_admin)
def add_bursar(request):
    if request.method == 'POST':
        form = AddBursarForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, 'Bursar added successfully!')
            return redirect('manage_bursars')
    else:
        form = AddBursarForm()
    return render(request, 'admin/add_bursar.html', {'form': form})

# Database Backup
@login_required
@user_passes_test(is_admin)
def backup_database(request):
    if request.method == 'POST':
        try:
            from django.db import connections
            from django.conf import settings
            import subprocess
            
            db_name = settings.DATABASES['default']['NAME']
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = f"backup_{timestamp}.sql"
            backup_path = os.path.join(settings.MEDIA_ROOT, 'backups', backup_file)
            
            # Create backups directory if not exists
            os.makedirs(os.path.dirname(backup_path), exist_ok=True)
            
            # Using mysqldump for MySQL (adjust for your database)
            command = f"mysqldump -u {settings.DATABASES['default']['USER']} -p{settings.DATABASES['default']['PASSWORD']} {db_name} > {backup_path}"
            subprocess.run(command, shell=True, check=True)
            
            messages.success(request, f'Database backup created successfully: {backup_file}')
            return redirect('settings')
            
        except Exception as e:
            messages.error(request, f'Backup failed: {str(e)}')
            return redirect('settings')
    
    return redirect('settings')

# System Logs
@login_required
@user_passes_test(is_admin)
def system_logs(request):
    logs = SystemLog.objects.all().order_by('-timestamp')
    
    log_type = request.GET.get('type')
    if log_type:
        logs = logs.filter(log_type=log_type)
    
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    if date_from and date_to:
        logs = logs.filter(timestamp__date__range=[date_from, date_to])
    
    context = {
        'logs': logs,
        'log_types': SystemLog.LOG_TYPE_CHOICES,
        'log_type': log_type,
        'date_from': date_from,
        'date_to': date_to
    }
    return render(request, 'admin/system_logs.html', context)

@login_required
@user_passes_test(is_admin)
def export_logs(request):
    logs = SystemLog.objects.all().order_by('-timestamp')
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="system_logs.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Timestamp', 'Type', 'User', 'Action', 'Details'])
    
    for log in logs:
        writer.writerow([
            log.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            log.get_log_type_display(),
            log.user.get_full_name() if log.user else 'System',
            log.action,
            log.details[:100]  # Limit details length
        ])
    
    return response

@login_required
@user_passes_test(is_admin)
def send_notification(request):
    if request.method == 'POST':
        form = NotificationForm(request.POST)
        if form.is_valid():
            notification = form.save(commit=False)
            notification.sender = request.user
            notification.save()
            
            # Save many-to-many relationship
            form.save_m2m()
            
            messages.success(request, 'Notification sent successfully!')
            return redirect('send_notification')
    else:
        form = NotificationForm()
    
    context = {'form': form}
    return render(request, 'admin/send_notification.html', context)

@login_required
@user_passes_test(is_admin)
def notification_history(request):
    notifications = Notification.objects.filter(
        sender=request.user
    ).prefetch_related('recipients').order_by('-created_at')
    
    context = {'notifications': notifications}
    return render(request, 'admin/notification_history.html', context)

@login_required
@user_passes_test(is_admin)
def generate_reports(request):
    context = {
        'student_count': Student.objects.count(),
        'staff_count': Staff.objects.count(),
    }
    return render(request, 'admin/generate_reports.html', context)

@login_required
@user_passes_test(is_admin)
def generate_student_report(request, report_type):
    students = Student.objects.select_related('user', 'current_class')
    
    if report_type == 'pdf':
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename=student_report.pdf'
        
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        
        # Create data for table
        data = [['Admission No', 'Full Name', 'Class', 'Gender', 'Date of Birth']]
        for student in students:
            data.append([
                student.user.username,
                student.user.get_full_name(),
                student.current_class.name if student.current_class else '',
                student.get_gender_display(),
                student.date_of_birth.strftime("%Y-%m-%d") if student.date_of_birth else ''
            ])
        
        # Create table
        table = Table(data)
        style = TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.grey),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,0), 14),
            ('BOTTOMPADDING', (0,0), (-1,0), 12),
            ('BACKGROUND', (0,1), (-1,-1), colors.beige),
            ('GRID', (0,0), (-1,-1), 1, colors.black)
        ])
        table.setStyle(style)
        
        # Build PDF
        elements = []
        elements.append(table)
        doc.build(elements)
        
        pdf = buffer.getvalue()
        buffer.close()
        response.write(pdf)
        return response
        
    elif report_type == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename=student_report.csv'
        
        writer = csv.writer(response)
        writer.writerow(['Admission No', 'Full Name', 'Class', 'Gender', 'Date of Birth'])
        
        for student in students:
            writer.writerow([
                student.user.username,
                student.user.get_full_name(),
                student.current_class.name if student.current_class else '',
                student.get_gender_display(),
                student.date_of_birth.strftime("%Y-%m-%d") if student.date_of_birth else ''
            ])
        
        return response

@login_required
@user_passes_test(is_admin)
def generate_attendance_report(request):
    if request.method == 'POST':
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        class_id = request.POST.get('class_id')
        
        attendance = Attendance.objects.filter(
            attendance_date__range=[start_date, end_date]
        )
        
        if class_id:
            attendance = attendance.filter(class_obj_id=class_id)
        
        context = {
            'attendance': attendance.select_related('class_obj', 'subject'),
            'start_date': start_date,
            'end_date': end_date,
            'date': datetime.now().strftime("%B %d, %Y")
        }
        
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attendance_report_{datetime.now().strftime("%Y%m%d")}.pdf'
        
        html = render_to_string('admin/attendance_report_pdf.html', context)
        
        # Create PDF
        pdf_status = pisa.CreatePDF(
            html,
            dest=response,
            encoding='UTF-8'
        )
        
        if pdf_status.err:
            return HttpResponse('Error generating PDF', status=500)
        return response
    
    classes = StudentClass.objects.all()
    return render(request, 'admin/attendance_report_form.html', {'classes': classes})

@bursar_required
def generate_finance_report(request):
    return redirect('payment_reports')

@login_required
@user_passes_test(is_admin)
def manage_academic_years(request):
    academic_years = AcademicYear.objects.all().order_by('-start_date')
    context = {
        'academic_years': academic_years
    }
    return render(request, 'admin/manage_academic_years.html', context)

@login_required
@user_passes_test(is_admin)
def add_academic_year(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        
        try:
            with transaction.atomic():
                academic_year = AcademicYear.objects.create(
                    name=name,
                    start_date=start_date,
                    end_date=end_date
                )
                StudentClass.objects.bulk_create([
                    StudentClass(name=class_name, academic_year=academic_year)
                    for class_name in STANDARD_CLASS_NAMES
                ])
            messages.success(request, 'Academic year and standard classes added successfully!')
            return redirect('manage_academic_years')
        except Exception as e:
            messages.error(request, f'Error adding academic year: {str(e)}')
    
    return render(request, 'admin/add_edit_academic_year.html')

@login_required
@user_passes_test(is_admin)
def edit_academic_year(request, year_id):
    academic_year = get_object_or_404(AcademicYear, id=year_id)
    
    if request.method == 'POST':
        name = request.POST.get('name')
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        is_current = request.POST.get('is_current') == 'on'
        
        try:
            academic_year.name = name
            academic_year.start_date = start_date
            academic_year.end_date = end_date
            
            # If setting as current, update all others to not current
            if is_current:
                AcademicYear.objects.exclude(id=year_id).update(is_current=False)
                academic_year.is_current = True
            
            academic_year.save()
            messages.success(request, 'Academic year updated successfully!')
            return redirect('manage_academic_years')
        except Exception as e:
            messages.error(request, f'Error updating academic year: {str(e)}')
    
    context = {
        'academic_year': academic_year
    }
    return render(request, 'admin/add_edit_academic_year.html', context)

@login_required
@user_passes_test(is_admin)
def delete_academic_year(request, year_id):
    academic_year = get_object_or_404(AcademicYear, id=year_id)
    
    if request.method == 'POST':
        try:
            academic_year.delete()
            messages.success(request, 'Academic year deleted successfully!')
        except Exception as e:
            messages.error(request, f'Error deleting academic year: {str(e)}')
        
        return redirect('manage_academic_years')
    
    context = {
        'academic_year': academic_year
    }
    return render(request, 'admin/confirm_delete.html', context)

@login_required
@user_passes_test(is_admin)
def edit_bursar(request, bursar_id):
    bursar = get_object_or_404(Bursar, id=bursar_id)
    if request.method == 'POST':
        form = EditBursarForm(request.POST, request.FILES, instance=bursar.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Bursar account updated successfully.')
            return redirect('manage_bursars')
    else:
        form = EditBursarForm(instance=bursar.user)
    return render(request, 'admin/edit_bursar.html', {'bursar': bursar, 'form': form})

@login_required
@user_passes_test(is_admin)
@require_POST
def deactivate_bursar(request, bursar_id):
    bursar = get_object_or_404(Bursar, id=bursar_id)
    user = bursar.user
    user.is_active = not user.is_active
    user.save(update_fields=['is_active'])
    state = 'activated' if user.is_active else 'deactivated'
    messages.success(request, f'Bursar account {state}.')
    return redirect('manage_bursars')
@login_required
@user_passes_test(is_admin)
def set_current_academic_year(request):
    if request.method == 'POST':
        year_id = request.POST.get('academic_year')
        
        try:
            # First set all years to inactive
            AcademicYear.objects.update(is_current=False)
            
            # Then set the selected year as current
            selected_year = AcademicYear.objects.get(id=year_id)
            selected_year.is_current = True
            selected_year.save()
            
            # Log this action
            SystemLog.create_log(
                action='CONFIG',
                details=f'Changed current academic year to {selected_year.name}',
                user=request.user,
                affected_model='AcademicYear',
                object_id=selected_year.id
            )
            
            messages.success(request, f'{selected_year.name} set as current academic year!')
        except Exception as e:
            messages.error(request, f'Error setting academic year: {str(e)}')
        
        return redirect('settings')
    return redirect('settings')


@login_required
@user_passes_test(is_admin)
def edit_teacher(request, teacher_id):
    teacher = get_object_or_404(Staff, id=teacher_id)
    if request.method == 'POST':
        form = StaffForm(request.POST, request.FILES, instance=teacher.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Teacher updated successfully!')
            return redirect('manage_teachers')
    else:
        form = StaffForm(instance=teacher.user, initial={
            'qualification': teacher.qualification,
            'date_of_joining': teacher.date_of_joining
        })
    return render(request, 'admin/add_edit_teacher.html', {'form': form, 'teacher': teacher})

@login_required
@user_passes_test(is_admin)
@require_POST
def delete_teacher(request, teacher_id):
    teacher = get_object_or_404(Staff, id=teacher_id)
    teacher.user.delete()
    messages.success(request, 'Teacher deleted successfully!')
    return redirect('manage_teachers')
