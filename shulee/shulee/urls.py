"""
URL configuration for shulee project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path,include
from django.conf.urls.static import static
from index import views,HodViews,StaffViews,StudentViews
from django.conf import settings

from index.EditResultViewClass import EditResultViewClass

urlpatterns = [
    path('admin/', admin.site.urls),
    path('signup_admin',views.signup_admin,name="signup_admin"),
    path('admin_signup',views.admin_signup,name="admin_signup"),
    path('signup_staff',views.signup_staff,name="signup_staff"),
    path('staff_signup',views.staff_signup,name="staff_signup"),
    path('signup_student',views.signup_student,name="signup_student"),
    path('student_signup',views.student_signup,name="student_signup"),
    path('bursar/', views.bursar_dashboard, name='bursar_dashboard'),
    path('bursar/fee-records/', views.fee_records, name='fee_records'),
    path('bursar/record-payment/<int:student_id>/', views.record_payment, name='record_payment'),
    path('bursar/expenses/', views.expense_management, name='expense_management'),
    path('bursar/reports/', views.payment_reports, name='payment_reports'),

    path('index/',views.index,name='home'),
    path('about/',views.about,name='about'),
    path('academics/',views.academics,name='academics'),
    path('admissions/',views.admissions,name='admissions'),
    path('results/',views.results,name='results'),
    path('events/',views.events,name='events'),
    path('contact/',views.contact,name='contact'),

    path('accounts/',include('django.contrib.auth.urls')),
    path('',views.loginPage,name="show_login"),
    path('login',views.Login,name="do_login"),
    path('get_user_details',views.GetUserDetails),
    path('logout',views.Logout,name="logout"),
    path('admin_home',HodViews.admin_home,name="admin_home"),
    path('add_staff',HodViews.add_staff,name="add_staff"),
    path('add_staff_save',HodViews.add_staff_save,name="add_staff_save"),
    path('add_student',HodViews.add_student,name="add_student"),
    path('add_student_save',HodViews.add_student_save,name="add_student_save"),
    path('add_subject',HodViews.add_subject,name="add_subject"),
    path('add_subject_save',HodViews.add_subject_save,name="add_subject_save"),
    path('manage_staff',HodViews.manage_staff,name="manage_staff"),
    # path('manage_student',HodViews.manage_students,name="manage_student"),
    path('manage_subject',HodViews.manage_subject,name="manage_subject"),
    path('edit_staff/<str:staff_id>',HodViews.edit_staff,name="edit_staff"),
    path('edit_staff_save',HodViews.edit_staff_save,name="edit_staff_save"),
    path('edit_student/<str:student_id>',HodViews.edit_student,name="edit_student"),
    path('edit_student_save',HodViews.edit_student_save,name="edit_student_save"),
    path('edit_subject/<str:subject_id>',HodViews.edit_subject,name="edit_subject"),
    path('edit_subject_save',HodViews.edit_subject_save,name="edit_subject_save"),
    path('manage_session',HodViews.manage_session,name="manage_session"),
    path('add_session_save',HodViews.add_session_save,name="add_session_save"),
    path('check_email_exist',HodViews.check_email_exist,name="check_email_exist"),
    path('check_username_exist',HodViews.check_username_exist,name="check_username_exist"),
    path('student_feedback_message',HodViews.student_feedback_message,name="student_feedback_message"),
    path('student_leave_view',HodViews.student_leave_view,name="student_leave_view"),
    path('student_approve_leave/<str:leave_id>',HodViews.student_approve_leave,name="student_approve_leave"),
    path('student_disapprove_leave/<str:leave_id>',HodViews.student_disapprove_leave,name="student_disapprove_leave"),
    path('staff_leave_view',HodViews.staff_leave_view,name="staff_leave_view"),
    path('staff_disapprove_leave/<str:leave_id>',HodViews.staff_disapprove_leave,name="staff_disapprove_leave"),
    path('staff_approve_leave/<str:leave_id>',HodViews.staff_approve_leave,name="staff_approve_leave"),
    path('student_feedback_message_replied',HodViews.student_feedback_message_replied,name="student_feedback_message_replied"),
    path('staff_feedback_message',HodViews.staff_feedback_message,name="staff_feedback_message"),
    path('staff_feedback_message_replied',HodViews.staff_feedback_message_replied,name="staff_feedback_message_replied"),
    path('admin_view_atendance',HodViews.admin_view_atendance,name="admin_view_atendance"),
    path('admin_get_attendance_dates',HodViews.admin_get_attendance_dates,name="admin_get_attendance_dates"),
    path('admin_get_attendance_student',HodViews.admin_get_attendance_student,name="admin_get_attendance_student"),
    path('admin_profile',HodViews.admin_profile,name="admin_profile"),
    path('admin_profile_save',HodViews.admin_profile_save,name="admin_profile_save"),
    # Admin URLs
    path('admin_dashboard/', HodViews.admin_dashboard, name='admin_dashboard'),
    path('teachers/', HodViews.manage_teachers, name='manage_teachers'),
    path('teachers/add/', HodViews.add_teacher, name='add_teacher'),
    path('edit_teacher/<str:teacher_id>',HodViews.edit_teacher,name="edit_teacher"),
    path('delete_teacher/<str:teacher_id>',HodViews.delete_teacher,name="delete_teacher"),
    path('teachers/<int:teacher_id>/assign-subjects/', HodViews.assign_subjects, name='assign_subjects'),
    path('teachers/<int:teacher_id>/subjects/', HodViews.teacher_subjects, name='teacher_subjects'),
    path('assign-class-teachers/', HodViews.assign_class_teachers, name='assign_class_teachers'),
    path('remove-assignment/<int:assignment_id>/', HodViews.remove_subject_assignment, name='remove_subject_assignment'),
    path('attendance/', HodViews.manage_attendance, name='manage_attendance'),
    path('attendance/<int:attendance_id>/', HodViews.view_attendance, name='view_attendance'),
    path('classes/', HodViews.manage_classes, name='manage_classes'),
    path('add_class/', HodViews.add_class, name='add_class'),
    path('edit_class/<str:class_id>',HodViews.edit_class,name='edit_class'),
    path('delete_class/<str:class_id>',HodViews.delete_class,name='delete_class'),
    # Leaves
    path('leaves/', HodViews.manage_leaves, name='manage_leaves'),
    path('leaves/<int:leave_id>/respond/', HodViews.respond_leave, name='respond_leave'),
    
    # Feedback
    path('feedback/', HodViews.manage_feedback, name='manage_feedback'),
    path('feedback/<int:feedback_id>/respond/', HodViews.respond_feedback, name='respond_feedback'),
    
    # Settings
    path('settings/', HodViews.settings, name='settings'),
    # Student Management
    path('students/', HodViews.manage_students, name='manage_students'),
    path('students/add/', HodViews.add_student, name='add_student'),
    path('students/<int:student_id>/edit/', HodViews.edit_student, name='edit_student'),
    path('students/<int:student_id>/', HodViews.view_student, name='view_student'),
    
    # Finance Management
    path('finance/', HodViews.manage_finance, name='manage_finance'),
    path('finance/payments/', HodViews.fee_payments, name='fee_payments'),
    path('finance/expenses/', HodViews.expenses, name='expenses'),

     # Administrator Management
    path('administrators/', HodViews.manage_administrators, name='manage_administrators'),
    path('administrators/add/', HodViews.add_administrator, name='add_administrator'),
    
    # Bursar Management
    path('bursars/', HodViews.manage_bursars, name='manage_bursars'),
    path('bursars/add/', HodViews.add_bursar, name='add_bursar'),
    path('bursars/edit/<int:bursar_id>/', HodViews.edit_bursar, name='edit_bursar'),
    path('bursars/deactivate/<int:bursar_id>/', HodViews.deactivate_bursar, name='deactivate_bursar'),
    
    # System Maintenance
    path('backup/', HodViews.backup_database, name='backup_database'),
    path('logs/', HodViews.system_logs, name='system_logs'),
    path('logs/export/', HodViews.export_logs, name='export_logs'),
    
    # Subject Management
    path('subjects/add/', HodViews.add_subject, name='add_subject'),

    path('notifications/send/',HodViews.send_notification, name='send_notification'),
    path('notifications/history/', HodViews.notification_history, name='notification_history'),
    
    # Academic Years
    path('academic-years/', HodViews.manage_academic_years, name='manage_academic_years'),
    path('academic-years/add/', HodViews.add_academic_year, name='add_academic_year'),
    path('academic-years/edit/<int:year_id>/', HodViews.edit_academic_year, name='edit_academic_year'),
    path('academic-years/delete/<int:year_id>/', HodViews.delete_academic_year, name='delete_academic_year'),
    path('set-current-academic-year/', HodViews.set_current_academic_year, name='set_current_academic_year'),
    # Report URLs
    path('reports/', HodViews.generate_reports, name='generate_reports'),
    path('reports/students/<str:report_type>/', HodViews.generate_student_report, name='generate_student_report'),
    path('reports/attendance/', HodViews.generate_attendance_report, name='generate_attendance_report'),
    path('reports/finance/', HodViews.generate_finance_report, name='generate_finance_report'),
    #Staff urls
    path('staff_home',StaffViews.staff_home,name="staff_home"),
    path('staff_take_attendance',StaffViews.staff_take_attendance,name="staff_take_attendance"),
    path('staff_update_attendance',StaffViews.staff_update_attendance,name="staff_update_attendance"),
    path('get_attendance_dates',StaffViews.get_attendance_dates,name="get_attendance_dates"),
    path('get_attendance_student',StaffViews.get_attendance_student,name="get_attendance_student"),
    path('get_students',StaffViews.get_students,name="get_students"),
    path('save_attendance_data',StaffViews.save_attendance_data,name="save_attendance_data"),
    path('save_updateattendance_data',StaffViews.save_updateattendance_data,name="save_updateattendance_data"),
    path('staff_feedback',StaffViews.staff_feedback,name="staff_feedback"),
    path('staff_feedback_save',StaffViews.staff_feedback_save,name="staff_feedback_save"),
    path('staff_apply_leave',StaffViews.staff_apply_leave,name="staff_apply_leave"),
    path('staff_apply_leave_save',StaffViews.staff_apply_leave_save,name="staff_apply_leave_save"),
    path('staff_profile',StaffViews.staff_profile,name="staff_profile"),
    path('staff_profile_save',StaffViews.staff_profile_save,name="staff_profile_save"),
    path('staff_fcmtoken_save',StaffViews.staff_fcmtoken_save,name="student_fcmtoken_save"),
    path('staff_add_result',StaffViews.staff_add_result,name="staff_add_result"),
    path('save_student_result',StaffViews.save_student_result,name="save_student_result"),
    path('edit_student_result',EditResultViewClass.as_view(),name="edit_student_result"),
    path('fetch_student_result',StaffViews.fetch_student_result,name="fetch_student_result"),
    path('teacher/dashboard/', StaffViews.teacher_dashboard, name='teacher_dashboard'),
    path('teacher/upload-results/<int:class_id>/<int:subject_id>/', StaffViews.upload_results, name='upload_results'),
    
    # Class Teacher URLs
    path('class-teacher/dashboard/', StaffViews.class_teacher_dashboard, name='class_teacher_dashboard'),
    path('class-teacher/results/<int:class_id>/', StaffViews.view_class_results, name='view_class_results'),

   #student urls
    path('student_home',StudentViews.student_home,name="student_home"),
    path('student_view_attendance',StudentViews.student_view_attendance,name="student_view_attendance"),
    path('student_view_attendance_post',StudentViews.student_view_attendance_post,name="student_view_attendance_post"),
    path('student_feedback',StudentViews.student_feedback,name="student_feedback"),
    path('student_feedback_save',StudentViews.student_feedback_save,name="student_feedback_save"),
    path('student_apply_leave',StudentViews.student_apply_leave,name="student_apply_leave"),
    path('student_apply_leave_save',StudentViews.student_apply_leave_save,name="student_apply_leave_save"),
    path('student_profile',StudentViews.student_profile,name="student_profile"),
    path('student_profile_save',StudentViews.student_profile_save,name="student_profile_save"),
    path('student_fcmtoken_save',StudentViews.student_fcmtoken_save,name="student_fcmtoken_save"),
    path('student_view_result',StudentViews.student_view_result,name="student_view_result"),
    path('fee-statement/', StudentViews.student_fee_statement, name='student_fee_statement'),
    path('fee-payments/', StudentViews.student_fee_payments, name='student_fee_payments'),
    path('fee-balance/', StudentViews.student_fee_balance, name='student_fee_balance'),
    path('make-payment/', StudentViews.make_fee_payment, name='make_fee_payment'),

]+static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)+static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
