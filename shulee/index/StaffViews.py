from functools import wraps
from decimal import Decimal, InvalidOperation

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Count, Q
from django.http import Http404, HttpResponse, JsonResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render, redirect
from django.views.decorators.http import require_POST
from django.utils.dateparse import parse_date
from index.models import (
    AcademicYear,
    Attendance,
    AttendanceReport,
    CustomUser,
    Feedback,
    LeaveRequest,
    Notification,
    Staff,
    StaffSubjectAssignment,
    Student,
    StudentClass,
    Subject,
    SubjectResult,
)
from django.urls import reverse
from django.contrib import messages
import json
from django.contrib.auth.decorators import login_required
from .forms import ResultUploadForm, TeacherProfileForm


def teacher_required(view_func):
    @login_required(login_url='show_login')
    @wraps(view_func)
    def wrapped_view(request, *args, **kwargs):
        if request.user.user_type != 2 or not Staff.objects.filter(user=request.user).exists():
            raise PermissionDenied
        return view_func(request, *args, **kwargs)

    return wrapped_view


@teacher_required
def staff_home(request):
    return redirect('teacher_dashboard')


def _current_teacher_assignments(user):
    current_year = AcademicYear.objects.filter(is_current=True).first()
    if current_year is None:
        return current_year, StaffSubjectAssignment.objects.none()
    assignments = StaffSubjectAssignment.objects.filter(
        staff__user=user,
        academic_year=current_year,
    ).select_related('subject', 'academic_year').prefetch_related('classes')
    return current_year, assignments


def _required_pk(value):
    try:
        pk = int(value)
    except (TypeError, ValueError) as error:
        raise Http404 from error
    if pk < 1:
        raise Http404
    return pk


def _teacher_assignment(user, assignment_id, class_id):
    assignment_id = _required_pk(assignment_id)
    class_id = _required_pk(class_id)
    current_year = AcademicYear.objects.filter(is_current=True).first()
    if current_year is None:
        raise PermissionDenied
    assignment = get_object_or_404(
        StaffSubjectAssignment.objects.select_related('staff', 'subject', 'academic_year'),
        pk=assignment_id,
        staff__user=user,
        academic_year=current_year,
        classes__pk=class_id,
        classes__academic_year=current_year,
    )
    class_obj = get_object_or_404(
        StudentClass,
        pk=class_id,
        academic_year=current_year,
    )
    return assignment, class_obj, current_year


def _parse_attendance_statuses(raw_data, expected_ids):
    try:
        payload = json.loads(raw_data or '')
    except json.JSONDecodeError as error:
        raise ValueError('Attendance data must be valid JSON.') from error
    if not isinstance(payload, list):
        raise ValueError('Attendance data must be a list.')

    statuses = {}
    for item in payload:
        if not isinstance(item, dict) or set(item) != {'id', 'status'}:
            raise ValueError('Each attendance entry must include a student and status.')
        try:
            student_id = int(item['id'])
        except (TypeError, ValueError) as error:
            raise ValueError('Attendance includes an invalid student.') from error
        raw_status = item['status']
        if raw_status not in (0, 1, False, True, '0', '1'):
            raise ValueError('Attendance status must be present or absent.')
        if student_id in statuses:
            raise ValueError('Attendance includes a student more than once.')
        is_present = raw_status is True or raw_status == 1 or raw_status == '1'
        statuses[student_id] = 'P' if is_present else 'A'

    if set(statuses) != set(expected_ids):
        raise ValueError('Attendance must include every student in the assigned class.')
    return statuses


@teacher_required
def staff_take_attendance(request):
    current_year, assignments = _current_teacher_assignments(request.user)
    return render(request, 'staff_template/attendance.html', {
        'assignments': assignments,
        'current_year': current_year,
    })

@teacher_required
@require_POST
def get_students(request):
    assignment, class_obj, current_year = _teacher_assignment(
        request.user,
        request.POST.get('assignment_id'),
        request.POST.get('class_id'),
    )
    students = Student.objects.filter(
        current_class=class_obj,
        academic_year=current_year,
        active=True,
    ).select_related('user').order_by('user__last_name', 'user__first_name')
    return JsonResponse({
        'students': [
            {'id': student.pk, 'name': student.user.get_full_name() or student.user.username}
            for student in students
        ],
        'subject': assignment.subject.name,
        'class_name': class_obj.name,
    })

