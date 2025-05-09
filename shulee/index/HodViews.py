import json
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse,HttpResponseRedirect, JsonResponse
from django.contrib import messages
from django.core.files.storage import FileSystemStorage
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q, Count, Sum
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.template.loader import render_to_string
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
from reportlab.lib import colors
import csv
import os
from xhtml2pdf import pisa
from datetime import datetime
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, Spacer

from .models import (
    Bursar, Class,CustomUser, Expense, FeePayment, Notification, Subject, Staff, Student,
    Attendance, AttendanceReport, 
    LeaveRequest, Feedback,SessionYearModel,
    AcademicYear,StaffSubjectAssignment, SystemLog,
)
from .forms import (
    SystemSettingsForm,
    LeaveResponseForm, 
    AddSubjectForm, AddStudentForm,
    AddAdministratorForm, AddBursarForm,
    ClassForm, NotificationForm, StaffForm, 
    StaffSubjectAssignmentForm, ClassTeacherAssignmentForm,
    EditStudentForm
)

User = get_user_model()
# Helper function to check if user is admin
def is_admin(user):
    return user.user_type == 1
def admin_check(user):
    return user.is_authenticated and user.user_type == 1

@login_required
@user_passes_test(admin_check)
def admin_dashboard(request):
    return render(request, 'admin/admin_dashboard.html')

@login_required
@user_passes_test(admin_check)
def manage_teachers(request):
    teachers = Staff.objects.all()
    context = {
        'teachers': teachers,
    }
    return render(request, 'admin/manage_teachers.html', context)

@login_required
@user_passes_test(admin_check)
def add_teacher(request):
    subjects = Subject.objects.all()
    if request.method == 'POST':
        form = StaffForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, 'Teacher added successfully!')
            return redirect('manage_teachers')
    else:
        form = StaffForm()
    
    context = {
        'form': form,
        'subjects':subjects,
    }
    return render(request, 'admin/add_teacher.html', context)

@login_required
@user_passes_test(admin_check)
def assign_subjects(request, teacher_id):
    teacher = Staff.objects.get(id=teacher_id)
    
    if request.method == 'POST':
        form = StaffSubjectAssignmentForm(request.POST)
        if form.is_valid():
            assignment = form.save(commit=False)
            assignment.staff = teacher
            assignment.save()
            form.save_m2m()  # Save the many-to-many relationship for classes
            messages.success(request, 'Subject assignment added successfully!')
            return redirect('teacher_subjects', teacher_id=teacher.id)
    else:
        form = StaffSubjectAssignmentForm()
    
    current_assignments = teacher.staffsubjectassignment_set.all()
    
    context = {
        'teacher': teacher,
        'form': form,
        'current_assignments': current_assignments,
    }
    return render(request, 'admin/assign_subjects.html', context)

@login_required
@user_passes_test(admin_check)
def teacher_subjects(request, teacher_id):
    teacher = Staff.objects.get(id=teacher_id)
    assignments = teacher.staffsubjectassignment_set.all()
    
    context = {
        'teacher': teacher,
        'assignments': assignments,
    }
    return render(request, 'admin/teacher_subjects.html', context)

@login_required
@user_passes_test(admin_check)
def assign_class_teachers(request):
    classes = Class.objects.all()
    
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
@user_passes_test(admin_check)
def remove_subject_assignment(request, assignment_id):
    assignment = StaffSubjectAssignment.objects.get(id=assignment_id)
    teacher_id = assignment.staff.id
    assignment.delete()
    messages.success(request, 'Subject assignment removed successfully!')
    return redirect('teacher_subjects', teacher_id=teacher_id)

