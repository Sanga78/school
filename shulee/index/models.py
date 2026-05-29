from django.db import models
from django.contrib.auth.models import AbstractUser
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.auth import get_user_model

# Ensure CustomUser is defined before any models that reference it via a direct ForeignKey
# or OneToOneField. Using get_user_model() helps prevent circular imports in some cases,
# but for signals, it's often better to import the actual model.
# However, for direct ForeignKey/OneToOneField relationships, define CustomUser first.

class SessionYearModel(models.Model):
    # Django automatically adds an 'id' AutoField as primary_key=True if not specified.
    # So, id = models.AutoField(primary_key=True) is redundant and can be removed.
    session_start_year = models.DateField()
    session_end_year = models.DateField()
    is_current = models.BooleanField(default=False)
    # 'objects = models.Manager()' is redundant as it's the default manager.
    # You only need to define it if you're adding custom manager methods or overriding.

    class Meta:
        verbose_name = "Session Year"
        verbose_name_plural = "Session Years"
        # Add a constraint to ensure only one session year can be current at a time.
        # This will require custom logic in your views/forms to manage.
        constraints = [
            models.UniqueConstraint(fields=['is_current'], condition=models.Q(is_current=True), name='unique_is_current_session_year')
        ]


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

# Get the custom user model after it's defined
User = get_user_model()

class AcademicYear(models.Model):
    name = models.CharField(max_length=50, unique=True) # Ensure academic year names are unique
    start_date = models.DateField()
    end_date = models.DateField()
    is_current = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Academic Year"
        verbose_name_plural = "Academic Years"
        # Add a constraint to ensure only one academic year can be current at a time.
        constraints = [
            models.UniqueConstraint(fields=['is_current'], condition=models.Q(is_current=True), name='unique_is_current_academic_year')
        ]

    def __str__(self):
        return self.name


class Subject(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        verbose_name = "Subject"
        verbose_name_plural = "Subjects"

    def __str__(self):
        return f"{self.name} ({self.code})"

class Staff(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='staff_profile')
    subjects = models.ManyToManyField(Subject, through='StaffSubjectAssignment', blank=True) # Added blank=True
    qualification = models.CharField(max_length=100, blank=True)
    date_of_joining = models.DateField(default=timezone.now)

    class Meta:
        verbose_name = "Staff"
        verbose_name_plural = "Staff" # This was already correct

    def __str__(self):
        return self.user.get_full_name() if self.user.get_full_name() else self.user.username

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
        verbose_name = "Bursar"
        verbose_name_plural = "Bursars" # Corrected plural form for better readability

    def __str__(self):
        return self.user.get_full_name() if self.user.get_full_name() else self.user.username

class StaffSubjectAssignment(models.Model):
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    # Using 'StudentClass' instead of 'Class'
    classes = models.ManyToManyField('StudentClass', related_name='subject_assignments', blank=True) # Added blank=True
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('staff', 'subject', 'academic_year')
        verbose_name = "Staff Subject Assignment" # More descriptive
        verbose_name_plural = "Staff Subject Assignments" # More descriptive

    def __str__(self):
        class_names = ', '.join([c.name for c in self.classes.all()])
        return f"{self.staff} teaches {self.subject} in {self.academic_year} to {class_names if class_names else 'no specific classes'}"


class Student(models.Model):
    GENDER_CHOICES = (
        ('M', 'Male'),
        ('F', 'Female'),
        ('O', 'Other'),
    )
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='student_profile')
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES)
    date_of_birth = models.DateField(null=True, blank=True)
    current_class = models.ForeignKey('StudentClass', on_delete=models.SET_NULL, null=True, blank=True, related_name='students') # Added blank=True
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.SET_NULL, null=True, blank=True, related_name='students') # Added blank=True and related_name
    date_of_admission = models.DateField(default=timezone.now)
    father_name = models.CharField(max_length=100, blank=True)
    mother_name = models.CharField(max_length=100, blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ['current_class', 'user__last_name']
        verbose_name = "Student"
        verbose_name_plural = "Students"

    def __str__(self):
        return f"{self.user.get_full_name()} ({self.user.username})"

    # Renamed method for clarity and to indicate it returns a queryset
    def get_fee_transactions(self):
        return self.fee_transactions.all().order_by('-date', '-created_at')

    def get_total_invoiced_fees(self):
        return self.fee_transactions.filter(
            transaction_type='INVOICE'
        ).aggregate(total=models.Sum('amount'))['total'] or 0

    def get_total_paid_fees(self):
        return self.fee_transactions.filter(
            transaction_type='PAYMENT'
        ).aggregate(total=models.Sum('amount'))['total'] or 0

    def get_fee_balance(self):
        return self.get_total_invoiced_fees() - self.get_total_paid_fees()

    # The create_fee_invoice method was a class method on Student in your original file.
    # It makes more sense as a static method or a separate function/service,
    # or potentially a method on the FeeTransaction model.
    # Moved here for now, but consider its placement in a larger application structure.
    @staticmethod
    def create_fee_invoice(student, fee_structure):
        """
        Create a fee invoice transaction for a student.
        """
        if not isinstance(student, Student):
            raise TypeError("student must be an instance of Student model.")
        if not isinstance(fee_structure, FeeStructure):
            raise TypeError("fee_structure must be an instance of FeeStructure model.")

        # Ensure student is linked correctly for the balance calculation
        current_balance = student.get_fee_balance()
        new_balance = current_balance + fee_structure.amount

        # Note: student_id and fee_structure_id are automatically handled by Django
        # when you pass model instances to ForeignKey fields.
        transaction = FeeTransaction.objects.create(
            student=student, # Pass the student instance directly
            transaction_type='INVOICE',
            fee_structure=fee_structure, # Pass the fee_structure instance directly
            amount=fee_structure.amount,
            balance=new_balance,
            # Removed student.session_year_id as it's not directly on Student model
            # and might refer to AcademicYear which is already part of FeeStructure.
            description=f"Invoice for {fee_structure.name} for {student.academic_year}",
            date=timezone.now().date()
        )
        return transaction
    
class StudentClass(models.Model): # Renamed from 'Class' to 'StudentClass' to avoid conflict with Python's 'class' keyword
    name = models.CharField(max_length=50)
    # Use a string reference 'Staff' as Staff is defined later.
    # It's better to use get_user_model() for user-related foreign keys when possible,
    # but here Staff is a profile, so direct reference is fine.
    class_teacher = models.ForeignKey('Staff', on_delete=models.SET_NULL, null=True, blank=True, related_name='class_teacher_of')
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, related_name='classes')

    class Meta:
        verbose_name = "Student Class"
        verbose_name_plural = "Student Classes"
        unique_together = ('name', 'academic_year') # A class name should be unique per academic year

    def __str__(self):
        return f"{self.name} ({self.academic_year})"

