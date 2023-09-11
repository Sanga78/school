from django.db import models

# Create your models here.
class Student(models.Model):
    stu_name= models.CharField(max_length=100)
    adm_num = models.IntegerField()
    dob = models.DateField()
    grade = models.IntegerField()
    image = models.ImageField

    def __str__(self): 
            return self.stu_name  
    