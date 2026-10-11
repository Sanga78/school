from functools import wraps
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, render, redirect
from django.views.decorators.http import require_POST
from django.utils.dateparse import parse_date
from django.utils import timezone
from index.models import (
    AcademicYear,
    Attendance,
    AttendanceReport,
    Feedback,
    LeaveRequest,
    ResultPublication,
    SchoolEvent,
    Staff,
    StaffSubjectAssignment,
    Student,
    StudentClass,
    Subject,
    SubjectResultSubmission,
    SubjectResult,
)
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .forms import ClassEventForm, ResultUploadForm, TeacherProfileForm
from .services import admins, notify


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


def _notify_headteachers(sender, title, message):
    notify(admins(), title, message, sender=sender, priority='HIGH',
           link=reverse('review_results'))


@teacher_required
def staff_apply_leave(request):
    staff = request.user.staff_profile
    leave_data = LeaveRequest.objects.filter(
        applicant=request.user,
    ).select_related('cover_teacher__user', 'approved_by')
    colleagues = Staff.objects.filter(
        user__user_type=2, user__is_active=True,
    ).exclude(pk=staff.pk).select_related('user').order_by('user__first_name', 'user__last_name')
    return render(request, 'teacher/leave.html', {
        'staff': staff,
        'leave_data': leave_data,
        'colleagues': colleagues,
        'leave_types': LeaveRequest.LEAVE_TYPE_CHOICES,
        'today': timezone.localdate(),
    })


@teacher_required
@require_POST
def staff_apply_leave_save(request):
    leave_type = request.POST.get('leave_type', '').strip()
    start_date = parse_date(request.POST.get('start_date', ''))
    end_date = parse_date(request.POST.get('end_date', ''))
    reason = request.POST.get('reason', '').strip()
    handover_notes = request.POST.get('handover_notes', '').strip()[:2000]
    valid_types = {value for value, _ in LeaveRequest.LEAVE_TYPE_CHOICES}
    cover_teacher = None
    cover_id = request.POST.get('cover_teacher', '')
    if cover_id.isdigit():
        cover_teacher = Staff.objects.filter(
            pk=int(cover_id), user__user_type=2, user__is_active=True,
        ).exclude(user=request.user).first()

    if leave_type not in valid_types or not reason or not start_date or not end_date:
        messages.error(request, 'Choose a leave type, valid start and end dates, and give a reason.')
    elif end_date < start_date:
        messages.error(request, 'The leave end date must be on or after the start date.')
    else:
        LeaveRequest.objects.create(
            applicant=request.user,
            leave_type=leave_type,
            start_date=start_date,
            end_date=end_date,
            reason=reason,
            cover_teacher=cover_teacher,
            handover_notes=handover_notes,
        )
        messages.success(request, 'Your leave request was submitted and is awaiting approval.')
    return redirect('staff_apply_leave')

@teacher_required
def staff_feedback(request):
    feedback_data = Feedback.objects.filter(user=request.user)
    return render(request, 'teacher/feedback.html', {'feedback_data': feedback_data})

