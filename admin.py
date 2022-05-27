from django.contrib.gis import admin
from django import forms
from django.http import FileResponse, HttpResponse, HttpResponseRedirect, Http404
from django.urls import reverse

from django_object_actions import DjangoObjectActions

from .models import Block, formazione, trasferimento, utilizzo, anagrafica, isovalore


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
    map_template = 'admin/formazione/openlayers_extralayers.html'

def blockchain_output(queryset=None):
    if not queryset:
        queryset = Block.objects.all()
    all_b=[]
    #for b in queryset:


@admin.register(formazione)
class formazioneAdmin (DjangoObjectActions, baseGeom, admin.OSMGeoAdmin):
    
    def has_delete_permission(self, request, obj=None):
        return False
    
    def has_change_permission(self, request, obj=None):
        if obj is not None:
            return False
        return super().has_change_permission(request, obj=obj)

    change_actions = ('crediti_utilizzati', "crediti_disponibili")
    readonly_fields = ['blockchain_valida']
    fields = ['titolare','descrizione','coordinateCatastali', 'isovalore', 'ammontare_credito', 'tipo', 'the_geom']
    list_display = ('pk', 'time_stamp', 'cf','isovalore', 'ammontare_credito', "disponibilita_residua", "utilizzazione",'tipo','blockchain_valida')
    autocomplete_fields = ['titolare']

    def crediti_utilizzati(self, request, obj):
        if obj:
            pks = [b.pk for b in obj.crediti_utilizzati()]
            url = "/admin/recred/block/?" + (("pk__in=" + (",").join(sorted(pks))) if pks else "pk=-1")
            return HttpResponseRedirect(url)

    def crediti_disponibili(self, request, obj):
        if obj:
            pks = [str(b.pk) for b in obj.crediti_disponibili()]
            url = "/admin/recred/block/?" + (("pk__in=" + (",").join(sorted(pks))) if pks else "pk=-1")
            return HttpResponseRedirect(url)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):  
        formfield = super(formazioneAdmin, self).formfield_for_foreignkey(
            db_field, request, **kwargs
        )
        if db_field.name == 'titolare':
            formfield.widget.can_delete_related = False
            formfield.widget.can_change_related = False
            formfield.widget.can_add_related = False
        return formfield

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
    
    def __has_change_permission(self, request, obj=None):
        if obj is not None:
            return False
        return super().has_change_permission(request, obj=obj)

    changelist_actions = ('filtra_tutti_i_crediti_disponibili','filtra_tutti_i_crediti_utilizzati')

    fields = ['index','data','chain','hash', 'previous_hash', 'nonce']
    list_display = ('pk', 'time_stamp', 'causale', 'cf', 'isovalore', 'ammontare_credito', 'disponibile', 'hash')

    def utilizza_il_credito(self, request, obj):
        if obj:
            url = "/admin/recred/utilizzo/add/?origine=" + obj.hash
            return HttpResponseRedirect(url)

    def trasferisci_il_credito(self, request, obj):
        if obj:
            url = "/admin/recred/trasferimento/add/?origine=" + obj.hash
            return HttpResponseRedirect(url)

    def dettaglio_del_credito_originario(self, request, obj):
        if obj:
            url = "/admin/recred/formazione/%s/" % obj.chain.pk
            return HttpResponseRedirect(url)
        
    def filtra_tutti_i_crediti_disponibili(self, request, obj):
        pks = []
        tutte_formazioni = formazione.objects.all()
        for credito in tutte_formazioni:
            pks += [str(b.pk) for b in credito.crediti_disponibili()]
        url = "/admin/recred/block/?" + (("pk__in=" + (",").join(sorted(pks))) if pks else "pk=-1")
        return HttpResponseRedirect(url)
        
    def filtra_tutti_i_crediti_utilizzati(self, request, obj):
        pks = []
        tutte_formazioni = formazione.objects.all()
        for credito in tutte_formazioni:
            pks += [str(b.pk) for b in credito.crediti_utilizzati()]
        url = "/admin/recred/block/?" + (("pk__in=" + (",").join(sorted(pks))) if pks else "pk=-1")
        return HttpResponseRedirect(url)
        
    def genealogia_del_credito(self, request, obj):
        if obj:
            pks = [str(b.pk) for b in obj.genealogy()]
            url = "/admin/recred/block/?pk__in=" + (",").join(sorted(pks))
            return HttpResponseRedirect(url)


