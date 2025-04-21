from django.db import models
from django.contrib.auth.models import AbstractUser
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator,RegexValidator
from django.contrib.auth import get_user_model

class SessionYearModel(models.Model):
    id = models.AutoField(primary_key=True)
    session_start_year = models.DateField()
    session_end_year = models.DateField()
    is_current = models.BooleanField(default=False)
    objects = models.Manager()

    def __str__(self):
        return f"{self.session_start_year.year}-{self.session_end_year.year}"

class CustomUser(AbstractUser):
    USER_TYPE_CHOICES = (
        (1, "Admin"),
        (2, "Staff"),
        (3, "Student"),
        (4, "Bursar"),
    )
    user_type = models.PositiveSmallIntegerField(choices=USER_TYPE_CHOICES, default=1)
    profile_pic = models.ImageField(upload_to='profile_pics/', null=True, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"

class AcademicYear(models.Model):
    name = models.CharField(max_length=50)
    start_date = models.DateField()
    end_date = models.DateField()
    is_current = models.BooleanField(default=False)

    def __str__(self):
        return self.name

class Class(models.Model):
    name = models.CharField(max_length=50)
    class_teacher = models.ForeignKey('Staff', on_delete=models.SET_NULL, null=True, blank=True, related_name='class_teacher_of')
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE)
    
    def __str__(self):
        return f"{self.name} ({self.academic_year})"

class Subject(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True)
    
    def __str__(self):
        return f"{self.name} ({self.code})"

class Staff(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='staff_profile')
    subjects = models.ManyToManyField(Subject, through='StaffSubjectAssignment')
    qualification = models.CharField(max_length=100, blank=True)
    date_of_joining = models.DateField(default=timezone.now)
    
    class Meta:
        verbose_name_plural = "Staff"
    
    def __str__(self):
        return self.user.get_full_name()
    
class Bursar(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='bursar_profile')
    qualification = models.CharField(max_length=100, blank=True)
    date_of_joining = models.DateField(default=timezone.now)
    GENDER_CHOICES = (
        ('M', 'Male'),
        ('F', 'Female'),
        ('O', 'Other'),
    )
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES)
    
    class Meta:
        verbose_name_plural = "Bursar"
    
    def __str__(self):
        return self.user.get_full_name()

class StaffSubjectAssignment(models.Model):
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    classes = models.ManyToManyField(Class)
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE)
    
    class Meta:
        unique_together = ('staff', 'subject', 'academic_year')
        verbose_name = "Subject Assignment"
    
    def __str__(self):
        return f"{self.staff} teaches {self.subject} to {', '.join([c.name for c in self.classes.all()])}"

class Student(models.Model):
    GENDER_CHOICES = (
        ('M', 'Male'),
        ('F', 'Female'),
        ('O', 'Other'),
    )
    
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='student_profile')
    admission_number = models.CharField(max_length=20, unique=True)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES)
    date_of_birth = models.DateField(null=True, blank=True)
    current_class = models.ForeignKey(Class, on_delete=models.SET_NULL, null=True, related_name='students')
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.SET_NULL, null=True)
    date_of_admission = models.DateField(default=timezone.now)
    father_name = models.CharField(max_length=100, blank=True)
    mother_name = models.CharField(max_length=100, blank=True)
    
    class Meta:
        ordering = ['current_class', 'user__last_name']
    
    def __str__(self):
        return f"{self.user.get_full_name()} ({self.admission_number})"
    
    def get_fee_balance(self):
        total_invoices = FeeTransaction.objects.filter(
            student=self,
            transaction_type='INVOICE'
        ).aggregate(total=models.Sum('amount'))['total'] or 0
        
        total_payments = FeeTransaction.objects.filter(
            student=self,
            transaction_type='PAYMENT'
        ).aggregate(total=models.Sum('amount'))['total'] or 0
        
        return total_invoices - total_payments
    
    def get_fee_statement(self):
        return FeeTransaction.objects.filter(student=self).order_by('-date', '-created_at')
    
    def get_fee_payments(self):
        return FeePayment.objects.filter(student=self).order_by('-payment_date')
    def create_fee_invoice(student, fee_structure):
        """
        Create a fee invoice transaction for a student
        """
        current_balance = student.get_fee_balance()
        new_balance = current_balance + fee_structure.amount
        
        transaction = FeeTransaction.objects.create(
            student_id=student,
            transaction_type='INVOICE',
            fee_structure_id=fee_structure,
            amount=fee_structure.amount,
            balance=new_balance,
            description=f"{fee_structure.fee_name} for {student.session_year_id}",
            date=timezone.now().date()
        )
        return transaction

