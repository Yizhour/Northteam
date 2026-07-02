from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm
from django.contrib.auth.models import User

from .models import (
    CommonWebsite,
    CommonWebsiteSetting,
    Feature,
    FeatureAccess,
    InfoCard,
    InfoCardItem,
    InfoCardPermission,
    InfoCardSetting,
    Intern,
    InternSchedule,
    MarketYieldPoint,
)


def display_staff_name(user):
    if user is None:
        return '实习生本人'
    full_name = user.get_full_name().strip()
    return full_name or user.first_name.strip() or user.get_username()


class RequiredNameUserChangeForm(UserChangeForm):
    first_name = forms.CharField(label='姓名', required=True)

    class Meta(UserChangeForm.Meta):
        model = User
        fields = '__all__'

    def clean_first_name(self):
        value = self.cleaned_data['first_name'].strip()
        if not value:
            raise forms.ValidationError('姓名不能为空。')
        return value


class RequiredNameUserCreationForm(UserCreationForm):
    first_name = forms.CharField(label='姓名', required=True)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'first_name')

    def clean_first_name(self):
        value = self.cleaned_data['first_name'].strip()
        if not value:
            raise forms.ValidationError('姓名不能为空。')
        return value


admin.site.unregister(User)


@admin.register(User)
class WorkspaceUserAdmin(UserAdmin):
    form = RequiredNameUserChangeForm
    add_form = RequiredNameUserCreationForm
    list_display = ('username', 'first_name', 'email', 'is_staff', 'is_active')
    search_fields = ('username', 'first_name', 'last_name', 'email')
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('个人信息', {'fields': ('first_name', 'last_name', 'email')}),
        ('权限', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('重要日期', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'first_name', 'password1', 'password2'),
        }),
    )


@admin.register(Feature)
class FeatureAdmin(admin.ModelAdmin):
    list_display = ('name', 'key', 'url_name', 'sort_order', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'key', 'url_name')
    ordering = ('sort_order', 'id')


@admin.register(FeatureAccess)
class FeatureAccessAdmin(admin.ModelAdmin):
    list_display = ('feature', 'role', 'action', 'allowed')
    list_filter = ('role', 'action', 'allowed', 'feature')
    search_fields = ('feature__name', 'feature__key')


@admin.register(Intern)
class InternAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active', 'access_token', 'updated_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'note', 'access_token')
    readonly_fields = ('access_token', 'created_at', 'updated_at')


@admin.register(InternSchedule)
class InternScheduleAdmin(admin.ModelAdmin):
    list_display = ('title', 'intern', 'schedule_type', 'start_time', 'end_time', 'created_by_display')
    list_filter = ('schedule_type', 'start_time', 'created_by')
    search_fields = ('title', 'intern__name', 'created_by__username', 'created_by__first_name', 'created_by__last_name')
    autocomplete_fields = ('intern', 'created_by')
    date_hierarchy = 'start_time'

    @admin.display(description='安排人', ordering='created_by__first_name')
    def created_by_display(self, obj):
        return display_staff_name(obj.created_by)


@admin.register(MarketYieldPoint)
class MarketYieldPointAdmin(admin.ModelAdmin):
    list_display = ('trading_date', 'curve_name', 'maturity_label', 'yield_rate', 'fetched_at')
    list_filter = ('source', 'curve_code', 'trading_date')
    search_fields = ('curve_name', 'curve_full_name', 'maturity_label')
    date_hierarchy = 'trading_date'


@admin.register(CommonWebsite)
class CommonWebsiteAdmin(admin.ModelAdmin):
    list_display = ('name', 'url', 'sort_order', 'is_active', 'updated_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'url')
    ordering = ('sort_order', 'name', 'id')


@admin.register(CommonWebsiteSetting)
class CommonWebsiteSettingAdmin(admin.ModelAdmin):
    list_display = ('key', 'cards_per_row', 'updated_at')


class InfoCardItemInline(admin.TabularInline):
    model = InfoCardItem
    extra = 1
    fields = ('key', 'value', 'sort_order')
    ordering = ('sort_order', 'id')


class InfoCardPermissionInline(admin.TabularInline):
    model = InfoCardPermission
    extra = 1
    autocomplete_fields = ('user',)


@admin.register(InfoCard)
class InfoCardAdmin(admin.ModelAdmin):
    list_display = ('title', 'sort_order', 'is_active', 'is_restricted', 'updated_at')
    list_filter = ('is_active', 'is_restricted')
    search_fields = ('title', 'items__key', 'items__value')
    ordering = ('sort_order', 'title', 'id')
    inlines = (InfoCardItemInline, InfoCardPermissionInline)


@admin.register(InfoCardItem)
class InfoCardItemAdmin(admin.ModelAdmin):
    list_display = ('card', 'key', 'sort_order')
    search_fields = ('card__title', 'key', 'value')
    ordering = ('card__sort_order', 'sort_order', 'id')


@admin.register(InfoCardPermission)
class InfoCardPermissionAdmin(admin.ModelAdmin):
    list_display = ('card', 'user', 'created_at')
    search_fields = ('card__title', 'user__username', 'user__first_name', 'user__email')
    autocomplete_fields = ('card', 'user')


@admin.register(InfoCardSetting)
class InfoCardSettingAdmin(admin.ModelAdmin):
    list_display = ('key', 'cards_per_row', 'updated_at')
