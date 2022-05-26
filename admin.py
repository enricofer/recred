from django.contrib.gis import admin
from django import forms
from django.http import FileResponse, HttpResponse, HttpResponseRedirect, Http404
from django.urls import reverse

from django_object_actions import DjangoObjectActions

from .models import Block, crediti, transazioni, utilizzi, isovalore


class baseGeom:
    default_lon = 1725155
    default_lat = 5032083
    default_zoom = 13
    max_resolution = 350000
    num_zoom = 28
    max_zoom = 28
    min_zoom = 10
    map_width = 700
    map_height = 500
    map_srid = 3003
    wms_url = "https://rapper.comune.padova.it/mapproxy/"
    wms_layer = 'PI2030'
    wms_name = 'PI'
    map_template = 'admin/crediti/openlayers_extralayers.html'

@admin.register(crediti)
class creditiAdmin (DjangoObjectActions, baseGeom, admin.OSMGeoAdmin):
    
    def has_delete_permission(self, request, obj=None):
        return False
    
    def has_change_permission(self, request, obj=None):
        if obj is not None:
            return False
        return super().has_change_permission(request, obj=obj)

    change_actions = ('crediti_utilizzabili', "crediti_disponibiliti")

    fields = ['cf','descrizione','coordinateCatastali', 'isovalore', 'volumetria', 'tipo', 'the_geom']
    list_display = ('pk', 'time_stamp', 'cf','isovalore', 'volumetria', "disponibilita_residua", "utilizzazione",'tipo')

    def crediti_utilizzabili(self, request, obj):
        if obj:
            utilizzi_pks = [b.hash for b in obj.crediti_utilizzati()]
            url = "/admin/recred/block/?hash__in=" + (",").join(sorted(utilizzi_pks))
            return HttpResponseRedirect(url)

    def crediti_disponibiliti(self, request, obj):
        if obj:
            disponibilita_pks = [str(b.pk) for b in obj.crediti_disponibili()]
            url = "/admin/recred/block/?pk__in=" + (",").join(sorted(disponibilita_pks))
            print (url)
            return HttpResponseRedirect(url)

@admin.register(Block)
class blockAdmin (DjangoObjectActions, admin.OSMGeoAdmin):

    change_actions = ['dettaglio_del_credito_originario','genealogia_del_credito','utilizza_il_credito','trasferisci_il_credito']

    def get_change_actions(self, request, object_id, form_url):
        actions = super(blockAdmin, self).get_change_actions(request, object_id, form_url)
        actions = list(actions)
        if object_id:
            obj = Block.objects.get(pk=object_id)
            if not obj.can_transact():
                actions.remove('utilizza_il_credito')
                actions.remove('trasferisci_il_credito')
        else:
            actions.remove('genealogia_del_credito')
        return actions
    
    def has_delete_permission(self, request, obj=None):
        return False
    
    def has_change_permission(self, request, obj=None):
        if obj is not None:
            return False
        return super().has_change_permission(request, obj=obj)

    changelist_actions = ('filtra_tutti_i_crediti_disponibili','filtra_tutti_i_crediti_utilizzati')

    readonly_fields = ['index','data','chain','hash', 'previous_hash', 'nonce']
    list_display = ('pk', 'time_stamp', 'causale', 'cf', 'isovalore', 'volumetria', 'hash')

    def utilizza_il_credito(self, request, obj):
        if obj:
            url = "/admin/recred/utilizzi/add/?origine=" + obj.hash
            return HttpResponseRedirect(url)

    def trasferisci_il_credito(self, request, obj):
        if obj:
            url = "/admin/recred/transazioni/add/?origine=" + obj.hash
            return HttpResponseRedirect(url)

    def dettaglio_del_credito_originario(self, request, obj):
        if obj:
            url = "/admin/recred/crediti/%s/" % obj.chain.pk
            return HttpResponseRedirect(url)
        
    def filtra_tutti_i_crediti_disponibili(self, request, obj):
        disponibilita_pks = []
        tutte_formazioni_crediti = crediti.objects.all()
        for credito in tutte_formazioni_crediti:
            disponibilita_pks += [str(b.pk) for b in credito.crediti_disponibili()]
        url = "/admin/recred/block/?pk__in=" + (",").join(sorted(disponibilita_pks))
        return HttpResponseRedirect(url)
        
    def filtra_tutti_i_crediti_utilizzati(self, request, obj):
        utilizzati_pks = []
        tutte_formazioni_crediti = crediti.objects.all()
        for credito in tutte_formazioni_crediti:
            utilizzati_pks += [str(b.pk) for b in credito.crediti_utilizzati()]

        url = "/admin/recred/block/?pk__in=" + (",").join(sorted(utilizzati_pks))
        return HttpResponseRedirect(url)
        
    def genealogia_del_credito(self, request, obj):
        if obj:
            genealogia_pks = [str(b.pk) for b in obj.genealogy()]
            url = "/admin/recred/block/?pk__in=" + (",").join(sorted(genealogia_pks))
            return HttpResponseRedirect(url)


