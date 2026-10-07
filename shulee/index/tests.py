from datetime import date, timedelta
from io import BytesIO
import json
import re
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.template.loader import render_to_string
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from .models import (
    AcademicYear,
    Attendance,
    AttendanceReport,
    Bursar,
    Expense,
    Feedback,
    FeePayment,
    FeeStructure,
    LeaveRequest,
    SchoolEvent,
    Staff,
    StaffSubjectAssignment,
    SubjectResult,
    Subject,
    Student,
    StudentClass,
)


User = get_user_model()


class SchoolCalendarTests(TestCase):
    def setUp(self):
        self.headteacher = User.objects.create_user(
            username='headteacher',
            password='test-password',
            user_type=1,
        )
        self.student_user = User.objects.create_user(
            username='student',
            password='test-password',
            user_type=3,
        )
        self.student_user.student_profile.gender = 'F'
        self.student_user.student_profile.save()
        self.future_start = timezone.now() + timedelta(days=5)
        self.event = SchoolEvent.objects.create(
            title='Reading Day',
            description='A school reading activity.',
            starts_at=self.future_start,
            location='School library',
            created_by=self.headteacher,
        )

    def test_published_events_are_visible_to_active_registered_students(self):
        self.client.force_login(self.student_user)

        response = self.client.get(reverse('events'))

        self.assertContains(response, 'Reading Day')
        self.assertContains(response, 'School library')

    def test_calendar_event_details_are_hidden_from_anonymous_visitors(self):
        response = self.client.get(reverse('events'))

        self.assertNotContains(response, 'Reading Day')
        self.assertContains(response, 'Student login')

    def test_about_page_links_students_to_the_calendar(self):
        response = self.client.get(reverse('about'))

        self.assertContains(response, 'A school calendar for registered students')
        self.assertContains(response, reverse('events'))
        self.assertContains(response, reverse('show_login'))

    def test_student_portal_sidebar_links_to_the_calendar(self):
        sidebar = render_to_string(
            'student_template/sidebar.html',
            {'user': self.student_user},
        )

        self.assertIn('School Calendar', sidebar)
        self.assertIn(reverse('events'), sidebar)

    def test_drafts_and_past_events_are_not_shown_to_students(self):
        SchoolEvent.objects.create(
            title='Unpublished Assembly',
            description='Draft details.',
            starts_at=self.future_start + timedelta(days=1),
            is_published=False,
            created_by=self.headteacher,
        )
        SchoolEvent.objects.create(
            title='Past Activity',
            description='Past details.',
            starts_at=timezone.now() - timedelta(days=1),
            created_by=self.headteacher,
        )
        self.client.force_login(self.student_user)

        response = self.client.get(reverse('events'))

        self.assertContains(response, 'Reading Day')
        self.assertNotContains(response, 'Unpublished Assembly')
        self.assertNotContains(response, 'Past Activity')

    def test_only_admin_can_manage_school_events(self):
        self.client.force_login(self.student_user)

        response = self.client.get(reverse('manage_events'))

        self.assertEqual(response.status_code, 403)

    def test_admin_event_management_uses_the_admin_template(self):
        self.client.force_login(self.headteacher)

        response = self.client.get(reverse('manage_events'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'admin/manage_events.html')
        self.assertContains(response, 'School management')
        self.assertNotContains(response, 'Life at AIC Laboret')

    def test_headteacher_can_publish_an_event_for_students(self):
        self.client.force_login(self.headteacher)
        starts_at = (timezone.now() + timedelta(days=10)).strftime('%Y-%m-%dT%H:%M')

        response = self.client.post(reverse('manage_events'), {
            'title': 'Sports Day',
            'description': 'Pupils take part in school sports.',
            'starts_at': starts_at,
            'ends_at': '',
            'location': 'School grounds',
            'is_published': 'on',
        })

        self.assertRedirects(response, reverse('manage_events'))
        event = SchoolEvent.objects.get(title='Sports Day')
        self.assertEqual(event.created_by, self.headteacher)
        self.assertTrue(event.is_published)

    def test_headteacher_can_edit_and_delete_an_event(self):
        self.client.force_login(self.headteacher)
        edit_url = reverse('edit_school_event', args=[self.event.pk])
        starts_at = (timezone.now() + timedelta(days=12)).strftime('%Y-%m-%dT%H:%M')

        edit_response = self.client.get(edit_url)
        self.assertContains(edit_response, 'Edit school event')
        self.assertTemplateUsed(edit_response, 'admin/manage_events.html')

        response = self.client.post(edit_url, {
            'title': 'Updated Reading Day',
            'description': self.event.description,
            'starts_at': starts_at,
            'ends_at': '',
            'location': self.event.location,
            'is_published': 'on',
        })

        self.assertRedirects(response, reverse('manage_events'))
        self.event.refresh_from_db()
        self.assertEqual(self.event.title, 'Updated Reading Day')

        response = self.client.post(reverse('delete_school_event', args=[self.event.pk]))

        self.assertRedirects(response, reverse('manage_events'))
        self.assertFalse(SchoolEvent.objects.filter(pk=self.event.pk).exists())

    def test_event_end_time_must_not_precede_start_time(self):
        self.client.force_login(self.headteacher)
        starts_at = (timezone.now() + timedelta(days=10)).replace(second=0, microsecond=0)
        ends_at = starts_at - timedelta(hours=1)

        response = self.client.post(reverse('manage_events'), {
            'title': 'Invalid Event',
            'description': 'An invalid time range.',
            'starts_at': starts_at.strftime('%Y-%m-%dT%H:%M'),
            'ends_at': ends_at.strftime('%Y-%m-%dT%H:%M'),
            'location': '',
            'is_published': 'on',
        })

        self.assertEqual(response.status_code, 200)
        self.assertFalse(SchoolEvent.objects.filter(title='Invalid Event').exists())
        self.assertContains(response, 'The end time must be after the start time.')


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class PasswordResetTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='password-reset-user',
            email='pupil@example.com',
            password='old-password',
            user_type=3,
        )

    def test_login_page_links_to_password_reset_page(self):
        response = self.client.get(reverse('show_login'))

        self.assertContains(response, reverse('password_reset'))

    def test_password_reset_page_renders_and_sends_email(self):
        response = self.client.get(reverse('password_reset'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Reset your password')

        response = self.client.post(reverse('password_reset'), {
            'email': self.user.email,
        })

        self.assertRedirects(response, reverse('password_reset_done'))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('AIC Laboret', mail.outbox[0].subject)
        reset_link = re.search(r'https?://[^/\s]+(/accounts/reset/\S+)', mail.outbox[0].body)
        self.assertIsNotNone(reset_link)

        response = self.client.get(reset_link.group(1), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Choose a new password')

        response = self.client.post(response.request['PATH_INFO'], {
            'new_password1': 'New-Portal-Password-2091!',
            'new_password2': 'New-Portal-Password-2091!',
        })

        self.assertRedirects(response, reverse('password_reset_complete'))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('New-Portal-Password-2091!'))

    def test_unknown_email_gets_generic_confirmation_without_sending_mail(self):
        response = self.client.post(reverse('password_reset'), {
            'email': 'not-registered@example.com',
        })

        self.assertRedirects(response, reverse('password_reset_done'))
        self.assertEqual(len(mail.outbox), 0)
        self.assertContains(self.client.get(reverse('password_reset_done')), 'does not reveal whether an account exists')

    def test_password_reset_complete_page_has_sign_in_link(self):
        response = self.client.get(reverse('password_reset_complete'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('show_login'))


class SignupSecurityTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username='signup-admin',
            email='admin@example.com',
            password='test-password',
            user_type=1,
        )
        self.year = AcademicYear.objects.create(
            name='2029',
            start_date=date(2029, 1, 1),
            end_date=date(2029, 12, 31),
            is_current=True,
        )
        self.class_obj = StudentClass.objects.create(
            name='Grade 6',
            academic_year=self.year,
        )

    def student_signup_data(self):
        return {
            'first_name': 'Student',
            'last_name': 'Example',
            'username': 'new-student',
            'email': 'new-student@example.com',
            'address': 'School Road',
            'academic_year': str(self.year.pk),
            'current_class': str(self.class_obj.pk),
            'gender': 'F',
            'password': 'unique-long-password-8472',
        }

    def test_public_admin_signup_is_blocked_and_admin_signup_requires_admin_role(self):
        response = self.client.post(reverse('admin_signup'), {
            'username': 'attacker-admin',
            'email': 'attacker@example.com',
            'password': 'valid-strong-password-9382',
        })

        self.assertEqual(response.status_code, 302)
        self.assertFalse(User.objects.filter(username='attacker-admin').exists())

        student = User.objects.create_user(
            username='signup-student',
            password='test-password',
            user_type=3,
        )
        self.client.force_login(student)
        response = self.client.post(reverse('admin_signup'), {
            'username': 'unauthorized-admin',
            'email': 'unauthorized@example.com',
            'password': 'valid-strong-password-9382',
        })

        self.assertEqual(response.status_code, 403)
        self.assertFalse(User.objects.filter(username='unauthorized-admin').exists())

    def test_existing_admin_can_create_an_admin_using_the_protected_signup(self):
        self.client.force_login(self.admin)

        response = self.client.post(reverse('admin_signup'), {
            'username': 'second-admin',
            'email': 'second-admin@example.com',
            'password': 'different-strong-password-4827',
        })

        self.assertRedirects(response, reverse('manage_administrators'))
        created_user = User.objects.get(username='second-admin')
        self.assertEqual(created_user.user_type, 1)
        self.assertTrue(created_user.check_password('different-strong-password-4827'))

    def test_student_signup_rejects_non_image_upload_without_saving_file_or_user(self):
        with TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                response = self.client.post(
                    reverse('student_signup'),
                    {
                        **self.student_signup_data(),
                        'profile_pic': SimpleUploadedFile(
                            'profile.html',
                            b'<html><script>alert(document.domain)</script></html>',
                            content_type='text/html',
                        ),
                    },
                )

                self.assertEqual(response.status_code, 400)
                self.assertFalse(User.objects.filter(username='new-student').exists())
                self.assertEqual(list(Path(media_root).rglob('*')), [])

    def test_student_profile_image_is_reencoded_and_stored_with_generated_name(self):
        image_bytes = BytesIO()
        Image.new('RGB', (8, 8), color='navy').save(image_bytes, format='PNG')
        with TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                response = self.client.post(
                    reverse('student_signup'),
                    {
                        **self.student_signup_data(),
                        'profile_pic': SimpleUploadedFile(
                            'user-controlled-name.png',
                            image_bytes.getvalue(),
                            content_type='image/png',
                        ),
                    },
                )

                self.assertEqual(response.status_code, 302)
                user = User.objects.get(username='new-student')
                self.assertEqual(user.user_type, 3)
                self.assertEqual(user.student_profile.current_class, self.class_obj)
                self.assertRegex(user.profile_pic.name, r'^profile_pics/[0-9a-f]{32}\.jpg$')
                with user.profile_pic.open('rb') as stored_image:
                    self.assertTrue(stored_image.read(3).startswith(b'\xff\xd8\xff'))


class BursarAccountingTests(TestCase):
    def setUp(self):
        self.bursar_user = User.objects.create_user(
            username='accountant',
            email='accountant@example.com',
            password='test-password',
            user_type=4,
        )
        self.admin_user = User.objects.create_user(
            username='finance-admin',
            password='test-password',
            user_type=1,
        )
        self.student_user = User.objects.create_user(
            username='fee-student',
            password='test-password',
            user_type=3,
        )
        self.student_user.student_profile.gender = 'F'
        self.student_user.student_profile.save()
        self.academic_year = AcademicYear.objects.create(
            name='2026',
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            is_current=True,
        )
        self.student_class = StudentClass.objects.create(
            name='Grade 5',
            academic_year=self.academic_year,
        )
        self.student = self.student_user.student_profile
        self.student_user.first_name = 'Zoe'
        self.student_user.last_name = 'Zulu'
        self.student_user.save()
        self.student.current_class = self.student_class
        self.student.academic_year = self.academic_year
        self.student.save()
        self.fee_structure = FeeStructure.objects.create(
            name='Term 1 Fees',
            description='Term fees',
            amount='12000.00',
            class_obj=self.student_class,
            academic_year=self.academic_year,
            due_date=date(2026, 2, 1),
        )

    def test_bursar_profile_is_created_for_accountant_role(self):
        self.assertTrue(Bursar.objects.filter(user=self.bursar_user).exists())

    def test_bursar_login_redirects_to_dashboard(self):
        response = self.client.post(reverse('do_login'), {
            'email': 'accountant@example.com',
            'password': 'test-password',
        })

        self.assertRedirects(response, reverse('bursar_dashboard'))

    def test_only_active_bursars_can_access_finance_pages(self):
        self.client.force_login(self.student_user)
        response = self.client.get(reverse('bursar_dashboard'))
        self.assertEqual(response.status_code, 302)

        self.bursar_user.is_active = False
        self.bursar_user.save()
        self.client.force_login(self.bursar_user)
        response = self.client.get(reverse('fee_records'))
        self.assertEqual(response.status_code, 302)

    def test_bursar_finance_pages_render(self):
        self.client.force_login(self.bursar_user)
        for route in (
            'bursar_dashboard',
            'fee_records',
            'expense_management',
            'payment_reports',
        ):
            with self.subTest(route=route):
                response = self.client.get(reverse(route))
                self.assertEqual(response.status_code, 200)

    def test_fee_records_filter_by_search_class_year_and_active_status(self):
        other_class = StudentClass.objects.create(
            name='Grade 4',
            academic_year=self.academic_year,
        )
        other_user = User.objects.create_user(
            username='amina-able',
            first_name='Amina',
            last_name='Able',
            password='test-password',
            user_type=3,
        )
        other_user.student_profile.gender = 'F'
        other_user.student_profile.current_class = other_class
        other_user.student_profile.academic_year = self.academic_year
        other_user.student_profile.active = False
        other_user.student_profile.save()

        self.client.force_login(self.bursar_user)
        response = self.client.get(reverse('fee_records'), {
            'q': 'amina',
            'class': str(other_class.pk),
            'academic_year': str(self.academic_year.pk),
            'status': 'inactive',
        })

        students = list(response.context['students'])
        self.assertEqual([student.user.username for student in students], ['amina-able'])
        self.assertContains(response, 'Amina')
        self.assertContains(response, 'Grade 4')

    def test_fee_records_sort_by_name_and_total_paid(self):
        other_user = User.objects.create_user(
            username='amina-able',
            first_name='Amina',
            last_name='Able',
            password='test-password',
            user_type=3,
        )
        other_user.student_profile.gender = 'F'
        other_user.student_profile.current_class = self.student_class
        other_user.student_profile.academic_year = self.academic_year
        other_user.student_profile.save()
        FeePayment.objects.create(
            student=self.student,
            fee_structure=self.fee_structure,
            amount='500.00',
            payment_method='CASH',
        )
        FeePayment.objects.create(
            student=other_user.student_profile,
            fee_structure=self.fee_structure,
            amount='1500.00',
            payment_method='CASH',
        )
        self.client.force_login(self.bursar_user)

        by_name = self.client.get(reverse('fee_records'), {'sort': 'name'})
        self.assertEqual(
            [student.user.username for student in by_name.context['students']],
            ['amina-able', 'fee-student'],
        )
        by_paid = self.client.get(reverse('fee_records'), {'sort': '-paid'})
        self.assertEqual(
            [student.user.username for student in by_paid.context['students']],
            ['amina-able', 'fee-student'],
        )
        self.assertContains(by_paid, 'Highest total paid')

    def test_bursar_can_record_payment_and_is_attributed(self):
        self.client.force_login(self.bursar_user)
        response = self.client.post(
            reverse('record_payment', args=[self.student.pk]),
            {
                'fee_structure': str(self.fee_structure.pk),
                'amount': '3500.00',
                'payment_date': '2026-01-15',
                'payment_method': 'CASH',
                'transaction_code': 'RCPT-001',
                'notes': '',
            },
        )

        self.assertRedirects(response, reverse('fee_records'))
        payment = FeePayment.objects.get(student=self.student)
        self.assertEqual(payment.recorded_by_bursar, self.bursar_user.bursar_profile)
        self.assertIsNone(payment.received_by)

    def test_bursar_can_create_fee_structure(self):
        self.client.force_login(self.bursar_user)
        response = self.client.post(reverse('fee_records'), {
            'name': 'Boarding',
            'description': 'Boarding fees',
            'amount': '8000.00',
            'class_obj': str(self.student_class.pk),
            'academic_year': str(self.academic_year.pk),
            'due_date': '2026-03-01',
            'is_active': 'on',
        })

        self.assertRedirects(response, reverse('fee_records'))
        self.assertTrue(FeeStructure.objects.filter(name='Boarding').exists())

    def test_bursar_can_record_expense(self):
        self.client.force_login(self.bursar_user)
        response = self.client.post(reverse('expense_management'), {
            'amount': '450.00',
            'category': 'FOOD',
            'description': 'Kitchen supplies',
            'date': '2026-01-16',
            'receipt_number': 'EXP-001',
        })

        self.assertRedirects(response, reverse('expense_management'))
        expense = Expense.objects.get(receipt_number='EXP-001')
        self.assertEqual(expense.recorded_by_bursar, self.bursar_user.bursar_profile)

    def test_admin_can_add_and_edit_bursar_accounts(self):
        self.client.force_login(self.admin_user)
        response = self.client.post(reverse('add_bursar'), {
            'first_name': 'New',
            'last_name': 'Accountant',
            'email': 'new-accountant@example.com',
            'username': 'new-accountant',
            'password': 'test-password',
            'gender': 'F',
            'qualification': 'Accounting',
            'date_of_joining': '',
            'phone': '',
            'address': '',
            'profile_pic': '',
        })

        self.assertRedirects(response, reverse('manage_bursars'))
        new_bursar = Bursar.objects.get(user__username='new-accountant')
        self.assertEqual(new_bursar.gender, 'F')
        self.assertIsNotNone(new_bursar.date_of_joining)

        response = self.client.post(reverse('edit_bursar', args=[new_bursar.pk]), {
            'first_name': 'Edited',
            'last_name': 'Accountant',
            'email': 'new-accountant@example.com',
            'username': 'new-accountant',
            'password': '',
            'gender': 'O',
            'qualification': 'Senior Accountant',
            'date_of_joining': '2026-01-20',
            'phone': '',
            'address': '',
            'is_active': 'on',
            'profile_pic': '',
        })
        self.assertRedirects(response, reverse('manage_bursars'))
        new_bursar.refresh_from_db()
        self.assertEqual(new_bursar.gender, 'O')
        self.assertEqual(new_bursar.user.first_name, 'Edited')

    def test_admin_can_list_and_toggle_bursar_status(self):
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('manage_bursars'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'accountant')

        toggle_url = reverse('deactivate_bursar', args=[self.bursar_user.bursar_profile.pk])
        response = self.client.get(toggle_url)
        self.assertEqual(response.status_code, 405)

        response = self.client.post(toggle_url)
        self.assertRedirects(response, reverse('manage_bursars'))
        self.bursar_user.refresh_from_db()
        self.assertFalse(self.bursar_user.is_active)

        self.client.post(toggle_url)
        self.bursar_user.refresh_from_db()
        self.assertTrue(self.bursar_user.is_active)


class TeacherPortalTests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user(
            username='portal-teacher',
            password='test-password',
            user_type=2,
        )
        self.other_teacher = User.objects.create_user(
            username='other-teacher',
            password='test-password',
            user_type=2,
        )
        self.student_user = User.objects.create_user(
            username='portal-student',
            password='test-password',
            user_type=3,
        )
        self.student_user.student_profile.gender = 'F'
        self.year = AcademicYear.objects.create(
            name='2028',
            start_date=date(2028, 1, 1),
            end_date=date(2028, 12, 31),
            is_current=True,
        )
        self.class_obj = StudentClass.objects.create(
            name='Grade 5',
            academic_year=self.year,
            class_teacher=self.teacher.staff_profile,
        )
        self.student_user.student_profile.current_class = self.class_obj
        self.student_user.student_profile.academic_year = self.year
        self.student_user.student_profile.save()
        self.subject = Subject.objects.create(name='English', code='ENG5')
        self.assignment = StaffSubjectAssignment.objects.create(
            staff=self.teacher.staff_profile,
            subject=self.subject,
            academic_year=self.year,
        )
        self.assignment.classes.add(self.class_obj)

    def attendance_payload(self, status=1):
        return json.dumps([{
            'id': self.student_user.student_profile.pk,
            'status': status,
        }])

    def test_teacher_routes_require_a_teacher_role(self):
        for route, args in (
            ('teacher_dashboard', ()),
            ('class_teacher_dashboard', ()),
            ('upload_results', (self.class_obj.pk, self.subject.pk)),
            ('view_class_results', (self.class_obj.pk,)),
        ):
            with self.subTest(route=route):
                self.client.force_login(self.student_user)
                response = self.client.get(reverse(route, args=args))
                self.assertEqual(response.status_code, 403)

    def test_teacher_dashboard_uses_school_portal_and_current_assignments(self):
        self.client.force_login(self.teacher)

        response = self.client.get(reverse('teacher_dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'teacher/teacher_dashboard.html')
        self.assertContains(response, 'My subjects and classes')
        self.assertContains(response, self.subject.name)
        self.assertContains(response, self.class_obj.name)

    def test_teacher_can_upload_only_for_assigned_classes_and_valid_scores(self):
        self.client.force_login(self.teacher)
        upload_url = reverse('upload_results', args=[self.class_obj.pk, self.subject.pk])

        invalid_response = self.client.post(upload_url, {
            'term': 'TERM_1',
            f'exam_{self.student_user.student_profile.pk}': '120',
            f'assignment_{self.student_user.student_profile.pk}': '90',
        })
        self.assertEqual(invalid_response.status_code, 200)
        self.assertFalse(SubjectResult.objects.exists())
        self.assertContains(invalid_response, 'must be between 0 and 100')

        valid_response = self.client.post(upload_url, {
            'term': 'TERM_1',
            f'exam_{self.student_user.student_profile.pk}': '82.5',
            f'assignment_{self.student_user.student_profile.pk}': '90',
        })
        self.assertRedirects(valid_response, upload_url)
        result = SubjectResult.objects.get()
        self.assertEqual(result.student, self.student_user.student_profile)
        self.assertEqual(result.created_by, self.teacher.staff_profile)

        self.client.force_login(self.other_teacher)
        denied_response = self.client.get(upload_url)
        self.assertEqual(denied_response.status_code, 404)

    def test_class_teacher_results_are_limited_to_assigned_class(self):
        self.client.force_login(self.teacher)

        response = self.client.get(reverse('view_class_results', args=[self.class_obj.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'teacher/view_class_results.html')
        self.assertContains(response, self.student_user.username)

        self.client.force_login(self.other_teacher)
        denied_response = self.client.get(reverse('view_class_results', args=[self.class_obj.pk]))
        self.assertEqual(denied_response.status_code, 404)

    def test_teacher_profile_edit_updates_only_permitted_fields(self):
        self.client.force_login(self.teacher)

        response = self.client.post(reverse('staff_profile_save'), {
            'first_name': 'Taylor',
            'last_name': 'Teacher',
            'address': 'School staff quarters',
        })

        self.assertRedirects(response, reverse('staff_profile'))
        self.teacher.refresh_from_db()
        self.assertEqual(self.teacher.first_name, 'Taylor')
        self.assertEqual(self.teacher.address, 'School staff quarters')
        self.assertEqual(self.teacher.user_type, 2)

    def test_legacy_staff_post_endpoint_requires_csrf(self):
        csrf_client = self.client_class(enforce_csrf_checks=True)
        csrf_client.force_login(self.teacher)

        response = csrf_client.post(reverse('staff_feedback_save'), {'feedback_msg': 'Hello'})

        self.assertEqual(response.status_code, 403)

    def test_attendance_page_uses_only_current_assigned_classes(self):
        self.client.force_login(self.teacher)

        response = self.client.get(reverse('staff_take_attendance'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.subject.name)
        self.assertContains(response, self.class_obj.name)
        self.assertContains(response, reverse('get_students'))

        invalid_response = self.client.post(reverse('get_students'), {
            'assignment_id': 'not-an-id',
            'class_id': self.class_obj.pk,
        })
        self.assertEqual(invalid_response.status_code, 404)

        self.client.force_login(self.other_teacher)
        response = self.client.post(reverse('get_students'), {
            'assignment_id': self.assignment.pk,
            'class_id': self.class_obj.pk,
        })
        self.assertEqual(response.status_code, 404)

    def test_attendance_requires_complete_student_data_and_rejects_duplicate_dates(self):
        self.client.force_login(self.teacher)
        extra_student = User.objects.create_user(
            username='second-attendance-student',
            password='test-password',
            user_type=3,
        )
        extra_student.student_profile.gender = 'F'
        extra_student.student_profile.current_class = self.class_obj
        extra_student.student_profile.academic_year = self.year
        extra_student.student_profile.save()
        url = reverse('save_attendance_data')
        post_data = {
            'assignment_id': self.assignment.pk,
            'class_id': self.class_obj.pk,
            'attendance_date': '2028-04-15',
            'student_ids': self.attendance_payload(),
        }

        incomplete_response = self.client.post(url, post_data)
        self.assertEqual(incomplete_response.status_code, 400)
        self.assertFalse(Attendance.objects.exists())

        post_data['student_ids'] = json.dumps([
            {'id': self.student_user.student_profile.pk, 'status': True},
            {'id': extra_student.student_profile.pk, 'status': False},
        ])
        saved_response = self.client.post(url, post_data)
        self.assertEqual(saved_response.status_code, 200)
        self.assertEqual(AttendanceReport.objects.filter(status='P').count(), 1)
        self.assertEqual(AttendanceReport.objects.filter(status='A').count(), 1)

        duplicate_response = self.client.post(url, post_data)
        self.assertEqual(duplicate_response.status_code, 409)
        self.assertEqual(Attendance.objects.count(), 1)

    def test_attendance_updates_are_limited_to_the_teacher_assignment(self):
        self.client.force_login(self.teacher)
        attendance = Attendance.objects.create(
            subject=self.subject,
            class_obj=self.class_obj,
            academic_year=self.year,
            attendance_date=date(2028, 4, 15),
            created_by=self.teacher.staff_profile,
        )
        report = AttendanceReport.objects.create(
            attendance=attendance,
            student=self.student_user.student_profile,
            status='P',
        )
        request_data = {
            'assignment_id': self.assignment.pk,
            'class_id': self.class_obj.pk,
            'attendance_id': attendance.pk,
        }

        dates_response = self.client.post(reverse('get_attendance_dates'), request_data)
        self.assertEqual(dates_response.status_code, 200)
        self.assertEqual(dates_response.json()['attendance'][0]['id'], attendance.pk)

        detail_response = self.client.post(reverse('get_attendance_student'), request_data)
        self.assertEqual(detail_response.status_code, 200)
        self.assertTrue(detail_response.json()['students'][0]['status'])

        request_data['student_ids'] = self.attendance_payload(status=0)
        update_response = self.client.post(reverse('save_updateattendance_data'), request_data)
        self.assertEqual(update_response.status_code, 200)
        report.refresh_from_db()
        self.assertEqual(report.status, 'A')

        self.client.force_login(self.other_teacher)
        denied_response = self.client.post(reverse('save_updateattendance_data'), request_data)
        self.assertEqual(denied_response.status_code, 404)

    def test_attendance_api_requires_csrf(self):
        csrf_client = self.client_class(enforce_csrf_checks=True)
        csrf_client.force_login(self.teacher)

        response = csrf_client.post(reverse('get_students'), {
            'assignment_id': self.assignment.pk,
            'class_id': self.class_obj.pk,
        })

        self.assertEqual(response.status_code, 403)

    def test_teacher_leave_requests_use_current_fields_and_validate_dates(self):
        self.client.force_login(self.teacher)
        leave_url = reverse('staff_apply_leave_save')

        invalid_response = self.client.post(leave_url, {
            'leave_type': 'Annual',
            'start_date': '2028-06-12',
            'end_date': '2028-06-10',
            'reason': 'Family commitment',
        })
        self.assertRedirects(invalid_response, reverse('staff_apply_leave'))
        self.assertFalse(LeaveRequest.objects.exists())

        response = self.client.post(leave_url, {
            'leave_type': 'Annual',
            'start_date': '2028-06-10',
            'end_date': '2028-06-12',
            'reason': 'Family commitment',
        })
        self.assertRedirects(response, reverse('staff_apply_leave'))
        leave = LeaveRequest.objects.get()
        self.assertEqual(leave.applicant, self.teacher)
        self.assertEqual(leave.start_date, date(2028, 6, 10))
        self.assertEqual(leave.end_date, date(2028, 6, 12))

        history_response = self.client.get(reverse('staff_apply_leave'))
        self.assertContains(history_response, 'Family commitment')
        self.assertContains(history_response, 'Pending')

    def test_teacher_feedback_uses_current_fields_and_is_private_to_the_sender(self):
        self.client.force_login(self.teacher)

        response = self.client.post(reverse('staff_feedback_save'), {
            'feedback_msg': 'Please review the timetable.',
        })

        self.assertRedirects(response, reverse('staff_feedback'))
        feedback = Feedback.objects.get()
        self.assertEqual(feedback.user, self.teacher)
        self.assertEqual(feedback.message, 'Please review the timetable.')

        Feedback.objects.create(
            user=self.other_teacher,
            message='Private feedback from another teacher.',
        )
        history_response = self.client.get(reverse('staff_feedback'))
        self.assertContains(history_response, 'Please review the timetable.')
        self.assertNotContains(history_response, 'Private feedback from another teacher.')

    def test_legacy_result_pages_redirect_to_the_current_results_workflow(self):
        self.client.force_login(self.teacher)
        dashboard_url = reverse('teacher_dashboard')

        for route in ('staff_add_result', 'edit_student_result'):
            with self.subTest(route=route):
                response = self.client.get(reverse(route))
                self.assertRedirects(response, dashboard_url)

        response = self.client.post(reverse('save_student_result'), {})
        self.assertRedirects(response, dashboard_url)
        response = self.client.post(reverse('fetch_student_result'), {})
        self.assertRedirects(response, dashboard_url)


class AdminManagementTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username='school-admin',
            password='test-password',
            user_type=1,
        )
        self.teacher_user = User.objects.create_user(
            username='teacher-user',
            password='test-password',
            user_type=2,
        )
        self.student_user = User.objects.create_user(
            username='student-user',
            password='test-password',
            user_type=3,
        )
        self.student_user.student_profile.gender = 'F'
        self.academic_year = AcademicYear.objects.create(
            name='2027',
            start_date=date(2027, 1, 1),
            end_date=date(2027, 12, 31),
            is_current=True,
        )
        self.student_class = StudentClass.objects.create(
            name='Grade 6',
            academic_year=self.academic_year,
        )
        self.student_user.student_profile.current_class = self.student_class
        self.student_user.student_profile.academic_year = self.academic_year
        self.student_user.student_profile.save()
        self.subject = Subject.objects.create(
            name='Mathematics',
            code='MATH6',
        )

    def test_admin_pages_and_report_forms_render(self):
        self.client.force_login(self.admin)
        routes = (
            ('admin_dashboard', ()),
            ('manage_students', ()),
            ('view_student', (self.student_user.student_profile.pk,)),
            ('manage_teachers', ()),
            ('teacher_subjects', (self.teacher_user.staff_profile.pk,)),
            ('manage_classes', ()),
            ('manage_subject', ()),
            ('edit_subject', (self.subject.pk,)),
            ('manage_finance', ()),
            ('fee_payments', ()),
            ('expenses', ()),
            ('generate_reports', ()),
            ('generate_attendance_report', ()),
            ('generate_finance_report', ()),
        )
        for route, args in routes:
            with self.subTest(route=route):
                response = self.client.get(reverse(route, args=args))
                self.assertEqual(response.status_code, 200)
        self.assertRedirects(
            self.client.get(reverse('admin_home')),
            reverse('admin_dashboard'),
        )

    def test_admin_student_search_uses_user_username_and_ignores_invalid_class(self):
        self.client.force_login(self.admin)

        response = self.client.get(reverse('manage_students'), {
            'search': 'student-user',
            'class': 'not-a-class-id',
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'student-user')
        self.assertContains(response, 'Grade 6')

    def test_subject_can_be_updated_without_changing_its_code(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse('edit_subject', args=[self.subject.pk]), {
            'name': 'Mathematics and Numeracy',
            'code': 'MATH6',
            'description': 'Updated curriculum description.',
        })

        self.assertRedirects(response, reverse('manage_subject'))
        self.subject.refresh_from_db()
        self.assertEqual(self.subject.name, 'Mathematics and Numeracy')

    def test_destructive_admin_actions_require_post(self):
        self.client.force_login(self.admin)
        urls = (
            reverse('delete_class', args=[self.student_class.pk]),
            reverse('delete_teacher', args=[self.teacher_user.staff_profile.pk]),
            reverse('deactivate_student', args=[self.student_user.student_profile.pk]),
        )
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 405)

    def test_legacy_admin_endpoints_are_restricted_to_admin_users(self):
        for user in (None, self.student_user):
            if user is None:
                self.client.logout()
            else:
                self.client.force_login(user)
            response = self.client.get(reverse('admin_home'))
            self.assertEqual(response.status_code, 302)