class SubjectResult(models.Model):
    TERM_CHOICES = (
        ('TERM_1', 'Term 1'), # Using uppercase for consistency and easier querying
        ('TERM_2', 'Term 2'),
        ('TERM_3', 'Term 3'),
    )
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='results')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='results')
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, related_name='results')
    term = models.CharField(max_length=20, choices=TERM_CHOICES)
    exam_score = models.DecimalField(max_digits=5, decimal_places=2, validators=[MinValueValidator(0), MaxValueValidator(100)])
    assignment_score = models.DecimalField(max_digits=5, decimal_places=2, validators=[MinValueValidator(0), MaxValueValidator(100)])
    created_by = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_results') # Added blank=True
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('student', 'subject', 'academic_year', 'term')
        ordering = ['student', 'subject', 'term']
        verbose_name = "Subject Result"
        verbose_name_plural = "Subject Results"

    @property
    def total_score(self):
        # Ensure scores are treated as decimals for addition
        return (self.exam_score or 0) + (self.assignment_score or 0)

    def __str__(self):
        return f"{self.student} - {self.subject} ({self.get_term_display()} in {self.academic_year})"

class Attendance(models.Model):
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='attendances')
    class_obj = models.ForeignKey('StudentClass', on_delete=models.CASCADE, related_name='attendances') # Renamed to StudentClass
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, related_name='attendances')
    attendance_date = models.DateField()
    created_by = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_attendances') # Added blank=True
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('subject', 'class_obj', 'attendance_date', 'academic_year') # Added academic_year for uniqueness
        verbose_name = "Attendance Record"
        verbose_name_plural = "Attendance Records"

    def __str__(self):
        return f"{self.subject} - {self.class_obj} on {self.attendance_date} ({self.academic_year})"

class AttendanceReport(models.Model):
    STATUS_CHOICES = (
        ('P', 'Present'),
        ('A', 'Absent'),
        ('L', 'Late'),
        ('E', 'Excused'),
    )

    attendance = models.ForeignKey(Attendance, on_delete=models.CASCADE, related_name='reports')
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='attendance_reports')
    status = models.CharField(max_length=1, choices=STATUS_CHOICES, default='P')
    remarks = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('attendance', 'student')
        verbose_name = "Attendance Report"
        verbose_name_plural = "Attendance Reports"

    def __str__(self):
        return f"{self.student} - {self.get_status_display()} ({self.attendance.attendance_date})"

