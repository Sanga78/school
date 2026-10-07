from django.http import HttpResponseRedirect
from django.urls import reverse
from django.views import View
from django.utils.decorators import method_decorator

from index.StaffViews import teacher_required


@method_decorator(teacher_required, name='dispatch')
class EditResultViewClass(View):
    def get(self, request, *args, **kwargs):
        return HttpResponseRedirect(reverse('teacher_dashboard'))

    def post(self, request, *args, **kwargs):
        return HttpResponseRedirect(reverse('teacher_dashboard'))