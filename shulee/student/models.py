from django.db import models

# Create your models here.
class Student(models.Model):
    stu_name= models.CharField(max_length=100)
    adm_num = models.IntegerField()
    dob = models.DateField()
    grade = models.IntegerField()
    image = models.ImageField

    def __str__(self): 
            return self.adm_num  

class result(models.Model):
      subjects = models.IntegerField()
      total_marks = models.IntegerField()
      adm_num = models.ForeignKey(Student, on_delete=models.CASCADE)

      def __str__(self): 
            return self.total_marks  