@admin.register(trasferimento)
class trasferimentoAdmin(DjangoObjectActions, admin.OSMGeoAdmin):
    
    def has_delete_permission(self, request, obj=None):
        return False
    
    def has_change_permission(self, request, obj=None):
        if obj is not None:
            return False
        return super().has_change_permission(request, obj=obj)

    change_actions = ()

    fields = ('origine','titolare','repertorio','ammontare_credito',)
    list_display = ('pk', 'time_stamp', 'cf', 'isovalore', 'ammontare_credito')
    autocomplete_fields = ['titolare']

    def formfield_for_foreignkey(self, db_field, request, **kwargs):   
        print ("formfield_for_foreignkey")     
        origine_hash = request.GET.get('origine', '')
        if origine_hash:
            origine_block = Block.objects.get(hash=origine_hash)
            if db_field.name == 'origine':
                kwargs['queryset'] = Block.objects.filter(hash=origine_hash)
                kwargs['initial'] = origine_block.pk
        formfield = super(trasferimentoAdmin, self).formfield_for_foreignkey(
            db_field, request, **kwargs
        )
        if db_field.name == 'titolare':
            formfield.widget.can_delete_related = False
            formfield.widget.can_change_related = True
            formfield.widget.can_add_related = True
        if db_field.name == 'origine':
            formfield.widget.can_delete_related = False
            formfield.widget.can_change_related = False
            formfield.widget.can_add_related = False
        return formfield

    def get_form(self, request, obj=None, **kwargs):
        print ("getform")
        form = super(trasferimentoAdmin, self).get_form(request, obj, **kwargs)
        origine_hash = request.GET.get('origine', '')
        if origine_hash:
            origine_block = Block.objects.get(hash=origine_hash)
            form.base_fields['ammontare_credito'].initial = origine_block.data_val("ammontare_credito")
        return form


@admin.register(utilizzo)
class utilizzoAdmin(DjangoObjectActions, baseGeom, admin.OSMGeoAdmin):
    
    def has_delete_permission(self, request, obj=None):
        return False
    
    def has_change_permission(self, request, obj=None):
        if obj is not None:
            return False
        return super().has_change_permission(request, obj=obj)

    change_actions = ()

    fields = ['origine','causale','isovalore','ammontare_credito','coordinateCatastali','the_geom']
    list_display = ('pk', 'time_stamp', 'cf', 'isovalore', 'ammontare_credito')

    def formfield_for_foreignkey(self, db_field, request, **kwargs):        
        origine_hash = request.GET.get('origine', '')
        origine_block = Block.objects.get(hash=origine_hash)
        print (origine_block, origine_block.hash)
        if db_field.name == 'origine':
            kwargs['queryset'] = Block.objects.filter(hash=origine_hash)
            kwargs['initial'] = origine_block.pk
        formfield = super(utilizzoAdmin, self).formfield_for_foreignkey(db_field, request, **kwargs)
        return formfield


    def get_form(self, request, obj=None, **kwargs):
        form = super(utilizzoAdmin, self).get_form(request, obj, **kwargs)
        origine_hash = request.GET.get('origine', '')
        origine_block = Block.objects.get(hash=origine_hash)
        form.base_fields['isovalore'].initial = origine_block.chain.isovalore
        form.base_fields['ammontare_credito'].initial = origine_block.data_val("ammontare_credito")
        return form
            
@admin.register(anagrafica)
class anagraficaAdmin(DjangoObjectActions, baseGeom, admin.OSMGeoAdmin):

    change_actions = ("crediti_a_disposizione_del_titolare", "crediti_utilizzati_dal_titolare", "crediti_formati_dal_titolare") # 

    fields = ['cf','consente_trattamento_dati','cognome','nome','indirizzo','telefono','email','note']
    list_display = ('cf', 'cognome', 'nome', 'disponibilita','consente_trattamento_dati',)
    search_fields = ('cf', 'cognome','note')

    def crediti_a_disposizione_del_titolare(self, request, obj):
        pks = [str(b.pk) for b in obj.crediti_disponibili()]
        url = "/admin/recred/block/?" + (("pk__in=" + (",").join(sorted(pks))) if pks else "pk=-1")
        return HttpResponseRedirect(url)

    def crediti_utilizzati_dal_titolare(self, request, obj):
        #pks = []
        #tutte_formazioni = formazione.objects.all()
        #for credito in tutte_formazioni:
        pks = [str(b.pk) for b in formazione.objects.filter(data__contains='"causale":"utilizzo"').filter(data__contains='"cf":"%s"' % cf).order_by('pk')]
        url = "/admin/recred/block/?" + (("pk__in=" + (",").join(sorted(pks))) if pks else "pk=-1")
        return HttpResponseRedirect(url)

    def crediti_formati_dal_titolare(self, request, obj):
        #pks = []
        #tutte_formazioni = formazione.objects.all()
        #for credito in tutte_formazioni:
        pks = [str(b.pk) for b in formazione.objects.filter(data__contains='"causale":"formazione"').filter(data__contains='"cf":"%s"' % cf).order_by('pk')]
        url = "/admin/recred/block/?" + (("pk__in=" + (",").join(sorted(pks))) if pks else "pk=-1")
        return HttpResponseRedirect(url)

@admin.register(isovalore)
class isovaloreAdmin(DjangoObjectActions, baseGeom, admin.OSMGeoAdmin):
    fields = ['codice_zona','denominazione','areeurb_valoreconvenzionale','areeurb_valorearea','areenonurb_valorearea','the_geom']