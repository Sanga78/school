from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class EmailBackEnd(ModelBackend):
    @staticmethod
    def authenticate(request=None, username=None, password=None, **kwargs):
        UserModel = get_user_model()
        if not username or password is None:
            return None

        try:
            email_matches = UserModel.objects.filter(email__iexact=username)
            if email_matches.count() == 1:
                user = email_matches.get()
            elif '@' not in username:
                user = UserModel.objects.get(username__iexact=username)
            else:
                return None
        except UserModel.DoesNotExist:
            return None
        except UserModel.MultipleObjectsReturned:
            return None

        if user.check_password(password) and ModelBackend().user_can_authenticate(user):
            return user
        return None