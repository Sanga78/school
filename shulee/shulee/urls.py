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
from django.urls import path,include
from django.conf.urls.static import static
from index import views,HodViews,StaffViews,StudentViews,FinanceViews
from django.conf import settings


urlpatterns = [
    path('bursar/food/', FinanceViews.bursar_food, name='bursar_food'),
    path('bursar/food/student/<int:student_id>/', FinanceViews.bursar_food_student, name='bursar_food_student'),
    path('bursar/grants/', FinanceViews.bursar_grants, name='bursar_grants'),
    path('bursar/expenses/<int:expense_id>/edit/', FinanceViews.edit_expense, name='edit_expense'),
    path('bursar/invoice/<int:student_id>/', FinanceViews.bursar_invoice, name='bursar_invoice'),
    path('bursar/receipt/payment/<int:payment_id>/', FinanceViews.payment_receipt, name='payment_receipt'),
    path('bursar/receipt/food/<int:contribution_id>/', FinanceViews.food_receipt, name='food_receipt'),
    path('bursar/payroll/', FinanceViews.bursar_payroll, name='bursar_payroll'),
    path('bursar/payroll/payslip/<int:payslip_id>/', FinanceViews.bursar_payslip, name='bursar_payslip'),
    path('teacher/payslips/', FinanceViews.my_payslips, name='my_payslips'),
    path('teacher/payslips/<int:payslip_id>/', FinanceViews.my_payslip_detail, name='my_payslip_detail'),
    path('student/invoice/', FinanceViews.student_invoice, name='student_invoice'),
    path('admin/school-profile/', FinanceViews.manage_school_profile, name='manage_school_profile'),
    path('admin/school-profile/uniform/<int:item_id>/delete/', FinanceViews.delete_uniform_item, name='delete_uniform_item'),
    path('admin/cash-payments/', HodViews.review_cash_payments, name='review_cash_payments'),
    path('admin/cash-payments/<int:approval_id>/decision/', HodViews.decide_cash_payment, name='decide_cash_payment'),
    path('admin/applications/', HodViews.review_student_applications, name='review_student_applications'),
    path('admin/applications/<int:application_id>/review/', HodViews.review_student_application, name='review_student_application'),
    path('admin/results/', HodViews.review_results, name='review_results'),
    path('admin/results/<int:publication_id>/review/', HodViews.review_result_publication, name='review_result_publication'),
    path('apply/form/',views.signup_student,name="application_form"),
    path('apply/submit/',views.student_signup,name="submit_application"),
    path('application-confirmation/<int:application_id>/', views.application_confirmation, name='application_confirmation'),
    path('bursar/', views.bursar_dashboard, name='bursar_dashboard'),
    path('bursar/fee-records/', views.fee_records, name='fee_records'),
    path('bursar/record-payment/<int:student_id>/', views.record_payment, name='record_payment'),
    path('bursar/expenses/', views.expense_management, name='expense_management'),
    path('bursar/reports/', views.payment_reports, name='payment_reports'),

    path('index/',views.index,name='home'),
    path('about/',views.about,name='about'),
    path('academics/',views.academics,name='academics'),
    path('admissions/',views.admissions,name='admissions'),
    path('apply/',views.apply,name='apply'),
    path('results/',views.results,name='results'),
    path('events/',views.events,name='events'),
    path('events/manage/',views.manage_events,name='manage_events'),
    path('events/manage/<int:event_id>/edit/',views.edit_school_event,name='edit_school_event'),
    path('events/manage/<int:event_id>/delete/',views.delete_school_event,name='delete_school_event'),
    path('contact/',views.contact,name='contact'),

    path('accounts/',include('django.contrib.auth.urls')),
    path('loginPage',views.loginPage,name="show_login"),
    path('',views.home,name="home"),
    path('login',views.Login,name="do_login"),
    path('get_user_details',views.GetUserDetails),
    path('logout',views.Logout,name="logout"),
    path('student/application-status/',StudentViews.student_application_status,name='student_application_status'),
    path('student/confirmation-letter/',StudentViews.student_confirmation_letter,name='student_confirmation_letter'),
    path('admin_home',HodViews.admin_home,name="admin_home"),
    # path('manage_student',HodViews.manage_students,name="manage_student"),
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
    path('edit_class/<str:class_id>',HodViews.edit_class,name='edit_class'),
    # Leaves
    path('leaves/', HodViews.manage_leaves, name='manage_leaves'),
    path('leaves/<int:leave_id>/respond/', HodViews.respond_leave, name='respond_leave'),
    
    # Feedback
    path('feedback/', HodViews.manage_feedback, name='manage_feedback'),
    path('feedback/<int:feedback_id>/respond/', HodViews.respond_feedback, name='respond_feedback'),
    
    # Settings
    path('settings/', HodViews.settings_view, name='settings'),
    # Student Management
    path('students/', HodViews.manage_students, name='manage_students'),
    path('students/add/', HodViews.add_student, name='add_student'),
    path('students/<int:student_id>/', HodViews.view_student, name='view_student'),
    path('activate_student/<str:student_id>',HodViews.activate_student,name="activate_student"),
    path('deactivate_student/<str:student_id>',HodViews.deactivate_student,name="deactivate_student"), 
    path('students/edit/<int:student_id>/', HodViews.edit_student, name='edit_student'),
    path('students/delete/<int:student_id>/', HodViews.delete_student, name='delete_student'),
    
    # Finance Management
    path('finance/', HodViews.manage_finance, name='manage_finance'),
    path('finance/payments/', HodViews.fee_payments, name='fee_payments'),
    path('finance/expenses/', HodViews.expenses, name='expenses'),

     # Administrator Management
    path('administrators/', HodViews.manage_administrators, name='manage_administrators'),
    path('administrators/add/', HodViews.add_administrator, name='add_administrator'),
    
    # Bursar Management
    path('bursars/', HodViews.manage_bursars, name='manage_bursars'),
    path('bursars/edit/<int:bursar_id>/', HodViews.edit_bursar, name='edit_bursar'),
    path('bursars/deactivate/<int:bursar_id>/', HodViews.deactivate_bursar, name='deactivate_bursar'),
    
    # System Maintenance
    path('backup/', HodViews.backup_database, name='backup_database'),
    path('logs/', HodViews.system_logs, name='system_logs'),
    path('logs/export/', HodViews.export_logs, name='export_logs'),
    
    # Subject Management

    path('notifications/send/',HodViews.send_notification, name='send_notification'),
    path('notifications/history/', HodViews.notification_history, name='notification_history'),
    path('notifications/', views.notifications, name='notifications'),
    path('notifications/read-all/', views.mark_notifications_read, name='mark_notifications_read'),
    path('notifications/<int:notification_id>/open/', views.open_notification, name='open_notification'),
    
    # Academic years (generated automatically; read-only listing)
    path('academic-years/', HodViews.manage_academic_years, name='manage_academic_years'),
    # Report URLs
    path('reports/', HodViews.generate_reports, name='generate_reports'),
    path('reports/students/<str:report_type>/', HodViews.generate_student_report, name='generate_student_report'),
    path('reports/attendance/', HodViews.generate_attendance_report, name='generate_attendance_report'),
    path('reports/finance/', HodViews.generate_finance_report, name='generate_finance_report'),
    #Staff urls
    path('staff_home',StaffViews.staff_home,name="staff_home"),
    path('staff_feedback',StaffViews.staff_feedback,name="staff_feedback"),
    path('staff_feedback_save',StaffViews.staff_feedback_save,name="staff_feedback_save"),
    path('staff_apply_leave',StaffViews.staff_apply_leave,name="staff_apply_leave"),
    path('staff_apply_leave_save',StaffViews.staff_apply_leave_save,name="staff_apply_leave_save"),
    path('staff_profile',StaffViews.staff_profile,name="staff_profile"),
    path('staff_profile_save',StaffViews.teacher_profile_save,name="staff_profile_save"),
    path('teacher/dashboard/', StaffViews.teacher_dashboard, name='teacher_dashboard'),
    path('teacher/upload-results/<int:class_id>/<int:subject_id>/', StaffViews.upload_results, name='upload_results'),
    path('teacher/classes/<int:class_id>/results/submit/', StaffViews.submit_class_results, name='submit_class_results'),
    
    # Class Teacher URLs
    path('class-teacher/dashboard/', StaffViews.class_teacher_dashboard, name='class_teacher_dashboard'),
    path('class-teacher/attendance/<int:class_id>/', StaffViews.class_teacher_attendance, name='class_teacher_attendance'),
    path('class-teacher/events/<int:class_id>/', StaffViews.class_teacher_events, name='class_teacher_events'),
    path('class-teacher/events/<int:class_id>/<int:event_id>/delete/', StaffViews.class_teacher_delete_event, name='class_teacher_delete_event'),
    path('class-teacher/attendance/<int:class_id>/weekly/', StaffViews.class_teacher_weekly_attendance, name='class_teacher_weekly_attendance'),
    path('class-teacher/results/<int:class_id>/', StaffViews.view_class_results, name='view_class_results'),

   #student urls
    path('student_home',StudentViews.student_home,name="student_home"),
    path('student_feedback',StudentViews.student_feedback,name="student_feedback"),
    path('student_feedback_save',StudentViews.student_feedback_save,name="student_feedback_save"),
    path('student_profile',StudentViews.student_profile,name="student_profile"),
    path('student_profile_save',StudentViews.student_profile_save,name="student_profile_save"),
    path('student_view_result',StudentViews.student_view_result,name="student_view_result"),
    path('fee-statement/', StudentViews.student_fee_statement, name='student_fee_statement'),
    path('fee-payments/', StudentViews.student_fee_payments, name='student_fee_payments'),
    path('make-payment/', StudentViews.make_fee_payment, name='make_fee_payment'),
    path('payments/mpesa/callback/', StudentViews.mpesa_stk_callback, name='mpesa_stk_callback'),
]+static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)+static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
