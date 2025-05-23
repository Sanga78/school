from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.views import View
from django.contrib import messages

from index.forms import EditResultForm
from index.models import SubjectResult, Student, Subject


class EditResultViewClass(View):
    def get(self,request,*args,**kwargs):
        staff_id=request.user.id
        edit_result_form = EditResultForm(staff_id=staff_id)
        return render(request,"staff_template/edit_student_result.html",{"form":edit_result_form})
    
    def post(self,request,*args,**kwargs):
        form=EditResultForm(request.POST,staff_id=request.user.id)
        if form.is_valid():
            student_admin_id=form.cleaned_data['student_id']
            assignment_marks=form.cleaned_data['assignment_marks']
            exam_marks=form.cleaned_data['exam_marks']
            subject_id=form.cleaned_data['subject_id']

            student_obj=Student.objects.get(admin=student_admin_id)
            subject_obj=Subject.objects.get(id=subject_id)
            result=SubjectResult.objects.get(subject_id=subject_obj,student_id=student_obj)
            result.subject_assignment_marks=assignment_marks
            result.subject_exam_marks=exam_marks
            result.save()
            messages.success(request,"Successfully Updated Result")
            return HttpResponseRedirect(reverse("edit_student_result"))
        else:
            messages.error(request,"Failed to Update Result")
            form=EditResultForm(request.POST,staff_id=request.user.id)
            return render(request,"staff_template/edit_student_result.html",{"form":form})
            
            