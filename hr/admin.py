from django.contrib import admin

from .models import Employee, PayrollItem, PayrollPeriod, SalaryAdvance, SalaryPayment


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ("full_name", "position", "base_salary", "tenant", "is_active")


class PayrollItemInline(admin.TabularInline):
    model = PayrollItem
    extra = 0


@admin.register(PayrollPeriod)
class PayrollPeriodAdmin(admin.ModelAdmin):
    list_display = ("year", "month", "status", "tenant")
    inlines = [PayrollItemInline]


@admin.register(SalaryPayment)
class SalaryPaymentAdmin(admin.ModelAdmin):
    list_display = ("item", "amount", "paid_at", "method")