def admin_home(request):
    student_count=Student.objects.all().count()
    staff_count=Staff.objects.all().count()
    subject_count=Subject.objects.all().count()

    subject_count_list=[]


    subjects_all=Subject.objects.all() 
    subjects_list=[]
    student_count_list_in_subject=[]
    for subject in subjects_all:
        student_count=Student.objects.count()
        subjects_list.append(subject.subject_name)
        student_count_list_in_subject.append(student_count)
    
    staffs=Staff.objects.all()
    attendance_present_list_staff=[]
    attendance_absent_list_staff=[]
    staff_name_list=[]
    for staff in staffs:
        subject_ids=Subject.objects.filter(staff_id=staff.admin.id)
        attendance=Attendance.objects.filter(subject_id__in=subject_ids).count()
        leaves= LeaveRequest.objects.filter(staff_id=staff.id,leave_status=1).count()
        attendance_absent_list_staff.append(leaves)
        attendance_present_list_staff.append(attendance)
        staff_name_list.append(staff.admin.username)

    students_all=Student.objects.all()
    attendance_present_list_student=[]
    attendance_absent_list_student=[]
    student_name_list=[]
    for student in students_all:
        attendance=AttendanceReport.objects.filter(student_id=student.id,status=True).count()
        absent=AttendanceReport.objects.filter(student_id=student.id,status=False).count()
        leaves= LeaveRequest.objects.filter(student_id=student.id,leave_status=1).count()
        attendance_absent_list_student.append(leaves+absent)
        attendance_present_list_student.append(attendance)
        student_name_list.append(student.admin.username)

    return render(request, "hod_templates/home.html",{"student_count":student_count,"staff_count":staff_count,"subject_count":subject_count,"subject_count_list":subject_count_list,"student_count_list_in_subject":student_count_list_in_subject,"subjects_list":subjects_list,"staff_name_list":staff_name_list,"attendance_absent_list_staff":attendance_absent_list_staff,"attendance_present_list_staff":attendance_present_list_staff,"student_name_list":student_name_list,"attendance_absent_list_student":attendance_absent_list_student,"attendance_present_list_student":attendance_present_list_student})

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
    
        
def add_student(request):
    form = AddStudentForm()
    return render(request,"hod_templates/add_student.html",{"form":form})

def add_student_save(request):
    if request.method != "POST":
        return HttpResponse("Method Not Allowed")
    else:
        form = AddStudentForm(request.POST,request.FILES)
        if form.is_valid():
            first_name = form.cleaned_data["first_name"]
            last_name = form.cleaned_data["last_name"]
            username = form.cleaned_data["username"]
            email = form.cleaned_data["email"] 
            password = form.cleaned_data["password"]
            address = form.cleaned_data["address"]
            session_year_id = form.cleaned_data["session_year_id"]
            sex = form.cleaned_data["sex"]

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
                messages.success(request,"Successfully added student")
                return HttpResponseRedirect(reverse("add_student"))
            except:
                messages.error(request,"Failed to Add student")
                return HttpResponseRedirect(reverse("add_student"))
        else:
            form=AddStudentForm(request.POST)
            return render(request,"hod_templates/add_student.html",{"form":form})

def add_subject(request):
    staffs = CustomUser.objects.filter(user_type=2)
    return render(request, 'hod_templates/add_subject.html',{"staffs":staffs})

def add_subject_save(request):
    if request.method != 'POST':
        return HttpResponseRedirect("Method Not Allowed")
    else:
        subject_name = request.POST.get("subject_name")
        staff_id = request.POST.get("staff")
        staff = CustomUser.objects.get(id=staff_id)
        try:
            subject = Subject(subject_name=subject_name,staff_id=staff)
            subject.save()
            messages.success(request,"Successfully Added Subject")
            return HttpResponseRedirect(reverse("add_subject"))
        except:
            messages.error(request,"Failed to Add Subject")
            return HttpResponseRedirect(reverse("add_subject"))
 
def manage_staff(request):
    staffs=Staff.objects.all()
    return render(request,"hod_templates/manage_staff.html",{"staffs":staffs})

# def manage_student(request):
#     students=Student.objects.all()
#     return render(request,"hod_templates/manage_student.html",{"students":students})


