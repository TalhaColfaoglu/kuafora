from __future__ import annotations

from django.template.response import TemplateResponse
from django.contrib import admin


def admin_help_view(request):
    """
    Admin içi kullanım rehberi.
    Unfold temasıyla uyumlu olması için admin/base_site.html üzerinden render edilir.
    """
    context = {
        **admin.site.each_context(request),
        "title": "Admin Rehberi",
    }
    return TemplateResponse(request, "admin/help.html", context)


