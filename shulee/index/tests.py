from datetime import date, timedelta
from io import BytesIO
import json
import re
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from decimal import Decimal

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
    CashPaymentApproval,
    Expense,
    Feedback,
    FeePayment,
    FeeStructure,
    FeeTransaction,
    LeaveRequest,
    MpesaPayment,
    Notification,
    SchoolProfile,
    SchoolEvent,
    ResultPublication,
    Staff,
    StaffSubjectAssignment,
    SubjectResultSubmission,
    StudentApplication,
    STANDARD_CLASS_NAMES,
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

    def test_public_events_are_visible_to_anonymous_visitors(self):
        response = self.client.get(reverse('events'))

        self.assertContains(response, 'Reading Day')

    def test_targeted_class_events_reach_only_intended_students(self):
        year = AcademicYear.objects.filter(is_current=True).first() or AcademicYear.objects.create(
            name='2026', start_date=timezone.localdate(), end_date=timezone.localdate() + timedelta(days=300),
            is_current=True,
        )
        teacher = User.objects.create_user(username='ct', password='test-password', user_type=2)
        klass = StudentClass.objects.create(name='Events Class', academic_year=year, class_teacher=teacher.staff_profile)
        other = User.objects.create_user(username='s2', password='test-password', user_type=3)
        third = User.objects.create_user(username='s3', password='test-password', user_type=3)
        for u in (self.student_user, other, third):
            p = u.student_profile
            p.gender = 'F'
            p.current_class = klass
            p.academic_year = year
            p.save()
        url = reverse('class_teacher_events', args=[klass.pk])
        payload = {
            'title': 'Parents Evening', 'description': 'Parents meet', 'starts_at': '2099-01-01T10:00',
            'location': 'Hall', 'send_to': 'selected', 'recipients': [other.student_profile.pk],
        }
        self.client.force_login(teacher)
        self.assertRedirects(self.client.post(url, payload), url)
        self.assertEqual(SchoolEvent.objects.get(title='Parents Evening').recipients.count(), 1)
        payload.update(title='Whole class', send_to='all', recipients=[])
        self.client.post(url, payload)

        self.client.force_login(other)
        page = self.client.get(reverse('events'))
        self.assertContains(page, 'Parents Evening')
        self.assertContains(page, 'Whole class')
        self.client.force_login(third)
        page = self.client.get(reverse('events'))
        self.assertNotContains(page, 'Parents Evening')
        self.assertContains(page, 'Whole class')
        self.client.logout()
        page = self.client.get(reverse('events'))
        self.assertNotContains(page, 'Parents Evening')
        self.assertNotContains(page, 'Whole class')
        self.assertContains(page, 'Reading Day')

        self.client.force_login(self.student_user)
        self.assertEqual(self.client.get(url).status_code, 403)

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

    def test_invalid_login_redirects_back_to_login_with_error(self):
        response = self.client.post(reverse('do_login'), {
            'email': self.user.email,
            'password': 'incorrect-password',
        }, follow=True)

        self.assertRedirects(response, reverse('show_login'))
        self.assertContains(response, 'Invalid Login Details')

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
        AcademicYear.objects.filter(is_current=True).update(is_current=False)
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
            'parent_email': 'parent@example.com',
            'address': 'School Road',
            'academic_year': str(self.year.pk),
            'current_class': str(self.class_obj.pk),
            'gender': 'F',
            'date_of_birth': str(date.today().replace(year=date.today().year - 8, day=1)),
            'password': 'unique-long-password-8472',
        }

    def test_application_rejects_underage_future_and_missing_birth_dates(self):
        today = date.today()
        for value in (str(today), str(today.replace(year=today.year - 3, day=1)),
                      str(today + timedelta(days=30)), str(today.replace(year=today.year - 30, day=1)), ''):
            with self.subTest(dob=value):
                response = self.client.post(
                    reverse('submit_application'), {**self.student_signup_data(), 'date_of_birth': value})
                self.assertEqual(response.status_code, 400)
                self.assertIn('date_of_birth', response.context['form'].errors)
        self.assertFalse(User.objects.filter(username='new-student').exists())

    def test_apply_page_renders_single_functional_form(self):
        response = self.client.get(reverse('apply'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'base.html')
        self.assertContains(response, reverse('submit_application'))
        self.assertContains(response, 'name="first_name"')

    def test_application_without_username_gets_temporary_login_and_confirmation(self):
        data = self.student_signup_data()
        data.pop('username')
        response = self.client.post(reverse('submit_application'), data)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(username__startswith='APP').exists())

    def test_student_signup_rejects_non_image_upload_without_saving_file_or_user(self):
        with TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                response = self.client.post(
                    reverse('submit_application'),
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
                    reverse('submit_application'),
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
                self.assertEqual(user.student_profile.parent_email, 'parent@example.com')
                self.assertFalse(user.student_profile.active)
                self.assertEqual(user.student_profile.application.status, 'PENDING')
                self.assertEqual(user.student_profile.get_fee_balance(), Decimal('0.00'))
                self.assertFalse(FeeTransaction.objects.filter(student=user.student_profile).exists())
                self.assertRegex(user.profile_pic.name, r'^profile_pics/[0-9a-f]{32}\.jpg$')
                with user.profile_pic.open('rb') as stored_image:
                    self.assertTrue(stored_image.read(3).startswith(b'\xff\xd8\xff'))

    def test_parent_email_is_required_for_student_application(self):
        data = self.student_signup_data()
        data.pop('parent_email')

        response = self.client.post(reverse('submit_application'), data)

        self.assertEqual(response.status_code, 400)
        self.assertFalse(User.objects.filter(username='new-student').exists())

    def test_headteacher_can_schedule_interview_and_approve_applicant(self):
        response = self.client.post(reverse('submit_application'), self.student_signup_data())
        self.assertEqual(response.status_code, 302)
        student_user = User.objects.get(username='new-student')
        application = StudentApplication.objects.get(student=student_user.student_profile)

        self.client.force_login(self.admin)
        response = self.client.get(reverse('review_student_applications'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'parent@example.com')
        self.assertContains(response, 'Student Example')

        response = self.client.post(
            reverse('review_student_application', args=[application.pk]),
            {
                'action': 'schedule',
                'interview_at': '2099-05-12T10:30',
                'review_notes': 'Bring the latest school report.',
            },
        )
        self.assertRedirects(response, reverse('review_student_applications'))
        application.refresh_from_db()
        self.assertEqual(application.status, 'INTERVIEW')
        self.assertIsNotNone(application.interview_at)

        response = self.client.post(
            reverse('review_student_application', args=[application.pk]),
            {
                'action': 'approve',
                'review_notes': 'Approved after interview.',
            },
        )
        self.assertRedirects(response, reverse('review_student_applications'))
        application.refresh_from_db()
        student_user.student_profile.refresh_from_db()
        self.assertEqual(application.status, 'APPROVED')
        self.assertTrue(student_user.student_profile.active)
        student_user.refresh_from_db()
        self.assertEqual(student_user.username, student_user.student_profile.admission_number)
        self.assertRegex(student_user.username, r'^\d{4}')
        self.assertEqual(student_user.student_profile.get_fee_balance(), Decimal('0.00'))
        self.assertFalse(FeeTransaction.objects.filter(student=student_user.student_profile).exists())

        self.client.force_login(student_user)
        dashboard = self.client.get(reverse('student_home'))
        self.assertEqual(dashboard.status_code, 200)
        self.assertEqual(dashboard.context['fee_balance'], Decimal('0.00'))

    def test_applicant_can_track_status_but_cannot_open_student_portal_until_approved(self):
        self.client.post(reverse('submit_application'), self.student_signup_data())
        student_user = User.objects.get(username='new-student')
        self.client.post(reverse('do_login'), {
            'email': 'new-student',
            'password': 'unique-long-password-8472',
        })

        status_response = self.client.get(reverse('student_application_status'))
        self.assertEqual(status_response.status_code, 200)
        self.assertContains(status_response, 'Application under review')
        portal_response = self.client.get(reverse('student_home'))
        self.assertRedirects(portal_response, reverse('student_application_status'))

        application = student_user.student_profile.application
        self.client.force_login(self.admin)
        approval_response = self.client.post(
            reverse('review_student_application', args=[application.pk]),
            {'action': 'approve', 'review_notes': ''},
        )
        self.assertEqual(approval_response.status_code, 302)
        application.refresh_from_db()
        self.assertEqual(application.status, 'APPROVED')
        self.assertTrue(Student.objects.get(pk=student_user.student_profile.pk).active)
        self.client.force_login(student_user)
        portal_response = self.client.get(reverse('student_home'))
        self.assertEqual(portal_response.status_code, 200)

    def test_admin_add_student_reuses_signal_created_profile(self):
        self.client.force_login(self.admin)

        response = self.client.post(reverse('add_student'), {
            'first_name': 'Manually',
            'last_name': 'Added',
            'email': '',
            'parent_email': 'guardian@example.com',
            'username': 'manual-admission',
            'password': 'Strong-Password-8274!',
            'confirm_password': 'Strong-Password-8274!',
            'gender': 'F',
            'date_of_birth': '',
            'current_class': str(self.class_obj.pk),
            'academic_year': str(self.year.pk),
            'father_name': '',
            'mother_name': '',
            'active': 'on',
        })

        self.assertRedirects(response, reverse('manage_students'))
        user = User.objects.get(username='manual-admission')
        self.assertEqual(user.student_profile.parent_email, 'guardian@example.com')
        self.assertEqual(Student.objects.filter(user=user).count(), 1)
        self.assertEqual(user.student_profile.get_fee_balance(), Decimal('0.00'))
        self.assertFalse(user.student_profile.fee_transactions.exists())


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
        AcademicYear.objects.filter(is_current=True).update(is_current=False)
        self.academic_year = AcademicYear.objects.create(
            name='2026-test',
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

    def test_record_payment_loads_student_balance_and_fee_structures_without_selector(self):
        FeePayment.objects.create(
            student=self.student,
            fee_structure=self.fee_structure,
            amount='1500.00',
            payment_method='BANK',
            transaction_code='BANK-1500',
        )
        self.client.force_login(self.bursar_user)

        response = self.client.get(reverse('record_payment', args=[self.student.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['student'].pk, self.student.pk)
        self.assertEqual(response.context['total_fee_due'], Decimal('12000.00'))
        self.assertEqual(response.context['total_paid'], Decimal('1500.00'))
        self.assertEqual(response.context['fee_balance'], Decimal('10500.00'))
        self.assertEqual(list(response.context['fee_structures']), [self.fee_structure])
        self.assertNotIn('fee_structure', response.context['form'].fields)
        self.assertContains(response, 'Student ID:')
        self.assertContains(response, 'Outstanding fees')

    def test_bursar_payment_uses_student_class_fee_structure_and_updates_balance(self):
        self.client.force_login(self.bursar_user)

        response = self.client.post(reverse('record_payment', args=[self.student.pk]), {
            'amount': '2500.00',
            'payment_date': '2026-01-15',
            'payment_method': 'BANK',
            'transaction_code': 'BANK-001',
            'notes': 'Bank payment',
        })

        self.assertRedirects(response, reverse('fee_records'))
        payment = FeePayment.objects.get(transaction_code='BANK-001')
        self.assertEqual(payment.fee_structure, self.fee_structure)
        transaction = FeeTransaction.objects.get(fee_payment=payment)
        self.assertEqual(transaction.balance, Decimal('9500.00'))
        self.assertEqual(self.student.get_fee_balance(), Decimal('9500.00'))

    def test_cash_payment_requires_headteacher_approval_before_ledger_update(self):
        FeeTransaction.objects.create(
            student=self.student,
            transaction_type='INVOICE',
            amount='12000.00',
            balance='12000.00',
            description='School fee invoice',
        )
        self.client.force_login(self.bursar_user)
        response = self.client.post(reverse('record_payment', args=[self.student.pk]), {
            'fee_structure': self.fee_structure.pk,
            'amount': '2500.00',
            'payment_date': '2026-01-15',
            'payment_method': 'CASH',
            'transaction_code': 'CASH-001',
            'notes': 'Cash received at the office',
        })

        self.assertRedirects(response, reverse('fee_records'))
        approval = CashPaymentApproval.objects.get()
        self.assertEqual(approval.status, 'PENDING')
        self.assertFalse(FeePayment.objects.exists())
        self.assertEqual(self.student.get_fee_balance(), Decimal('12000.00'))

        self.client.force_login(self.admin_user)
        review_response = self.client.get(reverse('review_cash_payments'))
        self.assertEqual(review_response.status_code, 200)
        self.assertContains(review_response, 'CASH-001')
        dashboard_response = self.client.get(reverse('admin_dashboard'))
        self.assertEqual(dashboard_response.status_code, 200)
        self.assertEqual(dashboard_response.context['stats']['pending_cash_payments'], 1)
        self.assertContains(dashboard_response, 'Cash fee approvals')

        response = self.client.post(reverse('decide_cash_payment', args=[approval.pk]), {
            'decision': 'approve',
            'review_note': 'Receipt checked',
        })
        self.assertRedirects(response, reverse('review_cash_payments'))
        approval.refresh_from_db()
        self.assertEqual(approval.status, 'APPROVED')
        self.assertEqual(approval.reviewed_by, self.admin_user)
        self.assertEqual(FeePayment.objects.get().amount, Decimal('2500.00'))
        self.assertEqual(self.student.get_fee_balance(), Decimal('9500.00'))


    def test_bursar_can_record_payment_and_is_attributed(self):
        FeeTransaction.objects.create(
            student=self.student,
            transaction_type='INVOICE',
            amount='12000.00',
            balance='12000.00',
            description='School fee invoice',
        )
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
        approval = CashPaymentApproval.objects.get()
        self.assertEqual(approval.recorded_by, self.bursar_user.bursar_profile)
        self.assertEqual(approval.status, 'PENDING')
        self.assertFalse(FeePayment.objects.exists())

    def test_bursar_can_create_fee_structure(self):
        self.client.force_login(self.bursar_user)
        response = self.client.post(reverse('fee_records'), {
            'name': 'Boarding',
            'description': 'Boarding fees',
            'amount': '8000.00',
            'class_obj': str(self.student_class.pk),
            'academic_year': str(self.academic_year.pk),
            'due_date': '2026-03-01',
            'category': 'BOARDING',
            'applies_to': 'BOARDER',
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

    def test_admin_can_edit_bursar_accounts_but_not_create_them(self):
        self.client.force_login(self.admin_user)
        new_bursar = self.bursar_user.bursar_profile

        response = self.client.post(reverse('edit_bursar', args=[new_bursar.pk]), {
            'first_name': 'Edited',
            'last_name': 'Accountant',
            'email': 'accountant@example.com',
            'username': 'accountant',
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


@override_settings(
    MPESA_ENVIRONMENT='sandbox',
    MPESA_CONSUMER_KEY='test-key',
    MPESA_CONSUMER_SECRET='test-secret',
    MPESA_SHORTCODE='174379',
    MPESA_PASSKEY='test-passkey',
    MPESA_CALLBACK_URL='https://school.example/payments/mpesa/callback/',
    SCHOOL_MPESA_PAYBILL='123456',
)
class StudentPortalTests(TestCase):
    def setUp(self):
        self.teacher_user = User.objects.create_user(
            username='class-teacher',
            first_name='Grace',
            last_name='Teacher',
            email='grace@example.com',
            password='test-password',
            user_type=2,
        )
        self.student_user = User.objects.create_user(
            username='portal-pupil',
            first_name='Amina',
            last_name='Learner',
            phone='0712345678',
            password='test-password',
            user_type=3,
        )
        self.other_student_user = User.objects.create_user(
            username='another-pupil',
            password='test-password',
            user_type=3,
        )
        AcademicYear.objects.filter(is_current=True).update(is_current=False)
        self.year = AcademicYear.objects.create(
            name='2030',
            start_date=date(2030, 1, 1),
            end_date=date(2030, 12, 31),
            is_current=True,
        )
        self.class_obj = StudentClass.objects.create(
            name='Grade 7',
            academic_year=self.year,
            class_teacher=self.teacher_user.staff_profile,
        )
        self.student = self.student_user.student_profile
        self.student.gender = 'F'
        self.student.current_class = self.class_obj
        self.student.academic_year = self.year
        self.student.save()
        self.other_student = self.other_student_user.student_profile
        self.other_student.gender = 'F'
        self.other_student.current_class = self.class_obj
        self.other_student.academic_year = self.year
        self.other_student.save()
        self.subject = Subject.objects.create(name='Science', code='SCI7')
        self.fee_structure = FeeStructure.objects.create(
            name='Term One',
            amount='1000.00',
            class_obj=self.class_obj,
            academic_year=self.year,
            due_date=date(2030, 3, 1),
        )
        FeeTransaction.objects.create(
            student=self.student,
            transaction_type='INVOICE',
            amount='1000.00',
            balance='1000.00',
            description='Term One invoice',
        )

    def test_dashboard_and_results_are_scoped_to_authenticated_student(self):
        SubjectResult.objects.create(
            student=self.student,
            subject=self.subject,
            academic_year=self.year,
            term='TERM_1',
            exam_score='80',
            assignment_score='70',
        )
        SubjectResult.objects.create(
            student=self.other_student,
            subject=self.subject,
            academic_year=self.year,
            term='TERM_1',
            exam_score='25',
            assignment_score='20',
        )
        ResultPublication.objects.create(
            class_obj=self.class_obj,
            academic_year=self.year,
            term='TERM_1',
            status='APPROVED',
            submitted_by=self.teacher_user.staff_profile,
        )
        self.client.force_login(self.student_user)

        dashboard = self.client.get(reverse('student_home'))
        self.assertEqual(dashboard.status_code, 200)
        self.assertEqual(dashboard.context['fee_balance'], Decimal('1000.00'))
        self.assertEqual(dashboard.context['term_scores'], [75.0])
        self.assertContains(dashboard, 'Contact administration')
        self.assertTemplateUsed(dashboard, 'student_template/base.html')
        self.assertContains(dashboard, 'Student Portal')
        self.assertContains(dashboard, 'Results &amp; progress')
        self.assertNotContains(dashboard, 'main-header')
        self.assertNotContains(dashboard, 'main-footer')
        self.assertNotContains(dashboard, 'Login to Portal')
        self.assertNotContains(dashboard, 'Apply Now')
        self.assertNotContains(dashboard, 'AdminLTE')
        self.assertNotContains(dashboard, 'Attendance rate')
        self.assertNotContains(dashboard, 'Apply for Leave')
        self.assertEqual(self.client.get('/student_view_attendance').status_code, 404)
        self.assertEqual(self.client.get('/student_apply_leave').status_code, 404)

        results_response = self.client.get(reverse('student_view_result'))
        self.assertEqual(results_response.status_code, 200)
        self.assertContains(results_response, '80')
        self.assertNotContains(results_response, '25.0%')

        self.client.force_login(self.teacher_user)
        denied = self.client.get(reverse('student_home'))
        self.assertEqual(denied.status_code, 403)

    @patch('index.StudentViews.initiate_stk_push')
    def test_student_can_start_partial_mpesa_payment_without_early_credit(self, initiate):
        initiate.return_value = {
            'ResponseCode': '0',
            'MerchantRequestID': 'merchant-1',
            'CheckoutRequestID': 'checkout-1',
        }
        self.client.force_login(self.student_user)

        response = self.client.post(reverse('make_fee_payment'), {
            'amount': '400',
            'phone_number': '0712345678',
        })

        self.assertRedirects(response, reverse('student_fee_payments'))
        initiate.assert_called_once_with(
            phone_number='254712345678',
            amount=400,
            account_reference='AminaLearner',
            transaction_desc='School fee Grade 7',
        )
        payment = MpesaPayment.objects.get()
        self.assertEqual(payment.status, 'PENDING')
        self.assertFalse(FeePayment.objects.exists())
        self.assertEqual(self.student.get_fee_balance(), Decimal('1000.00'))

    @patch('index.StudentViews.initiate_stk_push')
    def test_payment_request_cannot_exceed_balance_reserved_by_pending_payments(self, initiate):
        MpesaPayment.objects.create(
            student=self.student,
            amount='700.00',
            phone_number='254712345678',
            account_reference='AminaLearner',
            checkout_request_id='existing-pending-payment',
        )
        self.client.force_login(self.student_user)

        response = self.client.post(reverse('make_fee_payment'), {
            'amount': '400',
            'phone_number': '0712345678',
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Payment cannot exceed the outstanding balance')
        self.assertContains(response, 'Ksh 300.00')
        self.assertEqual(response.context['payment_limit'], Decimal('300.00'))
        initiate.assert_not_called()
        self.assertEqual(MpesaPayment.objects.count(), 1)

    @patch('index.StudentViews.initiate_stk_push')
    def test_payment_form_caps_maximum_at_whole_shillings_available(self, initiate):
        FeeTransaction.objects.filter(student=self.student).delete()
        self.fee_structure.amount = Decimal('1000.50')
        self.fee_structure.save(update_fields=['amount'])
        FeeTransaction.objects.create(
            student=self.student,
            transaction_type='INVOICE',
            amount='1000.50',
            balance='1000.50',
            description='Fractional balance regression',
        )
        self.client.force_login(self.student_user)

        response = self.client.get(reverse('make_fee_payment'))

        self.assertContains(response, 'max="1000"')
        self.assertEqual(response.context['payment_limit'], Decimal('1000'))
        initiate.assert_not_called()

    def test_fee_payment_history_combines_methods_and_statuses_without_duplicates(self):
        bursar_user = User.objects.create_user(
            username='history-bursar',
            password='test-password',
            user_type=4,
        )
        FeePayment.objects.create(
            student=self.student,
            amount='150.00',
            payment_method='CASH',
            transaction_code='CASH-150',
        )
        CashPaymentApproval.objects.create(
            student=self.student,
            amount='200.00',
            transaction_code='CASH-PENDING',
            recorded_by=bursar_user.bursar_profile,
        )
        approved_cash = FeePayment.objects.create(
            student=self.student,
            amount='250.00',
            payment_method='CASH',
            transaction_code='CASH-250',
        )
        CashPaymentApproval.objects.create(
            student=self.student,
            amount='250.00',
            transaction_code='CASH-250',
            recorded_by=bursar_user.bursar_profile,
            status='APPROVED',
            fee_payment=approved_cash,
        )
        MpesaPayment.objects.create(
            student=self.student,
            amount='300.00',
            phone_number='254712345678',
            account_reference='AminaLearner',
            checkout_request_id='paid-checkout',
            receipt_number='MPESA-300',
            status='PAID',
        )
        FeePayment.objects.create(
            student=self.student,
            amount='300.00',
            payment_method='MPESA',
            transaction_code='MPESA-300',
        )
        MpesaPayment.objects.create(
            student=self.student,
            amount='400.00',
            phone_number='254712345678',
            account_reference='AminaLearner',
            checkout_request_id='pending-checkout',
        )
        self.client.force_login(self.student_user)

        response = self.client.get(reverse('student_fee_payments'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['payment_history']), 5)
        self.assertEqual(response.content.count(b'<table'), 1)
        self.assertContains(response, 'Cash')
        self.assertContains(response, 'M-Pesa')
        self.assertContains(response, 'Paid')
        self.assertContains(response, 'Pending confirmation')
        self.assertContains(response, 'Pending headteacher approval')
        self.assertContains(response, 'MPESA-300')
        self.assertEqual(response.content.count(b'MPESA-300'), 1)

    @patch('index.StudentViews.query_stk_push')
    def test_only_provider_verified_callback_updates_balance_and_is_idempotent(self, query):
        payment = MpesaPayment.objects.create(
            student=self.student,
            amount='400.00',
            phone_number='254712345678',
            account_reference='AminaLearner',
            merchant_request_id='merchant-1',
            checkout_request_id='checkout-1',
        )
        callback = {
            'Body': {
                'stkCallback': {
                    'MerchantRequestID': 'merchant-1',
                    'CheckoutRequestID': 'checkout-1',
                    'ResultCode': 0,
                    'ResultDesc': 'The service request is processed successfully.',
                    'CallbackMetadata': {'Item': [
                        {'Name': 'Amount', 'Value': 400},
                        {'Name': 'MpesaReceiptNumber', 'Value': 'QAZ1234567'},
                    ]},
                },
            },
        }
        self.client.force_login(self.student_user)
        query.return_value = {'ResultCode': '1032', 'ResultDesc': 'Cancelled'}
        unverified = self.client.post(
            reverse('mpesa_stk_callback'),
            data=json.dumps(callback),
            content_type='application/json',
        )
        self.assertEqual(unverified.status_code, 200)
        self.assertFalse(FeePayment.objects.exists())
        self.assertEqual(payment.status, 'PENDING')

        query.return_value = {'ResultCode': '0', 'ResultDesc': 'Confirmed'}
        confirmed = self.client.post(
            reverse('mpesa_stk_callback'),
            data=json.dumps(callback),
            content_type='application/json',
        )
        self.assertEqual(confirmed.status_code, 200)
        payment.refresh_from_db()
        self.assertEqual(payment.status, 'PAID')
        self.assertEqual(payment.receipt_number, 'QAZ1234567')
        fee_payment = FeePayment.objects.get()
        self.assertEqual(fee_payment.fee_structure, self.fee_structure)
        self.assertEqual(self.student.get_fee_balance(), Decimal('600.00'))

        repeated = self.client.post(
            reverse('mpesa_stk_callback'),
            data=json.dumps(callback),
            content_type='application/json',
        )
        self.assertEqual(repeated.status_code, 200)
        self.assertEqual(FeePayment.objects.count(), 1)

    def test_failed_mpesa_callback_releases_reserved_balance(self):
        payment = MpesaPayment.objects.create(
            student=self.student,
            amount='400.00',
            phone_number='254712345678',
            account_reference='AminaLearner',
            merchant_request_id='merchant-failed',
            checkout_request_id='checkout-failed',
        )
        callback = {
            'Body': {
                'stkCallback': {
                    'MerchantRequestID': 'merchant-failed',
                    'CheckoutRequestID': 'checkout-failed',
                    'ResultCode': 1032,
                    'ResultDesc': 'Request cancelled by user.',
                },
            },
        }

        response = self.client.post(
            reverse('mpesa_stk_callback'),
            data=json.dumps(callback),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        payment.refresh_from_db()
        self.assertEqual(payment.status, 'FAILED')
        self.assertEqual(payment.result_description, 'Request cancelled by user.')
        self.assertEqual(self.student.get_available_fee_balance(), Decimal('1000.00'))

    def test_student_feedback_goes_only_to_admin(self):
        admin = User.objects.create_user(username='fb-admin', password='x', user_type=1)
        self.client.force_login(self.student_user)
        sent = self.client.post(reverse('student_feedback_save'), {
            'feedback_msg': 'Could I ask about my Science result?',
        })
        self.assertRedirects(sent, reverse('student_feedback'))
        feedback = Feedback.objects.get()
        self.assertEqual(feedback.user, self.student_user)
        self.assertTrue(Notification.objects.filter(recipients=admin, title__icontains='feedback').exists())
        self.assertFalse(Notification.objects.filter(recipients=self.teacher_user).exists())

        self.client.force_login(admin)
        replied = self.client.post(reverse('respond_feedback', args=[feedback.pk]), {
            'reply': 'Please see me after class.',
        })
        self.assertEqual(replied.status_code, 302)
        feedback.refresh_from_db()
        self.assertEqual(feedback.reply, 'Please see me after class.')
        self.assertTrue(Notification.objects.filter(recipients=self.student_user).exists())

        self.client.force_login(self.other_student_user)
        hidden = self.client.get(reverse('student_feedback'))
        self.assertNotContains(hidden, 'Could I ask about my Science result?')

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
        AcademicYear.objects.filter(is_current=True).update(is_current=False)
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

    def test_class_teacher_records_attendance_once_per_day(self):
        profile = self.student_user.student_profile
        self.client.force_login(self.teacher)
        url = reverse('class_teacher_attendance', args=[self.class_obj.pk])
        today = timezone.localdate().isoformat()

        self.assertContains(self.client.get(url), 'portal-student')
        self.client.post(url, {'date': today, f'status_{profile.pk}': 'L'})
        report = AttendanceReport.objects.get(student=profile)
        self.assertEqual(report.status, 'L')
        self.assertIsNone(report.attendance.subject)

        self.client.post(url, {'date': today, f'status_{profile.pk}': 'P'})
        self.assertEqual(Attendance.objects.filter(subject__isnull=True).count(), 1)
        report.refresh_from_db()
        self.assertEqual(report.status, 'L')

        self.client.force_login(self.other_teacher)
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_class_teacher_sees_weekly_attendance_and_print_view(self):
        profile = self.student_user.student_profile
        self.client.force_login(self.teacher)
        url = reverse('class_teacher_attendance', args=[self.class_obj.pk])
        monday = date(2026, 3, 2)
        for offset, status in enumerate(['P', 'A', 'L']):
            self.client.post(url, {'date': (monday + timedelta(days=offset)).isoformat(), f'status_{profile.pk}': status})

        weekly = reverse('class_teacher_weekly_attendance', args=[self.class_obj.pk])
        response = self.client.get(weekly, {'week': '2026-03-04'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['week_start'], monday)
        row = response.context['rows'][0]
        self.assertEqual(row['cells'][:4], ['P', 'A', 'L', None])
        self.assertEqual((row['present'], row['absent']), (2, 1))
        self.assertEqual(len(response.context['weeks']), 1)

        printed = self.client.get(weekly, {'week': '2026-03-02', 'print': '1'})
        self.assertTemplateUsed(printed, 'teacher/class_attendance_print.html')

        self.client.force_login(self.other_teacher)
        self.assertEqual(self.client.get(weekly).status_code, 404)

    def test_student_admission_number_matches_username(self):
        profile = self.student_user.student_profile
        self.assertEqual(profile.admission_number, 'portal-student')
        self.student_user.username = '2028G00001'
        self.student_user.save()
        profile.refresh_from_db()
        self.assertEqual(profile.admission_number, '2028G00001')

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

    def test_teacher_cannot_submit_subject_results_when_a_student_is_missing(self):
        second_user = User.objects.create_user(
            username='second-results-student',
            password='test-password',
            user_type=3,
        )
        second_user.student_profile.gender = 'F'
        second_user.student_profile.current_class = self.class_obj
        second_user.student_profile.academic_year = self.year
        second_user.student_profile.save()
        self.client.force_login(self.teacher)
        upload_url = reverse('upload_results', args=[self.class_obj.pk, self.subject.pk])

        response = self.client.post(upload_url, {
            'term': 'TERM_1',
            'action': 'submit_subject',
            f'exam_{self.student_user.student_profile.pk}': '82',
            f'assignment_{self.student_user.student_profile.pk}': '90',
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'student result(s) are missing')
        self.assertFalse(SubjectResultSubmission.objects.exists())
        self.assertFalse(Notification.objects.exists())
        self.assertFalse(SubjectResult.objects.exists())

    def test_complete_subject_submission_notifies_headteacher_and_keeps_scores_private(self):
        second_user = User.objects.create_user(
            username='second-results-student',
            password='test-password',
            user_type=3,
        )
        second_user.student_profile.gender = 'F'
        second_user.student_profile.current_class = self.class_obj
        second_user.student_profile.academic_year = self.year
        second_user.student_profile.save()
        headteacher = User.objects.create_user(
            username='results-headteacher',
            password='test-password',
            user_type=1,
        )
        self.client.force_login(self.teacher)
        upload_url = reverse('upload_results', args=[self.class_obj.pk, self.subject.pk])

        response = self.client.post(upload_url, {
            'term': 'TERM_1',
            'action': 'submit_subject',
            f'exam_{self.student_user.student_profile.pk}': '82',
            f'assignment_{self.student_user.student_profile.pk}': '90',
            f'exam_{second_user.student_profile.pk}': '76',
            f'assignment_{second_user.student_profile.pk}': '85',
        })

        self.assertRedirects(response, upload_url)
        self.assertTrue(SubjectResultSubmission.objects.filter(
            class_obj=self.class_obj,
            subject=self.subject,
            term='TERM_1',
        ).exists())
        notification = Notification.objects.get()
        self.assertIn('sent English results', notification.message)
        self.assertIn('Grade 5', notification.message)
        self.assertIn(headteacher, notification.recipients.all())
        self.client.force_login(self.student_user)
        result_response = self.client.get(reverse('student_view_result'))
        self.assertEqual(result_response.status_code, 200)
        self.assertNotContains(result_response, '82.00')
        self.assertFalse(result_response.context['studentresult'].exists())

    def test_class_results_need_every_subject_and_headteacher_approval_to_publish(self):
        headteacher = User.objects.create_user(
            username='results-headteacher',
            password='test-password',
            user_type=1,
        )
        science = Subject.objects.create(name='Science', code='SCI5')
        science_assignment = StaffSubjectAssignment.objects.create(
            staff=self.other_teacher.staff_profile,
            subject=science,
            academic_year=self.year,
        )
        science_assignment.classes.add(self.class_obj)
        self.client.force_login(self.teacher)
        english_upload = reverse('upload_results', args=[self.class_obj.pk, self.subject.pk])
        self.client.post(english_upload, {
            'term': 'TERM_1',
            'action': 'submit_subject',
            f'exam_{self.student_user.student_profile.pk}': '82',
            f'assignment_{self.student_user.student_profile.pk}': '90',
        })
        submit_url = reverse('submit_class_results', args=[self.class_obj.pk])
        incomplete_response = self.client.post(submit_url, {'term': 'TERM_1'})
        self.assertRedirects(incomplete_response, reverse('class_teacher_dashboard'))
        self.assertFalse(ResultPublication.objects.exists())

        self.client.force_login(self.other_teacher)
        science_upload = reverse('upload_results', args=[self.class_obj.pk, science.pk])
        self.client.post(science_upload, {
            'term': 'TERM_1',
            'action': 'submit_subject',
            f'exam_{self.student_user.student_profile.pk}': '70',
            f'assignment_{self.student_user.student_profile.pk}': '80',
        })
        self.client.force_login(self.teacher)
        complete_response = self.client.post(submit_url, {'term': 'TERM_1'})
        self.assertRedirects(complete_response, reverse('class_teacher_dashboard'))
        publication = ResultPublication.objects.get()
        self.assertEqual(publication.status, 'SUBMITTED')
        self.assertTrue(Notification.objects.filter(
            recipients=headteacher,
            title='Grade 5 results awaiting approval',
        ).exists())

        review_url = reverse('review_result_publication', args=[publication.pk])
        self.client.force_login(self.other_teacher)
        denied_response = self.client.post(
            review_url,
            {'decision': 'approve', 'review_note': ''},
        )
        self.assertEqual(denied_response.status_code, 302)
        publication.refresh_from_db()
        self.assertEqual(publication.status, 'SUBMITTED')

        self.client.force_login(headteacher)
        self.client.post(review_url, {'decision': 'approve', 'review_note': ''})
        publication.refresh_from_db()
        self.assertEqual(publication.status, 'APPROVED')
        student_notification = Notification.objects.get(
            title='Results are available online',
        )
        self.assertIn(self.student_user, student_notification.recipients.all())

        self.client.force_login(self.student_user)
        result_response = self.client.get(reverse('student_view_result'))
        self.assertEqual(result_response.status_code, 200)
        self.assertEqual(result_response.context['studentresult'].count(), 2)
        self.assertContains(result_response, 'Your Term 1 results')

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

    def test_teacher_leave_requests_use_current_fields_and_validate_dates(self):
        self.client.force_login(self.teacher)
        leave_url = reverse('staff_apply_leave_save')

        invalid_response = self.client.post(leave_url, {
            'leave_type': 'Annual Leave',
            'start_date': '2028-06-12',
            'end_date': '2028-06-10',
            'reason': 'Family commitment',
        })
        self.assertRedirects(invalid_response, reverse('staff_apply_leave'))
        self.assertFalse(LeaveRequest.objects.exists())

        admin = User.objects.create_user(username='leave-admin', password='x', user_type=1)
        response = self.client.post(leave_url, {
            'leave_type': 'Annual Leave',
            'start_date': '2028-06-10',
            'end_date': '2028-06-12',
            'reason': 'Family commitment',
            'cover_teacher': self.other_teacher.staff_profile.pk,
            'handover_notes': 'Notes for cover',
        })
        self.assertRedirects(response, reverse('staff_apply_leave'))
        leave = LeaveRequest.objects.get()
        self.assertEqual(leave.applicant, self.teacher)
        self.assertEqual(leave.start_date, date(2028, 6, 10))
        self.assertEqual(leave.end_date, date(2028, 6, 12))
        self.assertEqual(leave.total_days, 3)
        self.assertEqual(leave.cover_teacher, self.other_teacher.staff_profile)
        self.assertTrue(Notification.objects.filter(recipients=admin, title__icontains='leave').exists())

        self.client.force_login(admin)
        decision = self.client.post(reverse('respond_leave', args=[leave.pk]), {
            'status': 1, 'review_notes': 'Enjoy',
        })
        self.assertEqual(decision.status_code, 302)
        leave.refresh_from_db()
        self.assertEqual(leave.review_notes, 'Enjoy')
        self.assertTrue(Notification.objects.filter(recipients=self.teacher).exists())
        self.client.force_login(self.teacher)

        history_response = self.client.get(reverse('staff_apply_leave'))
        self.assertContains(history_response, 'Family commitment')
        self.assertContains(history_response, 'Approved')

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
        AcademicYear.objects.filter(is_current=True).update(is_current=False)
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
            ('generate_reports', ()),
            ('generate_attendance_report', ()),
        )
        for route, args in routes:
            with self.subTest(route=route):
                response = self.client.get(reverse(route, args=args))
                self.assertEqual(response.status_code, 200)
        for route in ('manage_finance', 'fee_payments', 'expenses', 'generate_finance_report'):
            with self.subTest(finance_route=route):
                response = self.client.get(reverse(route))
                self.assertEqual(response.status_code, 403)
        self.assertRedirects(
            self.client.get(reverse('admin_home')),
            reverse('admin_dashboard'),
        )

    def test_only_bursar_can_open_finance_dashboard_routes(self):
        bursar_user = User.objects.create_user(
            username='finance-bursar',
            password='test-password',
            user_type=4,
        )
        self.client.force_login(bursar_user)

        for route, expected_redirect in (
            ('manage_finance', 'bursar_dashboard'),
            ('fee_payments', 'payment_reports'),
            ('expenses', 'expense_management'),
            ('generate_finance_report', 'payment_reports'),
        ):
            with self.subTest(finance_route=route):
                response = self.client.get(reverse(route))
                self.assertRedirects(response, reverse(expected_redirect))

    def test_dashboard_is_focused_on_admissions_and_school_overview(self):
        self.client.force_login(self.admin)

        response = self.client.get(reverse('admin_dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['stats']['students_count'], 1)
        self.assertEqual(response.context['stats']['classes_count'], 1)
        self.assertContains(response, 'Pending applications')
        self.assertContains(response, 'Interviews scheduled')
        self.assertContains(response, reverse('review_student_applications'))
        self.assertNotContains(response, reverse('manage_finance'))
        self.assertNotContains(response, 'href="/finance/"')
        self.assertNotContains(response, 'Recent Activities')
        self.assertNotContains(response, 'Total Teachers')
        self.assertNotContains(response, 'Create Class')

    def test_academic_year_rolls_over_automatically_with_standard_classes(self):
        from .services import ensure_current_academic_year
        old = AcademicYear.objects.get(is_current=True)
        new_year = old.end_date.year + 1

        year = ensure_current_academic_year(date(new_year, 1, 15))

        self.assertEqual(year.name, str(new_year))
        self.assertTrue(year.is_current)
        old.refresh_from_db()
        self.assertFalse(old.is_current)
        self.assertEqual(
            set(StudentClass.objects.filter(academic_year=year).values_list('name', flat=True)),
            set(STANDARD_CLASS_NAMES),
        )
        self.assertEqual(AcademicYear.objects.filter(is_current=True).count(), 1)
        self.assertTrue(Notification.objects.filter(
            title__contains='has started', recipients=self.admin).exists())
        self.assertEqual(ensure_current_academic_year(date(new_year, 2, 1)).pk, year.pk)

    def test_academic_year_manual_routes_are_removed(self):
        from django.urls import NoReverseMatch
        for name in ('add_academic_year', 'edit_academic_year', 'delete_academic_year'):
            with self.assertRaises(NoReverseMatch):
                reverse(name)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse('manage_academic_years')).status_code, 200)

    def test_settings_page_saves_school_profile_and_term_dates(self):
        self.client.force_login(self.admin)
        page = self.client.get(reverse('settings'))
        self.assertEqual(page.status_code, 200)
        response = self.client.post(reverse('settings'), {
            'school_name': 'Renamed School',
            'address': 'P.O. Box 1',
            'contact_email': 'info@example.com',
            'contact_phone': '0700000000',
            'website': '',
            'applications_open': 'on',
            'term_1_start': '2026-01-05',
            'term_1_end': '2026-04-03',
            'term_2_start': '2026-05-04',
            'term_2_end': '2026-08-07',
            'term_3_start': '2026-08-31',
            'term_3_end': '2026-10-30',
        })
        self.assertRedirects(response, reverse('settings'))
        profile = SchoolProfile.get()
        self.assertEqual(profile.school_name, 'Renamed School')
        self.assertEqual(profile.term_2_start, date(2026, 5, 4))
        self.assertTrue(profile.applications_open)

    def test_notification_inbox_marks_read_and_blocks_external_redirects(self):
        from .services import notify
        note = notify([self.admin], 'Hello', 'Body', link='https://evil.example/x')
        self.client.force_login(self.admin)
        inbox = self.client.get(reverse('notifications'))
        self.assertContains(inbox, 'Hello')
        response = self.client.get(reverse('open_notification', args=[note.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertNotIn('evil.example', response['Location'])
        self.assertTrue(note.read_statuses.filter(user=self.admin).exists())

    def test_create_bursar_command_and_admin_cannot_add_bursar(self):
        from django.core.management import call_command
        call_command('create_bursar', 'cmd-bursar', '--email', 'cmd@example.com', '--password', 'Pass@123')
        self.assertEqual(User.objects.get(username='cmd-bursar').user_type, 4)
        from django.urls import NoReverseMatch
        with self.assertRaises(NoReverseMatch):
            reverse('add_bursar')

    def test_admin_student_search_uses_user_username_and_ignores_invalid_class(self):
        self.client.force_login(self.admin)

        response = self.client.get(reverse('manage_students'), {
            'search': 'student-user',
            'class': 'not-a-class-id',
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'student-user')
        self.assertContains(response, 'Grade 6')

    def test_headteacher_can_search_attendance_by_student_full_name(self):
        teacher = User.objects.create_user(username='reg-teacher', password='x', user_type=2)
        student_user = User.objects.create_user(
            username='2026G09999', password='x', user_type=3,
            first_name='Faith', last_name='Chepkoech',
        )
        year = AcademicYear.objects.filter(is_current=True).first() or AcademicYear.objects.first()
        class_obj = StudentClass.objects.create(name='Search Class', academic_year=year)
        attendance = Attendance.objects.create(
            subject=None, class_obj=class_obj, academic_year=year,
            attendance_date=date(2026, 3, 2), created_by=teacher.staff_profile,
        )
        AttendanceReport.objects.create(attendance=attendance, student=student_user.student_profile, status='P')
        self.client.force_login(self.admin)

        found = self.client.get(reverse('manage_attendance'), {'search': 'faith chepkoech'})
        self.assertEqual(found.status_code, 200)
        self.assertEqual(list(found.context['attendance_list']), [attendance])
        missing = self.client.get(reverse('manage_attendance'), {'search': 'faith nobody'})
        self.assertEqual(list(missing.context['attendance_list']), [])

    def test_headteacher_can_assign_a_subject_to_a_teacher_and_classes(self):
        self.client.force_login(self.admin)

        teacher_list = self.client.get(reverse('manage_teachers'))
        self.assertContains(
            teacher_list,
            reverse('teacher_subjects', args=[self.teacher_user.staff_profile.pk]),
        )
        self.assertContains(teacher_list, 'Manage subjects')

        assignment_url = reverse(
            'assign_subjects',
            args=[self.teacher_user.staff_profile.pk],
        )
        form_page = self.client.get(assignment_url)
        self.assertEqual(form_page.status_code, 200)
        self.assertContains(form_page, 'Academic year')

        response = self.client.post(assignment_url, {
            'subject': str(self.subject.pk),
            'classes': [str(self.student_class.pk)],
            'academic_year': str(self.academic_year.pk),
        })

        assignment = StaffSubjectAssignment.objects.get(
            staff=self.teacher_user.staff_profile,
            subject=self.subject,
            academic_year=self.academic_year,
        )
        self.assertRedirects(
            response,
            reverse('teacher_subjects', args=[self.teacher_user.staff_profile.pk]),
        )
        self.assertEqual(list(assignment.classes.all()), [self.student_class])

    def test_subjects_are_seeded_and_admin_management_is_not_exposed(self):
        self.client.force_login(self.admin)

        dashboard = self.client.get(reverse('admin_dashboard'))

        self.assertNotContains(dashboard, 'Subjects')
        self.assertTrue(Subject.objects.filter(code='CBC-ENGLISH').exists())
        self.assertTrue(Subject.objects.filter(code='CBC-MATH').exists())
        self.assertEqual(self.client.get('/manage_subject').status_code, 404)

    def test_class_edit_only_assigns_the_class_teacher(self):
        self.client.force_login(self.admin)
        url = reverse('edit_class', args=[self.student_class.pk])

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context['form'].fields), ['class_teacher'])
        response = self.client.post(url, {
            'class_teacher': str(self.teacher_user.staff_profile.pk),
            'name': 'A different class',
            'academic_year': '',
        })

        self.assertRedirects(response, reverse('manage_classes'))
        self.student_class.refresh_from_db()
        self.assertEqual(self.student_class.name, 'Grade 6')
        self.assertEqual(self.student_class.academic_year, self.academic_year)
        self.assertEqual(self.student_class.class_teacher, self.teacher_user.staff_profile)

    def test_destructive_admin_actions_require_post(self):
        self.client.force_login(self.admin)
        urls = (
            reverse('delete_teacher', args=[self.teacher_user.staff_profile.pk]),
            reverse('deactivate_student', args=[self.student_user.student_profile.pk]),
        )
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 405)

    def test_headteacher_cannot_delete_classes(self):
        self.client.force_login(self.admin)

        response = self.client.post(f'/delete_class/{self.student_class.pk}')

        self.assertEqual(response.status_code, 404)
        self.assertTrue(StudentClass.objects.filter(pk=self.student_class.pk).exists())
        classes_page = self.client.get(reverse('manage_classes'))
        self.assertNotContains(classes_page, 'Delete this class')
        self.assertNotContains(classes_page, 'fa-trash')

    def test_legacy_admin_endpoints_are_restricted_to_admin_users(self):
        for user in (None, self.student_user):
            if user is None:
                self.client.logout()
            else:
                self.client.force_login(user)
            response = self.client.get(reverse('admin_home'))
            self.assertEqual(response.status_code, 302)