@teacher_required
@require_POST
def staff_feedback_save(request):
    feedback_message = request.POST.get('feedback_msg', '').strip()
    if not feedback_message:
        messages.error(request, 'Enter a message before submitting feedback.')
    else:
        feedback = Feedback.objects.create(user=request.user, message=feedback_message[:5000])
        notify(admins(), 'New feedback from a teacher',
               f'{request.user.get_full_name() or request.user.username} sent feedback to the administration.',
               sender=request.user, link=reverse('respond_feedback', args=[feedback.pk]))
        messages.success(request, 'Your feedback was sent to the administration.')
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
    today = timezone.localdate()
    class_cards = []
    for class_obj in class_teacher_classes:
        reports = AttendanceReport.objects.filter(
            attendance__subject__isnull=True,
            attendance__class_obj=class_obj,
            attendance__attendance_date=today,
        )
        class_cards.append({
            'class': class_obj,
            'marked_today': reports.exists(),
            'present_today': reports.filter(status__in=['P', 'L']).count(),
            'absent_today': reports.filter(status='A').count(),
        })

    context = {
        'assignments': assignments,
        'current_year': current_year,
        'class_teacher_classes': class_teacher_classes,
        'class_cards': class_cards,
        'today': today,
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
    result_submission = SubjectResultSubmission.objects.filter(
        class_obj=class_obj,
        subject=assignment.subject,
        academic_year=current_year,
    )
    
    if request.method == 'POST':
        form = ResultUploadForm(request.POST)
        if form.is_valid():
            term = form.cleaned_data['term']
            action = request.POST.get('action', 'save')
            if action not in {'save', 'submit_subject'}:
                form.add_error(None, 'Choose whether to save or submit these results.')
            publication = ResultPublication.objects.filter(
                class_obj=class_obj,
                academic_year=current_year,
                term=term,
                status__in=['SUBMITTED', 'APPROVED'],
            ).first()
            if publication:
                form.add_error(
                    None,
                    'These class results have already been sent for review or published and can no longer be changed.',
                )
            if result_submission.filter(term=term).exists():
                form.add_error(
                    None,
                    'These subject results have already been submitted. Ask the headteacher to return the class results for correction before editing.',
                )

            score_rows = []
            missing_students = []
            for student in students:
                exam_score = request.POST.get(f'exam_{student.id}', '').strip()
                assignment_score = request.POST.get(f'assignment_{student.id}', '').strip()
                if not exam_score and not assignment_score:
                    if action == 'submit_subject':
                        missing_students.append(student)
                    continue
                if not exam_score or not assignment_score:
                    form.add_error(
                        None,
                        f'Enter both exam and assignment scores for {student.user.get_full_name() or student.user.username}.',
                    )
                    break
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

            if action == 'submit_subject' and missing_students and not form.non_field_errors():
                names = ', '.join(
                    student.user.get_full_name() or student.user.username
                    for student in missing_students[:5]
                )
                more = ' and others' if len(missing_students) > 5 else ''
                form.add_error(
                    None,
                    f'Cannot submit yet: {len(missing_students)} student result(s) are missing ({names}{more}).',
                )

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
                    if action == 'submit_subject':
                        submission, created = SubjectResultSubmission.objects.get_or_create(
                            class_obj=class_obj,
                            subject=assignment.subject,
                            academic_year=current_year,
                            term=term,
                            defaults={'submitted_by': staff},
                        )
                        if created:
                            teacher_name = request.user.get_full_name() or request.user.username
                            _notify_headteachers(
                                request.user,
                                f'{assignment.subject.name} results submitted',
                                f'{teacher_name} sent {assignment.subject.name} results for '
                                f'{class_obj.name}, {current_year.name} {dict(SubjectResult.TERM_CHOICES)[term]}.',
                            )
                            messages.success(
                                request,
                                f'{assignment.subject.name} results were submitted to the headteacher for review.',
                            )
                        else:
                            messages.info(request, 'These subject results were already submitted.')
                if action == 'save':
                    messages.success(request, 'Student results saved as a draft. They are not visible to students.')
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
        'result_submission': result_submission,
    }
    return render(request, 'teacher/upload_results.html', context)


