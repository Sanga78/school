from django.http import HttpResponse,JsonResponse,HttpResponseRedirect
from django.core import serializers
from django.shortcuts import render
from index.models import Courses, CustomUser, FeedbackStaff, NotificationStaff, Staffs, StudentResult, Subjects,SessionYearModel,Students,Attendance,AttendanceReport,LeaveReportStaff
from django.views.decorators.csrf import csrf_exempt
from django.urls import reverse
from django.contrib import messages
import json
def staff_home(request):
    # for fetching all student under staff
    subjects = Subjects.objects.filter(staff_id=request.user.id)
    course_id_list=[]
    for subject in subjects:
        course=Courses.objects.get(id=subject.course_id.id)
        course_id_list.append(course.id)
    # Removing Duplicate Course IDs
    final_course=[]
    for course_id in course_id_list:
        if course_id not in final_course:
            final_course.append(course_id)

    student_count=Students.objects.filter(course_id__in=final_course).count()

    # Fetch All Attendance Count
    attendance_count=Attendance.objects.filter(subject_id__in=subjects).count()

    # Fetch All Approved Leave
    staff=Staffs.objects.get(admin=request.user.id)
    leave_count=LeaveReportStaff.objects.filter(staff_id=staff.id,leave_status=1).count()
    subject_count=subjects.count()

    #Fetch Attendance Data By Subject
    subject_list=[]
    attendance_list=[]
    for subject in subjects:
        attendance_count1= Attendance.objects.filter(subject_id=subject).count()
        subject_list.append(subject.subject_name)
        attendance_list.append(attendance_count1)

    student_attendance=Students.objects.filter(course_id__in=final_course)
    student_list = []
    student_list_attendance_present = []
    student_list_attendance_absent = []
    for student in student_attendance:
        attendance_present_count=AttendanceReport.objects.filter(status=True,student_id=student.id).count()
        attendance_absent_count=AttendanceReport.objects.filter(status=False,student_id=student.id).count()
        student_list.append(student.admin.username)
        student_list_attendance_present.append(attendance_present_count)
        student_list_attendance_absent.append(attendance_absent_count)

    return render(request, "staff_template/staff_home.html",{"students_count":student_count,"attendance_count":attendance_count,"leave_count":leave_count,"subject_count":subject_count,"subject_list":subject_list,"attendance_list":attendance_list,"student_list":student_list,"present_list":student_list_attendance_present,"absent_list":student_list_attendance_absent})

def staff_take_attendance(request):
    subjects = Subjects.objects.filter(staff_id=request.user.id)
    session_years = SessionYearModel.object.all()
    return render(request,"staff_template/attendance.html",{"subjects":subjects,"session_years":session_years})

@csrf_exempt
def get_students(request):
    subject_id = request.POST.get("subject")
    session_year = request.POST.get("session_year")

    subject = Subjects.objects.get(id=subject_id)
    session_model = SessionYearModel.object.get(id=session_year)
    students = Students.objects.filter(course_id=subject.course_id,session_year_id=session_model)
    list_data=[]

    for student in students:
        data_small = {"id":student.admin.id,"name":student.admin.first_name+" "+student.admin.last_name}
        list_data.append(data_small)
    return JsonResponse(json.dumps(list_data),content_type="application/json",safe=False)

@csrf_exempt
def save_attendance_data(request):
    student_ids = request.POST.get("student_ids")
    subject_id = request.POST.get("subject_id")
    session_year_id = request.POST.get("session_year_id")
    attendance_date = request.POST.get("attendance_date")
    subject_model = Subjects.objects.get(id=subject_id)
    session_model = SessionYearModel.object.get(id=session_year_id)

    json_sstudent=json.loads(student_ids)
    # print(json_sstudent[0]['id'])

    try:
        attendance = Attendance(subject_id=subject_model,attendance_date=attendance_date,session_year_id=session_model)
        attendance.save()

        for stud in json_sstudent:
            student = Students.objects.get(admin=stud['id'])
            attendance_report=AttendanceReport(student_id=student,attendance_id=attendance,status=stud['status'])
            attendance_report.save()
        return HttpResponse("OK")
    except:
        return HttpResponse("ERROR")
    