class SubjectResult(models.Model):
    TERM_CHOICES = (
        ('Term 1', 'Term 1'),
        ('Term 2', 'Term 2'),
        ('Term 3', 'Term 3'),
    )
    
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE)
    term = models.CharField(max_length=20, choices=TERM_CHOICES)
    exam_score = models.DecimalField(max_digits=5, decimal_places=2, validators=[MinValueValidator(0), MaxValueValidator(100)])
    assignment_score = models.DecimalField(max_digits=5, decimal_places=2, validators=[MinValueValidator(0), MaxValueValidator(100)])
    created_by = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('student', 'subject', 'academic_year', 'term')
        ordering = ['student', 'subject', 'term']
    
    @property
    def total_score(self):
        return self.exam_score + self.assignment_score
    
    def __str__(self):
        return f"{self.student} - {self.subject} ({self.term})"

class Attendance(models.Model):
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    class_obj = models.ForeignKey(Class, on_delete=models.CASCADE)
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE)
    attendance_date = models.DateField()
    created_by = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('subject', 'class_obj', 'attendance_date')
    
    def __str__(self):
        return f"{self.subject} - {self.class_obj} on {self.attendance_date}"

class AttendanceReport(models.Model):
    STATUS_CHOICES = (
        ('P', 'Present'),
        ('A', 'Absent'),
        ('L', 'Late'),
        ('E', 'Excused'),
    )
    
    attendance = models.ForeignKey(Attendance, on_delete=models.CASCADE)
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    status = models.CharField(max_length=1, choices=STATUS_CHOICES, default='P')
    remarks = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('attendance', 'student')
    
    def __str__(self):
        return f"{self.student} - {self.get_status_display()}"

class LeaveRequest(models.Model):
    STATUS_CHOICES = (
        (0, 'Pending'),
        (1, 'Approved'),
        (2, 'Rejected'),
    )
    
    applicant = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    leave_type = models.CharField(max_length=50)
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.TextField()
    status = models.IntegerField(choices=STATUS_CHOICES, default=0)
    approved_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_leaves')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.applicant} - {self.leave_type} ({self.get_status_display()})"

class Feedback(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    message = models.TextField()
    reply = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Feedback from {self.user}"

User = get_user_model()

class Notification(models.Model):
    PRIORITY_CHOICES = [
        ('LOW', 'Low'),
        ('MEDIUM', 'Medium'),
        ('HIGH', 'High'),
    ]
    
    STATUS_CHOICES = [
        ('SENT', 'Sent'),
        ('READ', 'Read'),
        ('FAILED', 'Failed'),
    ]

    title = models.CharField(max_length=200)
    message = models.TextField()
    sender = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='sent_notifications'
    )
    recipients = models.ManyToManyField(
        User,
        related_name='received_notifications'
    )
    priority = models.CharField(
        max_length=10,
        choices=PRIORITY_CHOICES,
        default='MEDIUM'
    )
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='SENT'
    )
    created_at = models.DateTimeField(default=timezone.now)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'

    def __str__(self):
        return f"{self.title} - {self.get_priority_display()}"

    def mark_as_read(self, user):
        """Mark notification as read for a specific user"""
        NotificationReadStatus.objects.get_or_create(
            notification=self,
            user=user,
            defaults={'read_at': timezone.now()}
        )
        self.read_at = timezone.now()
        self.status = 'READ'
        self.save()

class NotificationReadStatus(models.Model):
    notification = models.ForeignKey(
        Notification,
        on_delete=models.CASCADE,
        related_name='read_statuses'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='notification_reads'
    )
    read_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ('notification', 'user')
        verbose_name = 'Notification Read Status'
        verbose_name_plural = 'Notification Read Statuses'

    def __str__(self):
        return f"{self.user} read {self.notification}"

class FeeStructure(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    class_obj = models.ForeignKey(Class, on_delete=models.CASCADE)
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE)
    due_date = models.DateField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.name} - {self.class_obj} ({self.academic_year})"

class FeePayment(models.Model):
    PAYMENT_METHODS = (
        ('MPESA', 'M-Pesa'),
        ('CASH', 'Cash'),
        ('BANK', 'Bank Transfer'),
        ('CHEQUE', 'Cheque'),
    )
    
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    fee_structure = models.ForeignKey(FeeStructure, on_delete=models.SET_NULL, null=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_date = models.DateField(default=timezone.now)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS)
    transaction_code = models.CharField(max_length=50, blank=True)
    received_by = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True)
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.student} - Ksh{self.amount} on {self.payment_date}"