def manage_subject(request):
    subjects=Subject.objects.all()
    return render(request,"admin/manage_subjects.html",{"subjects":subjects})

def edit_staff(request,staff_id):
    staff=Staff.objects.get(admin=staff_id)
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

            staff_model = Staff.objects.get(admin=staff_id)
            staff_model.address=address
            staff_model.save() 
            messages.success(request,"Successfully Edited Staff")
            return HttpResponseRedirect(reverse("edit_staff",kwargs={"staff_id":staff_id}))
        except:
            messages.error(request,"Failed to Edit Staff")
            return HttpResponseRedirect(reverse("edit_staff",kwargs={"staff_id":staff_id}))
    
def edit_student(request,student_id):
    request.session['student_id']=student_id
    student=Student.objects.get(admin=student_id)
    form = EditStudentForm()
    form.fields['email'].initial=student.admin.email
    form.fields['first_name'].initial=student.admin.first_name
    form.fields['last_name'].initial=student.admin.last_name
    form.fields['username'].initial=student.admin.username
    form.fields['address'].initial=student.address
    form.fields['sex'].initial=student.gender
    form.fields['session_year_id'].initial=student.session_year_id.id
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
            first_name = form.cleaned_data["first_name"]
            last_name = form.cleaned_data["last_name"]
            username = form.cleaned_data["username"]
            email = form.cleaned_data["email"] 
            address = form.cleaned_data["address"]
            session_year_id = form.cleaned_data["session_year_id"]
            sex = form.cleaned_data["sex"]

            if request.FILES.get('profile_pic',False):
                profile_pic = request.FILES('profile_pic')
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

                student = Student.objects.get(admin=student_id)
                student.address=address
                session_year =SessionYearModel.object.get(id=session_year_id)
                student.session_year_id = session_year
                student.gender=sex
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
            student = Student.objects.get(admin=student_id)
            return render(request,"hod_templates/edit_student.html",{"form":form,"id":student_id,"username":student.admin.username})
        


def edit_subject(request,subject_id):
    subject=Subject.objects.get(id=subject_id)
    staffs = CustomUser.objects.filter(user_type=2)
    return render(request,"hod_templates/edit_subject.html",{"subject":subject,"staffs":staffs,"id":subject_id})

def edit_subject_save(request):
    if request.method != 'POST':
        return HttpResponseRedirect("Method Not Allowed")
    else:
        subject_id = request.POST.get("subject_id")
        subject_name = request.POST.get("subject_name")
        staff_id = request.POST.get("staff")
        try:
            subject = Subject.objects.get(id=subject_id)
            staff = CustomUser.objects.get(id=staff_id)
            subject.staff_id = staff
            subject.subject_name = subject_name
            subject.save()
            messages.success(request,"Successfully Edited Subject")
            return HttpResponseRedirect(reverse("edit_subject",kwargs={"subject_id":subject_id}))
        except:
            messages.error(request,"Failed to Edit Subject")
            return HttpResponseRedirect(reverse("edit_subject",kwargs={"subject_id":subject_id}))

def manage_session(request):
   return render(request,"hod_templates/manage_session.html")

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

@csrf_exempt     
def check_email_exist(request):
    email=request.POST.get("email")
    user_obj=CustomUser.objects.filter(email=email).exists()
    if user_obj:
        return HttpResponse(True)
    else:
        return HttpResponse(False)
    
@csrf_exempt     
def check_username_exist(request):
    username=request.POST.get("username")
    user_obj=CustomUser.objects.filter(username=username).exists()
    if user_obj:
        return HttpResponse(True)
    else:
        return HttpResponse(False)
    
def staff_feedback_message(request):
    feedbacks=Feedback.objects.all()
    return render(request,"hod_templates/staff_feedback.html",{"feedbacks":feedbacks})

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
    
def student_feedback_message(request):
    feedbacks=Feedback.objects.all()
    return render(request,"hod_templates/student_feedback.html",{"feedbacks":feedbacks})

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
    