def staff_update_attendance(request):
    subjects = Subjects.objects.filter(staff_id=request.user.id)
    session_year_id = SessionYearModel.object.all()
    return render(request,"staff_template/attendance_update.html",{"subjects":subjects,"session_year_id":session_year_id})

@csrf_exempt
def get_attendance_dates(request):
    subject = request.POST.get("subject")
    session_year_id = request.POST.get("session_year_id")
    subject_obj = Subjects.objects.get(id=subject)
    session_year_obj = SessionYearModel.object.get(id=session_year_id)
    attendance = Attendance.objects.filter(subject_id=subject_obj,session_year_id=session_year_obj)
    attendance_obj=[]
    for attendance_single in attendance:
        data={"id":attendance_single.id,"attendance_date":str(attendance_single.attendance_date),"session_year_id":attendance_single.session_year_id.id}
        attendance_obj.append(data)

    return JsonResponse(json.dumps(attendance_obj),safe=False)

@csrf_exempt
def get_attendance_student(request):
    attendance_date = request.POST.get("attendance_date")
    attendace = Attendance.objects.get(id=attendance_date)

    attendance_data = AttendanceReport.objects.filter(attendance_id=attendace)

    list_data=[]

    for student in attendance_data:
        data_small = {"id":student.student_id.admin.id,"name":student.student_id.admin.first_name+" "+student.student_id.admin.last_name,"status":student.status}
        list_data.append(data_small)
    return JsonResponse(json.dumps(list_data),content_type="application/json",safe=False)

@csrf_exempt
def save_updateattendance_data(request):
    student_ids = request.POST.get("student_ids")
    attendance_date = request.POST.get("attendance_date")
    attendance = Attendance.objects.get(id=attendance_date)

    json_sstudent=json.loads(student_ids)

    try:
        for stud in json_sstudent:
            student = Students.objects.get(admin=stud['id'])
            attendance_report=AttendanceReport.objects.get(student_id=student,attendance_id=attendance)
            attendance_report.status=stud['status']
            attendance_report.save()
        return HttpResponse("OK")
    except:
        return HttpResponse("ERROR")
    
def staff_apply_leave(request):
    staff_obj = Staffs.objects.get(admin=request.user.id)
    leave_data = LeaveReportStaff.objects.filter(staff_id=staff_obj)
    return render(request,'staff_template/staff_apply_leave.html',{"leave_data":leave_data})

def staff_apply_leave_save(request):
    if request.method!="POST":
        return HttpResponseRedirect(reverse("staff_apply_leave"))
    else:
        leave_date = request.POST.get('leave_date')
        leave_msg = request.POST.get('leave_reason')

        staff_obj = Staffs.objects.get(admin=request.user.id)
        try:
            leave_report = LeaveReportStaff(staff_id=staff_obj,leave_date=leave_date,leave_message=leave_msg,leave_status=0)
            leave_report.save()
            messages.success(request,"Successfully Applied for Leave")
            return HttpResponseRedirect(reverse("staff_apply_leave"))
        except:
            messages.error(request,"Failed to Apply for Leave")
            return HttpResponseRedirect(reverse("staff_apply_leave"))

def staff_feedback(request):
    staff_obj = Staffs.objects.get(admin=request.user.id)
    feedback_data = FeedbackStaff.objects.filter(staff_id=staff_obj)
    return render(request,'staff_template/staff_feedback.html',{"feedback_data":feedback_data})

