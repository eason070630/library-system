from django.contrib import admin

from .models import Appointment, TimeSlot

admin.site.register(TimeSlot)
admin.site.register(Appointment)