def student_leave_view(request):
    leaves =  LeaveRequest.objects.all()
    return render(request,"hod_templates/student_leave_view.html",{"leaves":leaves})

def student_approve_leave(request,leave_id):
    leave= LeaveRequest.objects.get(id=leave_id)
    leave.leave_status=1
    leave.save()
    return HttpResponseRedirect(reverse("student_leave_view"))

def student_disapprove_leave(request,leave_id):
    leave= LeaveRequest.objects.get(id=leave_id)
    leave.leave_status=2
    leave.save()
    return HttpResponseRedirect(reverse("student_leave_view"))

def staff_leave_view(request):
    leaves =  LeaveRequest.objects.all()
    return render(request,"hod_templates/staff_leave_view.html",{"leaves":leaves})

def staff_approve_leave(request,leave_id):
    leave= LeaveRequest.objects.get(id=leave_id)
    leave.leave_status=1
    leave.save()
    return HttpResponseRedirect(reverse("staff_leave_view"))

def staff_disapprove_leave(request,leave_id):
    leave= LeaveRequest.objects.get(id=leave_id)
    leave.leave_status=2
    leave.save()    
    return HttpResponseRedirect(reverse("staff_leave_view"))

def admin_view_atendance(request):
    subjects = Subject.objects.all()
    session_year_id = SessionYearModel.object.all()
    return render(request,"hod_templates/admin_view_attendance.html",{"subjects":subjects,"session_year_id":session_year_id})


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

def admin_profile(request):
    user = CustomUser.objects.get(id=request.user.id)
    return render(request,"hod_templates/admin_profile.html",{"user":user})

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



def manage_classes(request):
    classes = Class.objects.select_related('academic_year', 'class_teacher').all()
    return render(request, 'admin/manage_classes.html', {'classes': classes})

def add_class(request):
    if request.method == 'POST':
        form = ClassForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('manage_classes')
    else:
        form = ClassForm()
    return render(request, 'admin/add_edit_class.html', {'form': form})

def edit_class(request, class_id):
    class_obj = get_object_or_404(Class, id=class_id)
    if request.method == 'POST':
        form = ClassForm(request.POST, instance=class_obj)
        if form.is_valid():
            form.save()
            return redirect('manage_classes')
    else:
        form = ClassForm(instance=class_obj)
    return render(request, 'admin/add_edit_class.html', {'form': form, 'class': class_obj})

def delete_class(request, class_id):
    class_obj = get_object_or_404(Class, id=class_id)
    if request.method == 'POST':
        class_obj.delete()
        return redirect('manage_classes')
    return render(request, 'admin/confirm_delete.html', {'object': class_obj})


@login_required
@user_passes_test(is_admin)
def admin_dashboard(request):
    stats = {
        'students_count': Student.objects.count(),
        'teachers_count': Staff.objects.count(),
        'classes_count': Class.objects.count(),
        'pending_requests': LeaveRequest.objects.filter(status=0).count()
    }
    
    recent_activities = []  # Add your recent activities logic here
    
    context = {
        'stats': stats,
        'recent_activities': recent_activities
    }
    return render(request, 'admin/admin_dashboard.html', context)

# Attendance Management
@login_required
@user_passes_test(is_admin)
def manage_attendance(request):
    classes = Class.objects.all()
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
            search_query = request.GET.get('search')
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
            # Save settings logic here
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
    
    class_filter = request.GET.get('class')
    if class_filter:
        students = students.filter(current_class_id=class_filter)
    
    search_query = request.GET.get('search')
    if search_query:
        students = students.filter(
            Q(user__first_name__icontains=search_query) |
            Q(user__last_name__icontains=search_query) |
            Q(admission_number__icontains=search_query)
        )
    
    classes = Class.objects.all()
    
    context = {
        'students': students,
        'classes': classes,
        'class_filter': int(class_filter) if class_filter else None,
        'search_query': search_query or ''
    }
    return render(request, 'admin/manage_students.html', context)