@teacher_required
@require_POST
def save_attendance_data(request):
    assignment, class_obj, current_year = _teacher_assignment(
        request.user,
        request.POST.get('assignment_id'),
        request.POST.get('class_id'),
    )
    attendance_date = parse_date(request.POST.get('attendance_date', ''))
    if attendance_date is None:
        return JsonResponse({'error': 'Enter a valid attendance date.'}, status=400)
    students = list(Student.objects.filter(
        current_class=class_obj,
        academic_year=current_year,
        active=True,
    ))
    if not students:
        return JsonResponse({'error': 'There are no active students in this assigned class.'}, status=400)
    try:
        statuses = _parse_attendance_statuses(
            request.POST.get('student_ids'),
            [student.pk for student in students],
        )
    except ValueError as error:
        return JsonResponse({'error': str(error)}, status=400)

    with transaction.atomic():
        attendance, created = Attendance.objects.get_or_create(
            subject=assignment.subject,
            class_obj=class_obj,
            academic_year=current_year,
            attendance_date=attendance_date,
            defaults={'created_by': request.user.staff_profile},
        )
        if not created:
            return JsonResponse({'error': 'Attendance has already been recorded for this class and date.'}, status=409)
        AttendanceReport.objects.bulk_create([
            AttendanceReport(
                attendance=attendance,
                student=student,
                status=statuses[student.pk],
            )
            for student in students
        ])
    return JsonResponse({'success': True})
    
@teacher_required
def staff_update_attendance(request):
    current_year, assignments = _current_teacher_assignments(request.user)
    return render(request, 'staff_template/attendance_update.html', {
        'assignments': assignments,
        'current_year': current_year,
    })

@teacher_required
@require_POST
def get_attendance_dates(request):
    assignment, class_obj, current_year = _teacher_assignment(
        request.user,
        request.POST.get('assignment_id'),
        request.POST.get('class_id'),
    )
    attendance = Attendance.objects.filter(
        subject=assignment.subject,
        class_obj=class_obj,
        academic_year=current_year,
    ).order_by('-attendance_date')
    return JsonResponse({
        'attendance': [
            {'id': row.pk, 'attendance_date': row.attendance_date.isoformat()}
            for row in attendance
        ],
    })

@teacher_required
@require_POST
def get_attendance_student(request):
    assignment, class_obj, current_year = _teacher_assignment(
        request.user,
        request.POST.get('assignment_id'),
        request.POST.get('class_id'),
    )
    attendance = get_object_or_404(
        Attendance,
        pk=_required_pk(request.POST.get('attendance_id')),
        subject=assignment.subject,
        class_obj=class_obj,
        academic_year=current_year,
    )
    reports = attendance.reports.select_related('student__user').order_by(
        'student__user__last_name',
        'student__user__first_name',
    )
    return JsonResponse({
        'students': [
            {
                'id': report.student_id,
                'name': report.student.user.get_full_name() or report.student.user.username,
                'status': report.status == 'P',
            }
            for report in reports
        ],
    })

@teacher_required
@require_POST
def save_updateattendance_data(request):
    assignment, class_obj, current_year = _teacher_assignment(
        request.user,
        request.POST.get('assignment_id'),
        request.POST.get('class_id'),
    )
    attendance = get_object_or_404(
        Attendance,
        pk=_required_pk(request.POST.get('attendance_id')),
        subject=assignment.subject,
        class_obj=class_obj,
        academic_year=current_year,
    )
    reports = list(attendance.reports.all())
    try:
        statuses = _parse_attendance_statuses(
            request.POST.get('student_ids'),
            [report.student_id for report in reports],
        )
    except ValueError as error:
        return JsonResponse({'error': str(error)}, status=400)
    for report in reports:
        report.status = statuses[report.student_id]
    AttendanceReport.objects.bulk_update(reports, ['status', 'updated_at'])
    return JsonResponse({'success': True})
    
@teacher_required
def staff_apply_leave(request):
    leave_data = LeaveRequest.objects.filter(applicant=request.user)
    return render(request, 'staff_template/staff_apply_leave.html', {'leave_data': leave_data})

