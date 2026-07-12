from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User

from .models import UserProfile


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = "Profile"
    fk_name = "user"


class CustomUserAdmin(UserAdmin):
    """
    Extends the default User admin so an Admin can see/edit role and
    BHEL-specific fields (employee ID, department, phone) directly on the
    user's own admin page, instead of needing a separate screen.
    """
    inlines = (UserProfileInline,)
    list_display = ("username", "email", "first_name", "last_name", "is_staff", "get_role")

    def get_role(self, instance):
        return instance.profile.get_role_display()
    get_role.short_description = "Role"


admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "employee_id", "department", "created_at")
    list_filter = ("role", "department")
    search_fields = ("user__username", "user__email", "employee_id")