@login_required
@user_passes_test(is_admin)
def add_student(request):
    if request.method == 'POST':
        form = AddStudentForm(request.POST, request.FILES)
        if form.is_valid():
            student = form.save(commit=False)
            student.user.user_type = 3  # Set as student
            student.user.save()
            student.save()
            messages.success(request, 'Student added successfully!')
            return redirect('manage_students')
    else:
        form = AddStudentForm()
    
    context = {'form': form}
    return render(request, 'admin/add_edit_student.html', context)

@login_required
@user_passes_test(is_admin)
def edit_student(request, student_id):
    student = get_object_or_404(Student, id=student_id)
    if request.method == 'POST':
        form = AddStudentForm(request.POST, request.FILES, instance=student)
        if form.is_valid():
            form.save()
            messages.success(request, 'Student updated successfully!')
            return redirect('manage_students')
    else:
        form = AddStudentForm(instance=student)
    
    context = {'form': form, 'student': student}
    return render(request, 'admin/add_edit_student.html', context)

@login_required
@user_passes_test(is_admin)
def view_student(request, student_id):
    student = get_object_or_404(Student.objects.select_related(
        'user', 'current_class', 'academic_year'
    ), id=student_id)
    
    context = {'student': student}
    return render(request, 'admin/view_student.html', context)


@login_required
@user_passes_test(is_admin)
def manage_finance(request):
    # Summary statistics
    total_fees = FeePayment.objects.aggregate(total=Sum('amount'))['total'] or 0
    total_expenses = Expense.objects.aggregate(total=Sum('amount'))['total'] or 0
    balance = total_fees - total_expenses
    
    # Recent transactions
    recent_payments = FeePayment.objects.select_related(
        'student', 'student__user', 'fee_structure'
    ).order_by('-payment_date')[:5]
    
    recent_expenses = Expense.objects.select_related(
        'bursar', 'approved_by'
    ).order_by('-date')[:5]
    
    context = {
        'total_fees': total_fees,
        'total_expenses': total_expenses,
        'balance': balance,
        'recent_payments': recent_payments,
        'recent_expenses': recent_expenses
    }
    return render(request, 'admin/manage_finance.html', context)

@login_required
@user_passes_test(is_admin)
def fee_payments(request):
    payments = FeePayment.objects.select_related(
        'student', 'student__user', 'fee_structure', 'received_by'
    ).order_by('-payment_date')
    
    student_filter = request.GET.get('student')
    if student_filter:
        payments = payments.filter(student_id=student_filter)
    
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    if date_from and date_to:
        payments = payments.filter(payment_date__range=[date_from, date_to])
    
    students = Student.objects.all()
    
    context = {
        'payments': payments,
        'students': students,
        'student_filter': student_filter,
        'date_from': date_from,
        'date_to': date_to
    }
    return render(request, 'admin/fee_payments.html', context)

@login_required
@user_passes_test(is_admin)
def expenses(request):
    expenses = Expense.objects.select_related(
        'bursar', 'approved_by'
    ).order_by('-date')
    
    category_filter = request.GET.get('category')
    if category_filter:
        expenses = expenses.filter(category=category_filter)
    
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    if date_from and date_to:
        expenses = expenses.filter(date__range=[date_from, date_to])
    
    context = {
        'expenses': expenses,
        'category_filter': category_filter,
        'date_from': date_from,
        'date_to': date_to
    }
    return render(request, 'admin/expenses.html', context)

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
    bursars = User.objects.filter(user_type=4).order_by('last_name')
    context = {'bursars': bursars}
    return render(request, 'admin/manage_bursars.html', context)