class LeaveRequest(models.Model):
    STATUS_CHOICES = (
        (0, 'Pending'),
        (1, 'Approved'),
        (2, 'Rejected'),
    )

    applicant = models.ForeignKey(User, on_delete=models.CASCADE, related_name='leave_requests') # Using User model
    leave_type = models.CharField(max_length=50)
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.TextField()
    status = models.IntegerField(choices=STATUS_CHOICES, default=0)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_leaves')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Leave Request"
        verbose_name_plural = "Leave Requests"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.applicant} - {self.leave_type} ({self.get_status_display()})"

class Feedback(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='feedback') # Using User model
    message = models.TextField()
    reply = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Feedback"
        verbose_name_plural = "Feedback"
        ordering = ['-created_at']

    def __str__(self):
        return f"Feedback from {self.user.get_full_name() or self.user.username}"


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
    # Using NotificationReadStatus to track individual recipient read status
    # So 'recipients' ManyToMany field can be simplified or removed if only tracking read status.
    # If recipients are meant to be ALL intended recipients, then keep it.
    # Assuming 'recipients' here means who the notification was sent TO.
    recipients = models.ManyToManyField(
        User,
        related_name='received_notifications_direct', # Renamed related_name to avoid confusion with read statuses
        blank=True # Notifications might be for a single user or broadcast, so blank=True is good.
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
    # 'read_at' on Notification model should indicate if *all* recipients have read it (which is hard to track)
    # or just if *any* recipient has read it. It's usually better handled by NotificationReadStatus.
    # Removed 'read_at' from Notification itself.

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'

    def __str__(self):
        return f"{self.title} - {self.get_priority_display()} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"

    # mark_as_read method was implicitly marking the *notification itself* as read,
    # which is problematic for multiple recipients. It should be on NotificationReadStatus.
    # Removed the method from here.

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
    read_at = models.DateTimeField(default=timezone.now) # Changed to default timezone.now, not auto_now_add

    class Meta:
        unique_together = ('notification', 'user')
        verbose_name = 'Notification Read Status'
        verbose_name_plural = 'Notification Read Statuses'
        ordering = ['-read_at'] # Order by read time

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} read '{self.notification.title}' at {self.read_at.strftime('%Y-%m-%d %H:%M')}"

class FeeStructure(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    class_obj = models.ForeignKey('StudentClass', on_delete=models.CASCADE, related_name='fee_structures') # Renamed to StudentClass
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, related_name='fee_structures')
    due_date = models.DateField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Fee Structure"
        verbose_name_plural = "Fee Structures"
        unique_together = ('name', 'class_obj', 'academic_year') # Ensures unique fee structure per class per academic year

    def __str__(self):
        return f"{self.name} - {self.class_obj} ({self.academic_year}) - Ksh{self.amount}"

class FeePayment(models.Model):
    PAYMENT_METHODS = (
        ('MPESA', 'M-Pesa'),
        ('CASH', 'Cash'),
        ('BANK', 'Bank Transfer'),
        ('CHEQUE', 'Cheque'),
        ('ONLINE', 'Online Payment'), # Added a common method
    )

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='payments')
    fee_structure = models.ForeignKey(FeeStructure, on_delete=models.SET_NULL, null=True, blank=True, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_date = models.DateField(default=timezone.now)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS)
    transaction_code = models.CharField(max_length=50, blank=True, help_text="Reference/Transaction ID for the payment") # Added help_text
    received_by = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True, related_name='received_payments') # Added blank=True
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True) # Added created_at
    updated_at = models.DateTimeField(auto_now=True) # Added updated_at

    class Meta:
        verbose_name = "Fee Payment"
        verbose_name_plural = "Fee Payments"
        ordering = ['-payment_date', '-created_at']

    def __str__(self):
        return f"{self.student} - Paid Ksh{self.amount} via {self.get_payment_method_display()} on {self.payment_date}"