@teacher_required
@require_POST
def staff_apply_leave_save(request):
    leave_type = request.POST.get('leave_type', '').strip()
    start_date = parse_date(request.POST.get('start_date', ''))
    end_date = parse_date(request.POST.get('end_date', ''))
    reason = request.POST.get('reason', '').strip()

    if not leave_type or len(leave_type) > 50 or not reason or not start_date or not end_date:
        messages.error(request, 'Enter a leave type, valid start and end dates, and a reason.')
    elif end_date < start_date:
        messages.error(request, 'The leave end date must be on or after the start date.')
    else:
        LeaveRequest.objects.create(
            applicant=request.user,
            leave_type=leave_type,
            start_date=start_date,
            end_date=end_date,
            reason=reason,
        )
        messages.success(request, 'Your leave request was submitted.')
    return redirect('staff_apply_leave')

@teacher_required
def staff_feedback(request):
    feedback_data = Feedback.objects.filter(user=request.user)
    return render(request, 'staff_template/staff_feedback.html', {'feedback_data': feedback_data})

@teacher_required
@require_POST
def staff_feedback_save(request):
    feedback_message = request.POST.get('feedback_msg', '').strip()
    if not feedback_message:
        messages.error(request, 'Enter a message before submitting feedback.')
    else:
        Feedback.objects.create(user=request.user, message=feedback_message)
        messages.success(request, 'Your feedback was submitted.')
    return redirect('staff_feedback')

@teacher_required
def staff_profile(request):
    staff = get_object_or_404(Staff, user=request.user)
    form = TeacherProfileForm(instance=request.user)
    return render(request, 'teacher/profile.html', {'staff': staff, 'form': form})


@teacher_required
@require_POST
def teacher_profile_save(request):
    staff = get_object_or_404(Staff, user=request.user)
    form = TeacherProfileForm(request.POST, instance=request.user)
    if form.is_valid():
        form.save()
        messages.success(request, 'Your profile was updated.')
        return redirect('staff_profile')
    return render(request, 'teacher/profile.html', {'staff': staff, 'form': form})

@teacher_required
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

            staff=Staff.objects.get(id=customuser.id)
            staff.address = address
            staff.save()
            messages.success(request,"Successfully Updated Profile")
            return HttpResponseRedirect(reverse("staff_profile"))
        except:
            messages.error(request,"Failed to Update Profile")
            return HttpResponseRedirect(reverse("staff_profile"))

@teacher_required
@require_POST
def staff_fcmtoken_save(request):
    token = request.POST.get("token")
    try:
        staff=Staff.objects.get(admin=request.user.id)
        staff.fcm_token=token
        staff.save()
        return HttpResponse("True")
    except:
        return HttpResponse("False")
    
@teacher_required
def staff_all_notifications(request):
    staff=Staff.objects.get(admin=request.user.id)
    notifications=Notification.objects.filter(staff_id=staff.id)
    return render(request,"staff_template/all_notifications.html",{"notifications":notifications})

@teacher_required
def staff_add_result(request):
    return redirect('teacher_dashboard')

@teacher_required
@require_POST
def save_student_result(request):
    return redirect('teacher_dashboard')

@teacher_required
@require_POST
def fetch_student_result(request):
    return redirect('teacher_dashboard')

@teacher_required
def teacher_dashboard(request):
    staff = get_object_or_404(Staff, user=request.user)
    current_year = AcademicYear.objects.filter(is_current=True).first()
    assignments = staff.staffsubjectassignment_set.none()
    if current_year:
        assignments = staff.staffsubjectassignment_set.filter(
            academic_year=current_year,
        ).select_related('subject', 'academic_year').prefetch_related('classes')
    class_teacher_classes = StudentClass.objects.none()
    if current_year:
        class_teacher_classes = StudentClass.objects.filter(
            class_teacher=staff,
            academic_year=current_year,
        ).annotate(
            active_student_count=Count('students', filter=Q(students__active=True)),
        )

    context = {
        'assignments': assignments,
        'current_year': current_year,
        'class_teacher_classes': class_teacher_classes,
    }
    return render(request, 'teacher/teacher_dashboard.html', context)

