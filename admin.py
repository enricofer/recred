from django.contrib.gis import admin
from django import forms
from django.http import FileResponse, HttpResponse, HttpResponseRedirect, Http404
from django.urls import reverse

from django_object_actions import DjangoObjectActions

from .models import Block, formazione, trasferimento, utilizzo, anagrafica, isovalore

from secretary import Renderer

import os, tempfile


parametri = {
    "settore": "Settore urbanistica e servizi catastali",
    "firma_titolo": "Firmato.",
    "firma_nome": "NNNNN MMMMMM",
}

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

def upload_odt(content,filename="recred.odt"):
    
    response = HttpResponse(content_type='application/vnd.oasis.opendocument.text')
    response['Content-Disposition'] = 'inline; filename='+filename

    with tempfile.NamedTemporaryFile() as output:
        output.write(content)
        output.flush()
        output = open(output.name, 'rb')
        response_content = output.read()
        response.write(response_content)

    return response

@admin.register(formazione)
class formazioneAdmin (DjangoObjectActions, baseGeom, admin.OSMGeoAdmin):
    
    def has_delete_permission(self, request, obj=None):
        return False
    
    def has_change_permission(self, request, obj=None):
        if obj is not None:
            return False
        return super().has_change_permission(request, obj=obj)

    change_actions = ('crediti_utilizzati', "crediti_disponibili")
    readonly_fields = ['blockchain_valida', 'isovalore',]
    fields = ['titolare','descrizione','coordinateCatastali', 'ammontare_credito', 'tipo', 'the_geom']
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

    change_actions = ['emetti_il_certificato','vai_alla_transazione','dettaglio_del_credito_originario','genealogia_del_credito','utilizza_il_credito','trasferisci_il_credito']

    changelist_actions = ('esporta_il_recred','filtra_tutti_i_crediti_disponibili','filtra_tutti_i_crediti_utilizzati')

    def get_change_actions(self, request, object_id, form_url):
        actions = super(blockAdmin, self).get_change_actions(request, object_id, form_url)
        actions = list(actions)
        if object_id:
            obj = Block.objects.get(pk=object_id)
            if not obj.can_transact():
                actions.remove('utilizza_il_credito')
                actions.remove('trasferisci_il_credito')
            if obj.data_val("causale") == "utilizzo":
                actions.remove('emetti_il_certificato')
        else:
            actions.remove('genealogia_del_credito')
        return actions
    
    def has_delete_permission(self, request, obj=None):
        return False
    
    def __has_change_permission(self, request, obj=None):
        if obj is not None:
            return False
        return super().has_change_permission(request, obj=obj)

    fields = ['index','data','chain','hash', 'previous_hash', 'nonce']
    list_display = ('pk', 'time_stamp', 'causale', 'cf', 'isovalore', 'ammontare_credito', 'disponibile', 'hash')
    search_fields = ['hash', 'data']

    def emetti_il_certificato(self, request, obj):
        if obj.data_val("causale") == "utilizzo":
            u = utilizzo.objects.get(destinazione__pk=obj.pk)
            return HttpResponseRedirect("/admin/recred/utilizzo/%d" % u.pk)
        engine = Renderer()
        oggetto = "Certificato di proprietà di Credito Edilizio"
        titolare = anagrafica.objects.get(cf=obj.cf)
        modello_path = os.path.join(os.path.dirname(__file__),'templates','certificato_singolo.odt') #modello.modello_odt.path
        result = engine.render(modello_path, credito=obj.as_dict, oggetto=oggetto, parametri=parametri, titolare=titolare) #parametri=modello.parametri
        return upload_odt(result,filename="certificato_proprieta_credito#%d.odt" % obj.pk)

    def vai_alla_transazione(self, request, obj):
        if obj.data_val("causale") == "utilizzo":
            u = utilizzo.objects.get(destinazione__pk=obj.pk)
            return HttpResponseRedirect("/admin/recred/utilizzo/%d" % u.pk)
        elif obj.data_val("causale") in ("trasferimento","residuo"):
            u = trasferimento.objects.get(destinazione__pk=obj.pk)
            return HttpResponseRedirect("/admin/recred/trasferimento/%d" % u.pk)
        if obj.data_val("causale") == "formazione":
            return HttpResponseRedirect("/admin/recred/formazione/%d" % obj.chain.pk)

    def esporta_il_recred(self, request, obj):
        engine = Renderer()
        blockset = []
        for block in Block.objects.all().order_by("pk"):
            blockset.append(block.as_dict)
        modello_path = os.path.join(os.path.dirname(__file__),'templates','registro_recred.odt') #modello.modello_odt.path
        result = engine.render(modello_path, blocks=blockset) #parametri=modello.parametri
        return upload_odt(result,filename="recred.odt")

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

    change_actions = ['certificato_di_trasferimento',]

    fields = ('origine','titolare','repertorio','ammontare_credito',)
    list_display = ('pk', 'time_stamp', 'cf', 'isovalore', 'ammontare_credito')
    autocomplete_fields = ['titolare']

    def certificato_di_trasferimento(self, request, obj):
        engine = Renderer()
        oggetto = "Certificato di trasferimento di Credito Edilizio"
        modello_path = os.path.join(os.path.dirname(__file__),'templates','certificato_trasferimento.odt') #modello.modello_odt.path
        soggetti = {
            "origine": anagrafica.objects.get(cf = obj.origine.data_val("cf")),
            "destinazione": anagrafica.objects.get(cf = obj.destinazione.data_val("cf"))
        }

        result = engine.render(modello_path, trasferimento=obj, soggetti=soggetti, oggetto=oggetto, parametri=parametri) #parametri=modello.parametri
        return upload_odt(result,filename="certificato_trasferimento#%d.odt" % obj.pk)

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

    change_actions = ('certificato_di_utilizzo',)
    readonly_fields = ['isovalore_destinazione','isovalore_origine']
    fields = ['origine','causale','ammontare_credito','isovalore_origine', 'isovalore_destinazione','coordinateCatastali','the_geom']
    list_display = ('pk', 'time_stamp', 'cf', 'isovalore_origine', 'ammontare_credito', 'isovalore_destinazione', 'ammontare_credito_trasformato')

    def certificato_di_utilizzo(self, request, obj):
        engine = Renderer()
        oggetto = "Certificato di utilizzo di Credito Edilizio"
        modello_path = os.path.join(os.path.dirname(__file__),'templates','certificato_utilizzo.odt') #modello.modello_odt.path
        soggetti = {
            "origine": anagrafica.objects.get(cf = obj.origine.data_val("cf")),
            "residuo": anagrafica.objects.get(cf = obj.residuo.data_val("cf")) if obj.residuo else None
        }
        trasformazione = isovalore.objects.get(codice_zona=obj.origine.data_val("isovalore")).trasformazione(obj.isovalore_destinazione)
        result = engine.render(modello_path, utilizzo=obj, soggetti=soggetti, oggetto=oggetto, parametri=parametri, trasformazione=trasformazione) #parametri=modello.parametri
        return upload_odt(result,filename="certificato_utilizzo#%d.odt" % obj.pk)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):        
        origine_hash = request.GET.get('origine', '')
        if origine_hash:
            origine_block = Block.objects.get(hash=origine_hash)
            print (origine_block, origine_block.hash)
            if db_field.name == 'origine':
                kwargs['queryset'] = Block.objects.filter(hash=origine_hash)
                kwargs['initial'] = origine_block.pk
        else:
            available_ids = []
            for item in Block.objects.all():
                if item.can_transact():
                    available_ids.append(item.pk)
            kwargs['queryset'] = Block.objects.filter(pk__in=available_ids)
        formfield = super(utilizzoAdmin, self).formfield_for_foreignkey(db_field, request, **kwargs)
        return formfield


    def get_form(self, request, obj=None, **kwargs):
        form = super(utilizzoAdmin, self).get_form(request, obj, **kwargs)

        if not obj or not obj.origine:
            origine_hash = request.GET.get('origine', '')
            if origine_hash:
                origine_block = Block.objects.get(hash=origine_hash)
                form.base_fields['ammontare_credito'].initial = origine_block.data_val("ammontare_credito")
        return form
            
@admin.register(anagrafica)
class anagraficaAdmin(DjangoObjectActions, baseGeom, admin.OSMGeoAdmin):

    change_actions = ("certificato_di_proprieta","crediti_a_disposizione_del_titolare", "crediti_utilizzati_dal_titolare", "crediti_formati_dal_titolare") # 

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

    def certificato_di_proprieta(self, request, obj):
        engine = Renderer()
        oggetto = "Certificato di proprietà di Crediti Edilizi"
        titolare = obj
        crediti = [b.as_dict for b in obj.crediti_disponibili()]
        modello_path = os.path.join(os.path.dirname(__file__),'templates','certificato_recred.odt') #modello.modello_odt.path
        result = engine.render(modello_path, crediti=crediti, oggetto=oggetto, parametri=parametri, titolare=titolare) #parametri=modello.parametri
        return upload_odt(result,filename="certificato_proprieta_%s.odt" % obj.cf)

@admin.register(isovalore)
class isovaloreAdmin(DjangoObjectActions, baseGeom, admin.OSMGeoAdmin):
    fields = ['fid', 'codice_zona','denominazione','areeurb_valoreconvenzionale','areeurb_valorearea','areenonurb_valorearea','the_geom']