def staff_feedback_save(request):
    if request.method!="POST":
        return HttpResponseRedirect(reverse("staff_feedback_save"))
    else:
        feedback_msg = request.POST.get('feedback_msg')

        staff_obj = Staffs.objects.get(admin=request.user.id)
        try:
            feedback = FeedbackStaff(staff_id=staff_obj,feedback=feedback_msg,feedback_reply="")
            feedback.save()
            messages.success(request,"Successfully Sent Feedback")
            return HttpResponseRedirect(reverse("staff_feedback"))
        except:
            messages.error(request,"Failed to Send Feedback")
            return HttpResponseRedirect(reverse("staff_feedback"))

def staff_profile(request):
    user = CustomUser.objects.get(id=request.user.id)
    staff = Staffs.objects.get(admin=user)
    return render(request,"staff_template/staff_profile.html",{"user":user,"staff":staff})

def staff_profile_save(request):
    if request.method != "POST":
        return HttpResponseRedirect(reverse("staff_profile"))
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

            staff=Staffs.objects.get(id=customuser.id)
            staff.address = address
            staff.save()
            messages.success(request,"Successfully Updated Profile")
            return HttpResponseRedirect(reverse("staff_profile"))
        except:
            messages.error(request,"Failed to Update Profile")
            return HttpResponseRedirect(reverse("staff_profile"))

@csrf_exempt        
def staff_fcmtoken_save(request):
    token = request.POST.get("token")
    try:
        staff=Staffs.objects.get(admin=request.user.id)
        staff.fcm_token=token
        staff.save()
        return HttpResponse("True")
    except:
        return HttpResponse("False")
    
def staff_all_notifications(request):
    staff=Staffs.objects.get(admin=request.user.id)
    notifications=NotificationStaff.objects.filter(staff_id=staff.id)
    return render(request,"staff_template/all_notifications.html",{"notifications":notifications})

def staff_add_result(request):
    subjects=Subjects.objects.filter(staff_id=request.user.id)
    session_year=SessionYearModel.object.all()
    return render(request,"staff_template/staff_add_result.html",{"subjects":subjects,"session_years":session_year})

def save_student_result(request):
    if request.method != "POST":
        return HttpResponseRedirect("staff_add_result")
    else:
        student_admin_id=request.POST.get("student_list")
        assignment_marks=request.POST.get("assignment_marks")
        exam_marks=request.POST.get("exam_marks")
        subject_id=request.POST.get("subject")
        student_obj=Students.objects.get(admin=student_admin_id)
        subject_obj=Subjects.objects.get(id=subject_id)
        try:
            check_exist=StudentResult.objects.filter(student_id=student_obj,subject_id=subject_obj).exists()
            if check_exist:
                result=StudentResult.objects.get(student_id=student_obj,subject_id=subject_obj)
                result.subject_assignment_marks=assignment_marks 
                result.subject_exam_marks=exam_marks
                result.save()
                messages.success(request,"Successfully Updated Result")
                return HttpResponseRedirect(reverse("staff_add_result"))
            else:
                result=StudentResult(student_id=student_obj,subject_id=subject_obj,subject_exam_marks=exam_marks,subject_assignment_marks=assignment_marks)
                result.save()
                messages.success(request,"Successfully Added Result")
                return HttpResponseRedirect(reverse("staff_add_result"))
        except:
            messages.error(request,"Failed to Add Result")
            return HttpResponseRedirect(reverse("staff_add_result"))

@csrf_exempt       
def fetch_student_result(request):
    subject_id=request.POST.get('subject_id')
    student_id=request.POST.get('student_id')
    student_obj=Students.objects.get(admin=student_id)
    result=StudentResult.objects.filter(student_id=student_obj.id,subject_id=subject_id).exists()
    if result:
        result=StudentResult.objects.get(student_id=student_obj.id,subject_id=subject_id)
        result_data={"exam_marks":result.subject_exam_marks,"assignment_marks":result.subject_assignment_marks}
        return HttpResponse(json.dumps(result_data))
    else:
        return HttpResponse("False")

