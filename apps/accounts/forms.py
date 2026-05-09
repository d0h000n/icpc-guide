"""Custom allauth forms."""

from __future__ import annotations

from allauth.socialaccount.forms import SignupForm as SocialSignupForm
from django import forms

from .models import User


class CustomSocialSignupForm(SocialSignupForm):
    """OAuth signup: collect nickname; trust the OAuth-verified email as-is."""

    nickname = forms.CharField(
        max_length=30,
        label="닉네임",
        help_text="다른 사용자에게 보이는 이름입니다. 이후 변경 가능합니다.",
    )

    field_order = ["email", "nickname"]

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        # Email comes from the OAuth provider and is treated as authoritative.
        # Mark the field disabled so its value is taken from `initial`, not POST data —
        # this resists tampering even if the rendered HTML is modified client-side.
        if "email" in self.fields:
            self.fields["email"].disabled = True
            self.fields["email"].help_text = "OAuth 계정의 이메일이 사용됩니다."

    def clean_nickname(self) -> str:
        nickname = self.cleaned_data["nickname"].strip()
        if not nickname:
            raise forms.ValidationError("닉네임을 입력하세요.")
        if User.objects.filter(nickname__iexact=nickname).exists():
            raise forms.ValidationError("이미 사용 중인 닉네임입니다.")
        return nickname

    def save(self, request):
        user = super().save(request)
        user.nickname = self.cleaned_data["nickname"]
        user.save(update_fields=["nickname"])
        return user
