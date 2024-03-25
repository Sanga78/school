from django.shortcuts import render
from index.models import Subjects,SessionYearModel,Students
from django.views.decorators.csrf import csrf_exempt

def staff_home(request):
    return render(request, "staff_template/staff_home.html")


def staff_take_attendance(request):
    subjects = Subjects.objects.filter(staff_id=request.user.id)
    session_years = SessionYearModel.object.all()
    return render(request,"staff_template/attendance.html",{"subjects":subjects,"session_years":session_years})

@csrf_exempt
def get_students(request):
    subject_id = request.POST.get("subject")
    session_year = request.POST.get("session_year")

    subject = Subjects.objects.get(id=subject_id)
    session_model = SessionYearModel.object.get(id=session_year)
    students = Students.objects.filter(corse_id=subject.course_id,session_id=session_model)
    return students