@login_required
@user_passes_test(is_admin)
def add_bursar(request):
    if request.method == 'POST':
        form = AddBursarForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save(commit=False)
            user.user_type = 4  # Bursar
            user.username = form.cleaned_data['email']
            user.set_password(form.cleaned_data['password'])
            user.save()
            
            # Create staff profile for bursar
            Bursar.objects.create(user=user)
            
            messages.success(request, 'Bursar added successfully!')
            return redirect('manage_bursars')
    else:
        form = AddBursarForm()
    
    context = {'form': form}
    return render(request, 'admin/add_bursar.html', context)

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

# Subject Management
@login_required
@user_passes_test(is_admin)
def add_subject(request):
    if request.method == 'POST':
        form = AddSubjectForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Subject added successfully!')
            return redirect('manage_subject')
    else:
        form = AddSubjectForm()
    
    context = {'form': form}
    return render(request, 'admin/add_subject.html', context)

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
                student.admission_number,
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
                student.admission_number,
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
    
    classes = Class.objects.all()
    return render(request, 'admin/attendance_report_form.html', {'classes': classes})

@login_required
@user_passes_test(is_admin)
def generate_finance_report(request):
    if request.method == 'POST':
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        
        payments = FeePayment.objects.filter(
            payment_date__range=[start_date, end_date]
        )
        expenses = Expense.objects.filter(
            date__range=[start_date, end_date]
        )
        
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = 'finance_report.pdf'
        
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        
        styles = getSampleStyleSheet()
        story = []
        
        # Title
        story.append(Paragraph(
            f"Financial Report ({start_date} to {end_date})", 
            styles['Title']
        ))
        story.append(Spacer(1, 0.25*inch))
        
        # Summary Data
        story.append(Paragraph("Summary", styles['Heading2']))
        data = [
            ['Total Payments', payments.aggregate(Sum('amount'))['amount__sum'] or 0],
            ['Total Expenses', expenses.aggregate(Sum('amount'))['amount__sum'] or 0],
            ['Balance', (payments.aggregate(Sum('amount'))['amount__sum'] or 0) - 
                      (expenses.aggregate(Sum('amount'))['amount__sum'] or 0)]
        ]
        
        t = Table(data, colWidths=[2*inch, 2*inch])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
            ('GRID', (0,0), (-1,-1), 1, colors.black)
        ]))
        story.append(t)
        
        doc.build(story)
        pdf = buffer.getvalue()
        buffer.close()
        response.write(pdf)
        return response
    
    return render(request, 'admin/finance_report_form.html')

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
            AcademicYear.objects.create(
                name=name,
                start_date=start_date,
                end_date=end_date
            )
            messages.success(request, 'Academic year added successfully!')
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
    user = bursar.user
    
    if request.method == 'POST':
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        gender = request.POST.get('gender')
        qualification = request.POST.get('qualification')
        date_of_joining = request.POST.get('date_of_joining')
        is_active = request.POST.get('is_active') == 'on'
        
        try:
            user.first_name = first_name
            user.last_name = last_name
            user.email = email
            user.phone = phone
            user.is_active = is_active
            user.save()
            
            bursar.gender = gender
            bursar.qualification = qualification
            bursar.date_of_joining = date_of_joining
            bursar.save()
            
            messages.success(request, 'Bursar updated successfully!')
            return redirect('manage_bursars')
        except Exception as e:
            messages.error(request, f'Error updating bursar: {str(e)}')
    
    context = {
        'bursar': bursar,
        'user': user
    }
    return render(request, 'admin/edit_bursar.html', context)

@login_required
@user_passes_test(is_admin)
def deactivate_bursar(request, bursar_id):
    bursar = get_object_or_404(Bursar, id=bursar_id)
    
    if request.method == 'POST':
        try:
            user = bursar.user
            user.is_active = False
            user.save()
            messages.success(request, 'Bursar deactivated successfully!')
        except Exception as e:
            messages.error(request, f'Error deactivating bursar: {str(e)}')
        
        return redirect('manage_bursars')
    
    context = {
        'bursar': bursar
    }
    return render(request, 'admin/confirm_deactivate.html', context)
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