@teacher_required
def upload_results(request, class_id, subject_id):
    staff = get_object_or_404(Staff, user=request.user)
    current_year = AcademicYear.objects.filter(is_current=True).first()
    if current_year is None:
        raise PermissionDenied
    assignment = get_object_or_404(
        staff.staffsubjectassignment_set.select_related('subject'),
        subject_id=subject_id,
        academic_year=current_year,
        classes__id=class_id,
        classes__academic_year=current_year,
    )
    class_obj = get_object_or_404(
        StudentClass,
        pk=class_id,
        academic_year=current_year,
    )
    students = Student.objects.filter(
        current_class=class_obj,
        academic_year=current_year,
        active=True,
    ).select_related('user').order_by('user__last_name', 'user__first_name')
    
    if request.method == 'POST':
        form = ResultUploadForm(request.POST)
        if form.is_valid():
            term = form.cleaned_data['term']
            score_rows = []
            for student in students:
                exam_score = request.POST.get(f'exam_{student.id}', '').strip()
                assignment_score = request.POST.get(f'assignment_{student.id}', '').strip()
                if not exam_score and not assignment_score:
                    continue
                try:
                    exam_score = Decimal(exam_score)
                    assignment_score = Decimal(assignment_score)
                except (InvalidOperation, TypeError, ValueError):
                    form.add_error(None, f'Enter valid scores for {student.user.get_full_name() or student.user.username}.')
                    break
                if (
                    not exam_score.is_finite()
                    or not assignment_score.is_finite()
                    or not Decimal('0') <= exam_score <= Decimal('100')
                    or not Decimal('0') <= assignment_score <= Decimal('100')
                ):
                    form.add_error(None, f'Scores for {student.user.get_full_name() or student.user.username} must be between 0 and 100.')
                    break
                score_rows.append((student, exam_score, assignment_score))

            if not score_rows and not form.non_field_errors():
                form.add_error(None, 'Enter at least one student result before saving.')

            if form.is_valid() and score_rows:
                with transaction.atomic():
                    for student, exam_score, assignment_score in score_rows:
                        SubjectResult.objects.update_or_create(
                            student=student,
                            subject=assignment.subject,
                            academic_year=current_year,
                            term=term,
                            defaults={
                                'exam_score': exam_score,
                                'assignment_score': assignment_score,
                                'created_by': staff,
                            },
                        )
                messages.success(request, 'Student results saved.')
                return redirect(
                    'upload_results',
                    class_id=class_obj.id,
                    subject_id=assignment.subject_id,
                )
    else:
        form = ResultUploadForm()
    
    context = {
        'students': students,
        'form': form,
        'class': class_obj,
        'subject': assignment.subject,
        'current_year': current_year,
    }
    return render(request, 'teacher/upload_results.html', context)

@teacher_required
def class_teacher_dashboard(request):
    staff = get_object_or_404(Staff, user=request.user)
    current_year = AcademicYear.objects.filter(is_current=True).first()
    classes = StudentClass.objects.filter(
        class_teacher=staff,
        academic_year=current_year,
    ).annotate(
        active_student_count=Count('students', filter=Q(students__active=True)),
    ) if current_year else StudentClass.objects.none()
    context = {
        'classes': classes,
        'current_year': current_year,
    }
    return render(request, 'teacher/class_teacher_dashboard.html', context)

@teacher_required
def view_class_results(request, class_id):
    staff = get_object_or_404(Staff, user=request.user)
    current_year = AcademicYear.objects.filter(is_current=True).first()
    if current_year is None:
        raise PermissionDenied
    class_obj = get_object_or_404(
        StudentClass,
        pk=class_id,
        class_teacher=staff,
        academic_year=current_year,
    )
    students = Student.objects.filter(
        current_class=class_obj,
        academic_year=current_year,
        active=True,
    ).select_related('user').order_by('user__last_name', 'user__first_name')
    results = SubjectResult.objects.filter(
        student__in=students,
        academic_year=current_year
    ).select_related('student__user', 'subject').order_by('term', 'subject__name')

    organized_results = {}
    for student in students:
        organized_results[student.id] = {
            'student': student,
            'terms': {}
        }
    
    for result in results:
        term_label = result.get_term_display()
        organized_results[result.student_id]['terms'].setdefault(term_label, []).append(result)
    
    context = {
        'class': class_obj,
        'organized_results': organized_results,
        'current_year': current_year,
    }
    return render(request, 'teacher/view_class_results.html', context)