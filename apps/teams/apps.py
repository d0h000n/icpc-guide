from django.apps import AppConfig


class TeamsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.teams"
    label = "teams"
    verbose_name = "Teams"

    def ready(self) -> None:
        from django.contrib.auth import get_user_model
        from django.db.models.signals import pre_delete

        from .models import transfer_owned_teams_on_user_delete

        pre_delete.connect(
            transfer_owned_teams_on_user_delete,
            sender=get_user_model(),
            dispatch_uid="teams.transfer_owned_teams_on_user_delete",
        )
