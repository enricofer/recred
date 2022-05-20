from django.contrib import admin
from .models import Block, crediti, transazioni, utilizzi

# Register your models here.
admin.site.register(Block)
admin.site.register(crediti)
admin.site.register(transazioni)
admin.site.register(utilizzi)