@admin.register(transazioni)
class transazioniAdmin(DjangoObjectActions, admin.OSMGeoAdmin):
    
    def has_delete_permission(self, request, obj=None):
        return False
    
    def has_change_permission(self, request, obj=None):
        if obj is not None:
            return False
        return super().has_change_permission(request, obj=obj)

    change_actions = ()

    fields = ('origine','cf','repertorio','volumetria',)
    list_display = ('pk', 'time_stamp', 'cf', 'isovalore', 'volumetria')

    def formfield_for_foreignkey(self, db_field, request, **kwargs):   
        print ("formfield_for_foreignkey")     
        origine_hash = request.GET.get('origine', '')
        if origine_hash:
            origine_block = Block.objects.get(hash=origine_hash)
            if db_field.name == 'origine':
                kwargs['queryset'] = Block.objects.filter(hash=origine_hash)
                kwargs['initial'] = origine_block.pk
        formfield = super(transazioniAdmin, self).formfield_for_foreignkey(
            db_field, request, **kwargs
        )
        return formfield

    def get_form(self, request, obj=None, **kwargs):
        print ("getform")
        form = super(transazioniAdmin, self).get_form(request, obj, **kwargs)
        origine_hash = request.GET.get('origine', '')
        if origine_hash:
            origine_block = Block.objects.get(hash=origine_hash)
            form.base_fields['volumetria'].initial = origine_block.data_val("volumetria")
        return form
        

@admin.register(utilizzi)
class utilizziAdmin(DjangoObjectActions, baseGeom, admin.OSMGeoAdmin):
    
    def has_delete_permission(self, request, obj=None):
        return False
    
    def has_change_permission(self, request, obj=None):
        if obj is not None:
            return False
        return super().has_change_permission(request, obj=obj)

    change_actions = ()

    fields = ['origine','causale','isovalore','volumetria','coordinateCatastali','the_geom']
    list_display = ('pk', 'time_stamp', 'cf', 'isovalore', 'volumetria')

    def formfield_for_foreignkey(self, db_field, request, **kwargs):        
        origine_hash = request.GET.get('origine', '')
        origine_block = Block.objects.get(hash=origine_hash)
        print (origine_block, origine_block.hash)
        if db_field.name == 'origine':
            kwargs['queryset'] = Block.objects.filter(hash=origine_hash)
            kwargs['initial'] = origine_block.pk
        formfield = super(utilizziAdmin, self).formfield_for_foreignkey(db_field, request, **kwargs)
        return formfield


    def get_form(self, request, obj=None, **kwargs):
        form = super(utilizziAdmin, self).get_form(request, obj, **kwargs)
        origine_hash = request.GET.get('origine', '')
        origine_block = Block.objects.get(hash=origine_hash)
        form.base_fields['isovalore'].initial = origine_block.chain.isovalore
        form.base_fields['volumetria'].initial = origine_block.data_val("volumetria")
        return form
            


# Register your models here.
#admin.site.register(Block)
#admin.site.register(transazioni)
#admin.site.register(utilizzi)
#admin.site.register(isovalore)