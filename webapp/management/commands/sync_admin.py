from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.core.exceptions import ValidationError
from django.db import transaction
from context_me.access import setting

class Command(BaseCommand):
    help = "Create/update the administrator from ADMIN_USERNAME and ADMIN_PASSWORD."
    def handle(self, *args, **options):
        password = setting("ADMIN_PASSWORD")
        if not password:
            self.stdout.write("No ADMIN_PASSWORD configured. Use createsuperuser to create an administrator.")
            return
        if len(password) < 16:
            raise CommandError("ADMIN_PASSWORD must contain at least 16 characters.")
        username = setting("ADMIN_USERNAME").strip()
        if not username or username.casefold() == "admin":
            raise CommandError("Set ADMIN_USERNAME to a custom username other than admin.")
        User = get_user_model()
        try:
            User._meta.get_field("username").clean(username, None)
        except ValidationError:
            raise CommandError("ADMIN_USERNAME must be a valid Django username of at most 150 characters.")
        previous = setting("ADMIN_PREVIOUS_USERNAME", "admin").strip()
        with transaction.atomic():
            user = User.objects.filter(username=username).first()
            old = User.objects.filter(username=previous).first() if previous != username else None
            if old and (not old.is_superuser or user):
                raise CommandError("Administrator rename conflicts with an existing account. Resolve the accounts before restarting.")
            if user and not user.is_superuser:
                raise CommandError("ADMIN_USERNAME belongs to an existing non-superuser account. Choose another username.")
            renamed = old is not None
            user = old or user or User(username=username)
            user.username = username
            user.is_staff = user.is_superuser = user.is_active = True
            # Rehash on rename to invalidate sessions authenticated under the old login.
            if renamed or not user.check_password(password):
                user.set_password(password)
            user.save()
        self.stdout.write("Administrator account ready.")