@teacher_required
@require_POST
def submit_class_results(request, class_id):
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
    term = request.POST.get('term')
    if term not in dict(SubjectResult.TERM_CHOICES):
        messages.error(request, 'Choose a valid term before submitting class results.')
        return redirect('class_teacher_dashboard')

    students = list(Student.objects.filter(
        current_class=class_obj,
        academic_year=current_year,
        active=True,
    ).select_related('user'))
    subject_ids = set(StaffSubjectAssignment.objects.filter(
        academic_year=current_year,
        classes=class_obj,
    ).values_list('subject_id', flat=True).distinct())
    if not students:
        messages.error(request, 'There are no active students in this class to submit results for.')
        return redirect('class_teacher_dashboard')
    if not subject_ids:
        messages.error(request, 'No subjects have been assigned to this class for the current academic year.')
        return redirect('class_teacher_dashboard')

    submitted_subject_ids = set(SubjectResultSubmission.objects.filter(
        class_obj=class_obj,
        academic_year=current_year,
        term=term,
        subject_id__in=subject_ids,
    ).values_list('subject_id', flat=True))
    missing_subjects = Subject.objects.filter(
        pk__in=subject_ids - submitted_subject_ids,
    ).order_by('name')
    if missing_subjects.exists():
        messages.error(
            request,
            'Cannot submit class results until every assigned subject teacher has submitted: '
            + ', '.join(subject.name for subject in missing_subjects),
        )
        return redirect('class_teacher_dashboard')

    missing_results = SubjectResult.objects.filter(
        student__in=students,
        subject_id__in=subject_ids,
        academic_year=current_year,
        term=term,
    ).values('subject_id').annotate(result_count=Count('student_id', distinct=True))
    complete_subject_ids = {
        item['subject_id']
        for item in missing_results
        if item['result_count'] == len(students)
    }
    incomplete_subject_ids = subject_ids - complete_subject_ids
    if incomplete_subject_ids:
        incomplete_names = Subject.objects.filter(
            pk__in=incomplete_subject_ids,
        ).order_by('name')
        messages.error(
            request,
            'Cannot submit class results because some students are missing results for: '
            + ', '.join(subject.name for subject in incomplete_names),
        )
        return redirect('class_teacher_dashboard')

    with transaction.atomic():
        existing_publication = ResultPublication.objects.filter(
            class_obj=class_obj,
            academic_year=current_year,
            term=term,
        ).first()
        if existing_publication and existing_publication.status == 'SUBMITTED':
            messages.info(request, 'These class results are already awaiting headteacher review.')
            return redirect('class_teacher_dashboard')
        if existing_publication and existing_publication.status == 'APPROVED':
            messages.error(request, 'These class results have already been published and cannot be resubmitted.')
            return redirect('class_teacher_dashboard')
        publication, created = ResultPublication.objects.update_or_create(
            class_obj=class_obj,
            academic_year=current_year,
            term=term,
            defaults={
                'status': 'SUBMITTED',
                'submitted_by': staff,
                'reviewed_by': None,
                'review_note': '',
                'submitted_at': timezone.now(),
                'reviewed_at': None,
            },
        )
        teacher_name = request.user.get_full_name() or request.user.username
        _notify_headteachers(
            request.user,
            f'{class_obj.name} results awaiting approval',
            f'{teacher_name} sent complete {class_obj.name} class results for '
            f'{current_year.name} {dict(SubjectResult.TERM_CHOICES)[term]}.',
        )
    messages.success(request, 'Complete class results were sent to the headteacher for verification.')
    return redirect('class_teacher_dashboard')


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
        'terms': SubjectResult.TERM_CHOICES,
        'result_publications': ResultPublication.objects.filter(
            class_obj__in=classes,
            academic_year=current_year,
        ) if current_year else ResultPublication.objects.none(),
    }
    return render(request, 'teacher/class_teacher_dashboard.html', context)


@teacher_required
def class_teacher_events(request, class_id):
    staff = get_object_or_404(Staff, user=request.user)
    current_year = AcademicYear.objects.filter(is_current=True).first()
    if current_year is None:
        raise PermissionDenied
    class_obj = get_object_or_404(
        StudentClass, pk=class_id, class_teacher=staff, academic_year=current_year,
    )
    if request.method == 'POST':
        form = ClassEventForm(request.POST, class_obj=class_obj)
        if form.is_valid():
            event = form.save(commit=False)
            event.created_by = request.user
            form.instance = event
            form.save()
            messages.success(request, 'Event sent to the selected students.')
            return redirect('class_teacher_events', class_id=class_obj.pk)
    else:
        form = ClassEventForm(class_obj=class_obj)
    events = SchoolEvent.objects.filter(audience_class=class_obj).prefetch_related(
        'recipients__user',
    ).order_by('-starts_at')
    return render(request, 'teacher/class_events.html', {
        'class_obj': class_obj,
        'form': form,
        'events': events,
    })


@teacher_required
@require_POST
def class_teacher_delete_event(request, class_id, event_id):
    staff = get_object_or_404(Staff, user=request.user)
    event = get_object_or_404(
        SchoolEvent, pk=event_id, audience_class_id=class_id,
        audience_class__class_teacher=staff,
    )
    event.delete()
    messages.success(request, 'Event removed.')
    return redirect('class_teacher_events', class_id=class_id)


