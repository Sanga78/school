from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from index.models import (
    CustomUser, Student, StudentApplication, AcademicYear, StudentClass,
)


class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'get_full_name', 'get_user_type', 'email', 'is_active')
    list_filter = ('user_type', 'is_active', 'is_staff')
    search_fields = ('username', 'first_name', 'last_name', 'email')
    fieldsets = UserAdmin.fieldsets + (
        ('Additional Info', {'fields': ('user_type', 'phone', 'profile_pic', 'address')}),
    )

    def get_user_type(self, obj):
        return dict(obj.USER_TYPE_CHOICES).get(obj.user_type, 'Unknown')
    get_user_type.short_description = 'User Type'


class StudentApplicationInline(admin.TabularInline):
    model = StudentApplication
    extra = 0
    readonly_fields = ('confirmation_id', 'submitted_at', 'updated_at')
    fields = ('status', 'confirmation_id', 'interview_at', 'review_notes')


class StudentAdmin(admin.ModelAdmin):
    list_display = (
        'get_full_name', 'admission_number', 'birth_certificate_number',
        'current_class', 'academic_year', 'active'
    )
    list_filter = ('active', 'gender', 'current_class', 'academic_year')
    search_fields = (
        'user__first_name', 'user__last_name', 'user__username',
        'admission_number', 'birth_certificate_number'
    )
    readonly_fields = ('date_of_admission', 'user')
    fieldsets = (
        ('User Account', {'fields': ('user',)}),
        ('Personal Information', {'fields': ('gender', 'date_of_birth', 'birth_certificate_number')}),
        ('Academic Information', {'fields': ('current_class', 'academic_year', 'admission_number', 'active')}),
        ('Family Information', {'fields': ('father_name', 'mother_name', 'parent_email')}),
        ('Admission', {'fields': ('date_of_admission',)}),
    )
    inlines = [StudentApplicationInline]

    def get_full_name(self, obj):
        return obj.user.get_full_name()
    get_full_name.short_description = 'Full Name'


class StudentApplicationAdmin(admin.ModelAdmin):
    list_display = (
        'get_applicant_name', 'confirmation_id', 'status',
        'get_applied_class', 'submitted_at'
    )
    list_filter = ('status', 'submitted_at')
    search_fields = (
        'student__user__first_name', 'student__user__last_name',
        'confirmation_id'
    )
    readonly_fields = ('confirmation_id', 'submitted_at', 'updated_at')
    fieldsets = (
        ('Application Details', {'fields': ('student', 'confirmation_id', 'status')}),
        ('Review', {'fields': ('interview_at', 'review_notes')}),
        ('Timestamps', {'fields': ('submitted_at', 'updated_at')}),
    )

    def get_applicant_name(self, obj):
        return obj.student.user.get_full_name()
    get_applicant_name.short_description = 'Applicant Name'

    def get_applied_class(self, obj):
        return obj.student.current_class or '—'
    get_applied_class.short_description = 'Applied Class'


class AcademicYearAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_current', 'start_date', 'end_date')
    list_filter = ('is_current',)
    search_fields = ('name',)


class StudentClassAdmin(admin.ModelAdmin):
    list_display = ('name', 'academic_year', 'class_teacher')
    list_filter = ('academic_year',)
    search_fields = ('name',)


# Register models
admin.site.register(CustomUser, CustomUserAdmin)
admin.site.register(Student, StudentAdmin)
admin.site.register(StudentApplication, StudentApplicationAdmin)
admin.site.register(AcademicYear, AcademicYearAdmin)
admin.site.register(StudentClass, StudentClassAdmin)