class Expense(models.Model):
    CATEGORIES = (
        ('SALARY', 'Staff Salaries'),
        ('FOOD', 'Food Supplies'),
        ('MAINTENANCE', 'Maintenance'),
        ('STATIONERY', 'Stationery'),
        ('OTHER', 'Other'),
    )
    
    bursar = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    category = models.CharField(max_length=20, choices=CATEGORIES)
    description = models.TextField()
    date = models.DateField(default=timezone.now)
    receipt_number = models.CharField(max_length=50, blank=True)
    approved_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, related_name='approved_expenses')

    def __str__(self):
        return f"{self.category} - Ksh{self.amount} on {self.date}"
    
class FeeTransaction(models.Model):
    TRANSACTION_TYPES = (
        ('INVOICE', 'Invoice'),
        ('PAYMENT', 'Payment'),
        ('ADJUSTMENT', 'Adjustment'),
    )
    
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    fee_structure = models.ForeignKey(FeeStructure, on_delete=models.SET_NULL, null=True, blank=True)
    fee_payment = models.ForeignKey(FeePayment, on_delete=models.SET_NULL, null=True, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    balance = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField(blank=True)
    date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.transaction_type} - {self.student} ({self.amount})"

@receiver(post_save, sender=CustomUser)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        if instance.user_type == 2:  # Staff
            Staff.objects.create(user=instance)
        elif instance.user_type == 3:  # Student
            Student.objects.create(user=instance)
        elif instance.user_type == 4:  # Bursar
            staff = Staff.objects.create(user=instance)
            staff.is_bursar = True
            staff.save()

@receiver(post_save, sender=CustomUser)
def save_user_profile(sender, instance, **kwargs):
    if instance.user_type == 1 or instance.user_type == 2:
        if hasattr(instance, 'staff_profile'):
            instance.staff_profile.save()
    elif instance.user_type == 3:
        if hasattr(instance, 'student_profile'):
            instance.student_profile.save()
    elif instance.user_type == 4:
        if hasattr(instance, 'bursar_profile'):
            instance.bursar_profile.save()


User = get_user_model()

class SystemLog(models.Model):
    LOG_TYPE_CHOICES = [
        ('INFO', 'Information'),
        ('WARNING', 'Warning'),
        ('ERROR', 'Error'),
        ('SECURITY', 'Security'),
        ('AUDIT', 'Audit'),
    ]
    
    ACTION_CATEGORIES = [
        ('LOGIN', 'User Login'),
        ('LOGOUT', 'User Logout'),
        ('CREATE', 'Create Operation'),
        ('UPDATE', 'Update Operation'),
        ('DELETE', 'Delete Operation'),
        ('CONFIG', 'Configuration Change'),
        ('BACKUP', 'Database Backup'),
        ('RESTORE', 'Database Restore'),
        ('PERMISSION', 'Permission Change'),
    ]
    
    timestamp = models.DateTimeField(default=timezone.now)
    log_type = models.CharField(max_length=10, choices=LOG_TYPE_CHOICES, default='INFO')
    action = models.CharField(max_length=50, choices=ACTION_CATEGORIES)
    details = models.TextField()
    user = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='system_logs'
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, null=True, blank=True)
    affected_model = models.CharField(max_length=100, null=True, blank=True)
    object_id = models.CharField(max_length=100, null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'System Log'
        verbose_name_plural = 'System Logs'
        indexes = [
            models.Index(fields=['-timestamp']),
            models.Index(fields=['log_type']),
            models.Index(fields=['action']),
            models.Index(fields=['user']),
            models.Index(fields=['affected_model']),
        ]

    def __str__(self):
        return f"{self.timestamp} - {self.get_log_type_display()} - {self.action}"

    @classmethod
    def create_log(cls, action, details, user=None, request=None, 
                 log_type='INFO', affected_model=None, object_id=None, **metadata):
        """
        Helper method to create log entries consistently
        """
        log = cls(
            action=action,
            details=details,
            user=user,
            log_type=log_type,
            affected_model=affected_model,
            object_id=object_id,
            metadata=metadata
        )
        
        if request:
            log.ip_address = request.META.get('REMOTE_ADDR')
            log.user_agent = request.META.get('HTTP_USER_AGENT', '')[:255]
        
        log.save()
        return log