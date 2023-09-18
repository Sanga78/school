from django.shortcuts import render,redirect,reverse
from django.views import generic
from django.contrib.auth.forms import UserCreationForm

# Create your views here.
def index(request):
    return render(request,'index.html')

class SignupView(generic.CreateView):
    template_name = "registration/signup.html"
    form_class = UserCreationForm

    def get_success_url(self):
        return reverse('login')