@teacher_required
def class_teacher_attendance(request, class_id):
    staff = get_object_or_404(Staff, user=request.user)
    current_year = AcademicYear.objects.filter(is_current=True).first()
    if current_year is None:
        raise PermissionDenied
    class_obj = get_object_or_404(
        StudentClass, pk=class_id, class_teacher=staff, academic_year=current_year,
    )
    source = request.POST if request.method == 'POST' else request.GET
    attendance_date = parse_date(source.get('date') or '') or timezone.localdate()
    students = list(Student.objects.filter(
        current_class=class_obj, academic_year=current_year, active=True,
    ).select_related('user').order_by('user__last_name', 'user__first_name'))
    valid_statuses = {code for code, _ in AttendanceReport.STATUS_CHOICES}

    if request.method == 'POST':
        if attendance_date > timezone.localdate():
            messages.error(request, 'Attendance cannot be recorded for a future date.')
        else:
            with transaction.atomic():
                attendance = Attendance.objects.filter(
                    subject__isnull=True, class_obj=class_obj,
                    attendance_date=attendance_date, academic_year=current_year,
                ).first()
                if attendance is not None:
                    messages.error(request, 'The register for this date has already been marked and cannot be marked again.')
                    return redirect(f"{reverse('class_teacher_attendance', args=[class_obj.pk])}?date={attendance_date.isoformat()}")
                if attendance is None:
                    attendance = Attendance.objects.create(
                        subject=None, class_obj=class_obj, attendance_date=attendance_date,
                        academic_year=current_year, created_by=staff,
                    )
                for student in students:
                    status = request.POST.get(f'status_{student.pk}')
                    if status not in valid_statuses:
                        status = 'A'
                    AttendanceReport.objects.update_or_create(
                        attendance=attendance, student=student,
                        defaults={
                            'status': status,
                            'remarks': request.POST.get(f'remarks_{student.pk}', '').strip()[:100],
                        },
                    )
            messages.success(request, f'Attendance for {class_obj.name} on {attendance_date:%d %b %Y} saved.')
            return redirect(f"{reverse('class_teacher_attendance', args=[class_obj.pk])}?date={attendance_date.isoformat()}")

    existing = {
        report.student_id: report
        for report in AttendanceReport.objects.filter(
            attendance__subject__isnull=True, attendance__class_obj=class_obj,
            attendance__attendance_date=attendance_date, attendance__academic_year=current_year,
        )
    }
    rows = [{'student': s, 'report': existing.get(s.pk)} for s in students]
    return render(request, 'teacher/class_attendance.html', {
        'class_obj': class_obj,
        'attendance_date': attendance_date,
        'today': timezone.localdate(),
        'rows': rows,
        'status_choices': AttendanceReport.STATUS_CHOICES,
        'recorded': bool(existing),
    })


@teacher_required
def class_teacher_weekly_attendance(request, class_id):
    staff = get_object_or_404(Staff, user=request.user)
    current_year = AcademicYear.objects.filter(is_current=True).first()
    if current_year is None:
        raise PermissionDenied
    class_obj = get_object_or_404(
        StudentClass, pk=class_id, class_teacher=staff, academic_year=current_year,
    )
    register = Attendance.objects.filter(
        subject__isnull=True, class_obj=class_obj, academic_year=current_year,
    )
    week_starts = sorted(
        {d - timedelta(days=d.weekday()) for d in register.values_list('attendance_date', flat=True)},
        reverse=True,
    )

    requested = parse_date(request.GET.get('week') or '')
    if requested is not None:
        week_start = requested - timedelta(days=requested.weekday())
    elif week_starts:
        week_start = week_starts[0]
    else:
        week_start = timezone.localdate() - timedelta(days=timezone.localdate().weekday())
    days = [week_start + timedelta(days=i) for i in range(5)]

    students = list(Student.objects.filter(
        current_class=class_obj, academic_year=current_year, active=True,
    ).select_related('user').order_by('user__last_name', 'user__first_name'))
    marks = {}
    for report in AttendanceReport.objects.filter(
        attendance__in=register.filter(attendance_date__in=days),
    ).select_related('attendance'):
        marks[(report.student_id, report.attendance.attendance_date)] = report.status

    rows = []
    for student in students:
        cells = [marks.get((student.pk, day)) for day in days]
        rows.append({
            'student': student,
            'cells': cells,
            'present': sum(1 for c in cells if c in ('P', 'L')),
            'absent': sum(1 for c in cells if c == 'A'),
            'late': sum(1 for c in cells if c == 'L'),
            'excused': sum(1 for c in cells if c == 'E'),
        })
    recorded_days = {d for (_, d) in marks}
    weeks = [
        {
            'start': start,
            'end': start + timedelta(days=4),
            'days_recorded': register.filter(
                attendance_date__range=(start, start + timedelta(days=6)),
            ).count(),
        }
        for start in week_starts
    ]
    template = 'teacher/class_attendance_print.html' if request.GET.get('print') else 'teacher/class_attendance_weekly.html'
    return render(request, template, {
        'class_obj': class_obj,
        'year': current_year,
        'week_start': week_start,
        'week_end': days[-1],
        'days': days,
        'recorded_days': recorded_days,
        'rows': rows,
        'weeks': weeks,
        'printed_at': timezone.now(),
        'teacher_name': request.user.get_full_name() or request.user.username,
    })

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