class Expense(models.Model):
    CATEGORIES = (
        ('SALARY', 'Staff Salaries'),
        ('FOOD', 'Food Supplies'),
        ('MAINTENANCE', 'Maintenance'),
        ('STATIONERY', 'Stationery'),
        ('UTILITIES', 'Utilities'), # Added utilities
        ('TRANSPORT', 'Transport'), # Added transport
        ('OTHER', 'Other'),
    )

    # bursar is usually a CustomUser with user_type=Bursar, not a Staff.
    # It should probably link to CustomUser or Bursar model.
    # Changed to Bursar for clarity. If staff can also record expenses, then CustomUser is fine.
    recorded_by_bursar = models.ForeignKey(Bursar, on_delete=models.SET_NULL, null=True, blank=True, related_name='recorded_expenses')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    category = models.CharField(max_length=20, choices=CATEGORIES)
    description = models.TextField()
    date = models.DateField(default=timezone.now)
    receipt_number = models.CharField(max_length=50, blank=True, unique=True) # Receipt numbers should be unique
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_expenses') # Using User model
    created_at = models.DateTimeField(auto_now_add=True) # Added created_at
    updated_at = models.DateTimeField(auto_now=True) # Added updated_at

    class Meta:
        verbose_name = "Expense"
        verbose_name_plural = "Expenses"
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.category} - Ksh{self.amount} on {self.date} (Recorded by: {self.recorded_by_bursar or 'N/A'})"

class FeeTransaction(models.Model):
    TRANSACTION_TYPES = (
        ('INVOICE', 'Invoice'),
        ('PAYMENT', 'Payment'),
        ('ADJUSTMENT', 'Adjustment'),
    )

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='fee_transactions')
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    # FeeStructure and FeePayment should be nullable as a transaction might be just an adjustment
    # not tied to a specific fee structure or payment record immediately.
    fee_structure = models.ForeignKey(FeeStructure, on_delete=models.SET_NULL, null=True, blank=True, related_name='transactions')
    fee_payment = models.ForeignKey(FeePayment, on_delete=models.SET_NULL, null=True, blank=True, related_name='transactions')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    balance = models.DecimalField(max_digits=10, decimal_places=2) # This represents the balance *after* this transaction
    description = models.TextField(blank=True)
    date = models.DateField(default=timezone.now) # Changed to default timezone.now.date() for consistency
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Fee Transaction"
        verbose_name_plural = "Fee Transactions"
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.get_transaction_type_display()} for {self.student} - Ksh{self.amount} (Balance: Ksh{self.balance})"

# --- Signals ---

@receiver(post_save, sender=CustomUser)
def create_user_profile(sender, instance, created, **kwargs):
    """
    Signal receiver to create associated Staff, Student, or Bursar profile
    when a CustomUser is created.
    """
    if created:
        if instance.user_type == 2:  # Staff
            Staff.objects.create(user=instance)
        elif instance.user_type == 3:  # Student
            Student.objects.create(user=instance)
        elif instance.user_type == 4:  # Bursar
            Bursar.objects.create(user=instance)
        # No 'else' for Admin (user_type 1) as they don't need a separate profile model typically.

@receiver(post_save, sender=CustomUser)
def save_user_profile(sender, instance, **kwargs):
    """
    Signal receiver to save associated Staff, Student, or Bursar profile
    when a CustomUser is saved (updated).
    """
    # Only try to save if the profile exists.
    # Admin (user_type 1) typically doesn't have a specific profile model, so skip.
    if instance.user_type == 2 and hasattr(instance, 'staff_profile'):  # Staff
        instance.staff_profile.save()
    elif instance.user_type == 3 and hasattr(instance, 'student_profile'):  # Student
        instance.student_profile.save()
    elif instance.user_type == 4 and hasattr(instance, 'bursar_profile'):  # Bursar
        instance.bursar_profile.save()


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
        ('FEE_PAYMENT', 'Fee Payment'), # Added for finance tracking
        ('ATTENDANCE', 'Attendance Recording'), # Added for academic tracking
        ('RESULT_ENTRY', 'Result Entry'), # Added for academic tracking
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
    affected_model = models.CharField(max_length=100, null=True, blank=True,
                                      help_text="Name of the model affected by the action (e.g., 'Student', 'FeePayment')")
    object_id = models.CharField(max_length=100, null=True, blank=True,
                                  help_text="Primary key of the affected object")
    metadata = models.JSONField(default=dict, blank=True,
                                help_text="Additional structured data about the log entry")

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
        return f"[{self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}] {self.get_log_type_display()} - {self.get_action_display()} by {self.user or 'System'}"

    @classmethod
    def create_log(cls, action, details, user=None, request=None,
                     log_type='INFO', affected_model=None, object_id=None, **metadata):
        """
        Helper method to create log entries consistently.
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