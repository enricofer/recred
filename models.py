from django.contrib.gis.db import models
from django.contrib.gis.geos import GEOSGeometry
from django.conf import settings
from django.contrib.auth.hashers import get_random_string
from django.core.serializers.json import DjangoJSONEncoder
from django.core.exceptions import ValidationError,RequestAborted

from localflavor.it.util import ssn_validation,vat_number_validation

import os
import requests
import json
import pytz
from hashlib import sha256
from datetime import datetime
from cryptography.fernet import Fernet, base64, InvalidSignature, InvalidToken
import hashlib
from functools import reduce

__author__ = "Enrico Ferreguti"
__email__ = "enricofer@gmail.com"
__copyright__ = "Copyright 2022, Enrico Ferreguti"
__license__ = "GPL3"

PREF_HASH = "0000"

#potrebbe essere necessario specificare la causale della transazione
CAUSALI_CHOICES = [
    ('compravendita','compravendita'),
    ('voltura','voltura'),
    ('altro','altro'),
]

TIPO_CREDITO_CHOICES = [
    ('CE','Crediti edilizi'),
    ('CER','Crediti edilizi da rinaturalizzazione'),
]

ISOVALORE_CHOICES = [
    ("B1","B1 - CENTRO STORICO ENTRO RIVIERE-VIA XX SETTEMBRE"),
    ("B2","B2 - CENTRO STORICO FUORI RIVIERE-VIA XX SETTEMBRE"),
    ("C1","C1 - PORTELLO"),
    ("C2","C2 - STAZIONE,SCROVEGNI,C.SO DEL POPOLO,FIERA, CITTADELLA"),
    ("C3","C3 - BORGOMAGNO, PRIMA ARCELLA, PESCAROTTO"),
    ("C4","C4 - ZONA DIREZIONALE PADOVAUNO"),
    ("C5","C5 - MADONNA PELLEGRINA, S.RITA, NAZARETH,SANT`OSVALDO"),
    ("C6a","C6a - PALESTRO, SACRA FAMIGLIA, SAN GIUSEPPE"),
    ("C6b","C6b - PORTA TRENTO"),
    ("D1","D1 - CHIESANUOVA,BRUSEGANA"),
    ("D2","D2 - PALTANA, VOLTABRUSEGANA, MANDRIA"),
    ("D3","D3 - BASSANELLO, GUIZZA, VOLTABAROZZO"),
    ("D4","D4 - PONTE DI BRENTA, SAN LAZZARO"),
    ("D5a","D5a - SANT'IGNAZIO, MONTA'"),
    ("D5b","D5b - SACRO CUORE"),
    ("D6","D6 - TORRE, PONTEVIGODARZERE, SACRO CUORE"),
    ("D7","D7 - ARCELLA NORD, MORTISE"),
    ("D8a","D8a - FORCELLINI EST"),
    ("D8b","D8b - SAN GREGORIO"),
    ("D8c","D8c - TERRANEGRA"),
    ("E1","E1 - CAMIN"),
    ("E2","E2 - ZONA INDUSTRIALE,ZIP"),
    ("E3","E3 - SALBORO"),
    ("R1","R1 - RURALE NORD COMPRENDE QUARTIERE PONTEROTTO"),
    ("R2","R2 - RURALE OVEST"),
    ("R3","R3 - RURALE SUD"),
]

def GeomFromCoordinateCatastali(coordinateCatastali, formato='GEOS', check=True):
    url = settings.RAPPER_URL+"certificati/cat_bp/"
    params = {
        "format": "wkt",
        "coordinateCatastali": coordinateCatastali
    }
    print (url)
    res = requests.get(url, params=params)
    if res.status_code == 200:
        return GEOSGeometry(res.json()["geom"]), res.json()["feedback"]
    print (res.url)

def validate_cf(value):
    res1 = True
    try:
        ssn_validation(value)
    except:
        res1 = False
    res2 = True
    try:
        vat_number_validation(value)
    except:
        res2 = False

    if not (res1 or res2):
        raise ValidationError("Codice fiscale errato")

class SymmetricEncryption(object):
    """
    AES256 encryption driven through Fernet library
    """
    @staticmethod
    def generate_key():
        return Fernet.generate_key()

    @staticmethod
    def safe_encode(value):
        if type(value) is str:
            value = value.encode('utf-8')
        return base64.urlsafe_b64encode(value)

    @staticmethod
    def generate_salt(length=12):
        return get_random_string(length=length)

    @classmethod
    def build_encryption_key(cls, password_hash):
        reduced = password_hash[:32].encode('utf-8')
        return base64.urlsafe_b64encode(reduced)

    @staticmethod
    def encrypt(key, secret):
        if type(key) is bytes:
            pass
        if type(secret) is str:
            secret = secret.encode('utf-8')
        if type(secret) is not bytes:
            raise TypeError('%s: Encryption requires string or bytes' % type(secret))

        return Fernet(key).encrypt(secret)

    @staticmethod
    def decrypt(key, token):
        return Fernet(key).decrypt(token)

    @staticmethod
    def hash(key):
        return hashlib.sha512(key).hexdigest()


class Block(models.Model):

    class Meta:
        verbose_name = "Credito"
        verbose_name_plural = "Crediti"

    time_stamp = models.DateTimeField(auto_now_add=False)
    index = models.IntegerField(auto_created=True, blank=True)
    data = models.TextField(blank=True, max_length=255)
    hash = models.CharField(max_length=255, blank=True)
    previous_hash = models.CharField(max_length=255)
    chain = models.ForeignKey(to='formazione', on_delete=models.CASCADE)
    nonce = models.CharField(max_length=255, default=0, blank=True)

    @property
    def isovalore(self):
        return self.chain.isovalore

    @property
    def coordinateCatastali(self):
        return self.chain.coordinateCatastali

    @property
    def foglioMappale(self):
        FMs = self.coordinateCatastali.split(' ',)
        out = ''
        for FM in FMs:
            decodeFM = FM.split('/')
            if decodeFM[0] != FM:
                if len(decodeFM[1].split('-')) == 1:
                    mappaleDesc = 'Mappale'
                else:
                    mappaleDesc = 'Mappali'
                out += ' Foglio '+ decodeFM[0]
                out += ' %s %s'% (mappaleDesc,decodeFM[1])
        return out

    @property
    def causale(self):
        return self.data_val("causale")

    @property
    def timestr(self):
        return self.time_stamp.strftime("%Y-%m-%d %H:%M")

    @property
    def cf(self):
        return self.data_val("cf")

    @property
    def ammontare_credito(self):
        return "{} {}".format( self.data_val("ammontare_credito"),self.data_val("tipo") )

    @property
    def tipo(self):
        return self.data_val("tipo") or "CE"

    @property
    def disponibile(self):
        return self.can_transact()

    def __str__(self):
        return "{}#{}:{} {} {} {}".format(
            self.causale,
            str(self.id),
            self.hash[-6:],
            self.cf,
            self.ammontare_credito,
            self.tipo
        )

    def __repr__(self):
        return '{}:{}'.format(self.index, str(self.hash)[-6:])

    def __hash__(self):
        return sha256(
            u'{}{}{}{}'.format(
                self.index,
                self.data,
                self.previous_hash,
                self.nonce).encode('utf-8')).hexdigest()

    @staticmethod
    def generate_next(latest_block, data, seed=False):
        if seed:
            index = 0
        else:
            index=latest_block.index + 1
        block = Block(
            data=data,
            index=index,
            time_stamp=datetime.now(tz=pytz.timezone('Europe/Rome')),
            previous_hash=latest_block.hash,
            nonce=SymmetricEncryption.generate_salt(26),
        )
        while not block.valid_hash():
            block.nonce = SymmetricEncryption.generate_salt(26)
        block.hash = block.__hash__()

        return block

    def is_valid_block(self, previous_block=None):
        if not previous_block:
            previous_block = self.chain.block_set.get(hash=self.previous_hash)
        if self.index != previous_block.index + 1:
            print('%s: Invalid index: %s and %s' % (self.index, self.index, previous_block.index))
            return False
        if self.previous_hash != previous_block.hash:
            print('%s: Invalid previous hash: %s and %s' % (self.index, self.hash, previous_block.hash))
            return False

        if self.__hash__() != self.hash and self.index > 1:
            print('%s: Invalid hash of content: %s and %s' % (self.index, self.hash, self.__hash__()))
            return False
        if not self.valid_hash() and self.index > 1:
            print('%s: Invalid hash value: %s' % (self.index, self.hash))
            return False
        return True
    
    def data_dict(self):
        return json.loads(self.data)
    
    @property
    def as_dict(self):
        record = self.data_dict()
        record["hash"] = self.hash
        record["prev_hash"] = self.previous_hash
        record["id"] = self.pk
        record["isovalore"] = self.chain.isovalore
        record["isovalore_descrizione"] = zona_isovalore.objects.get(codice_zona=self.chain.isovalore).denominazione if self.chain.isovalore else ""
        record["coordinateCatastali"] = self.coordinateCatastali
        record["foglioMappale"] = self.foglioMappale
        previous_block = Block.objects.filter(hash=self.previous_hash).first()
        record["prev_id"] = previous_block.pk if previous_block else -1
        record["nonce"] = self.nonce
        record["disponibile"] = self.can_transact()
        record["successori"] = [b.as_dict for b in Block.objects.filter(previous_hash=self.hash)]
        return record
    
    def data_val(self,key):
        return self.data_dict().get(key) #attenzione! potrebbe dare falsi risultati in caso di chiave non esistente
    
    def key_in_data(self,key):
        return key in self.data_dict()
    
    def data_query(self,**kwargs):
        for key,value in kwargs.items():
            if not self.key_in_data(key):
                return False
            if not self.data_val(key) == value:
                return False
        return True
    
    def can_transact(self):    
        """ check if block is available for transaction verifying if block hash is not referenced by any other block"""
        print("can_transact", self.is_leaf(), self.data_val("causale"), self.data_val("causale") != 'utilizzo')
        return self.is_leaf() and self.data_val("causale") != 'utilizzo'
    
    def is_leaf(self):
        if self.chain.block_set.filter(previous_hash=self.hash): #self.pk != self.chain.seed.pk and 
            return False
        else:
            return True

    def valid_hash(self):
        """simulate Proof of work"""
        return self.__hash__()[:len(PREF_HASH)] == PREF_HASH
    
    def genealogy(self):
        result = []
        target = self
        while target.hash != self.chain.seed.hash:
            result.append(target)
            target = target.chain.block_set.get(hash=target.previous_hash)
        result.append(self.chain.seed)
        result.reverse()
        return result


class formazione(models.Model):

    class Meta:
        verbose_name = "Formazione"
        verbose_name_plural = "Formazioni"

    """
    allows for multiple blockchain entities to exist simultaneously
    """
    time_stamp = models.DateTimeField(auto_now_add=True)
    nome = models.CharField(max_length=255)
    #cf = models.CharField(max_length=255, validators =[validate_cf])
    titolare = models.ForeignKey(to='anagrafica', on_delete=models.CASCADE)
    coordinateCatastali = models.CharField(max_length=255)
    isovalore = models.CharField(max_length=60,choices=ISOVALORE_CHOICES)
    #isovalore = models.ForeignKey(to='isovalore',null=True,blank=True, on_delete=models.CASCADE)
    the_geom = models.MultiPolygonField(srid=3003,null=True,blank=True)
    ammontare_credito = models.DecimalField(max_digits=10, decimal_places=2)
    tipo = models.CharField(max_length=3,choices=TIPO_CREDITO_CHOICES)
    descrizione = models.CharField(max_length=255)

    def __str__(self):
        return '{}_{}_{}{}'.format(self.cf,self.isovalore,self.ammontare_credito,self.tipo)

    def __len__(self):
        return self.block_set.count()
    
    @property
    def __isovalore(self):
        try:
            return self.zona_isovalore.codice_zona
        except:
            return self.seed.data_val("isovalore")

    def get_data_record(self):
        return {
            "causale": "formazione",
            "time_stamp": self.time_stamp or datetime.now(tz=pytz.timezone('Europe/Rome')),
            "nome": self.nome,
            "cf": self.cf,
            "coordinateCatastali": self.coordinateCatastali,
            "isovalore": self.isovalore,
            #"the_geom": self.the_geom.wkt,
            "ammontare_credito": float(self.ammontare_credito),
            "tipo": self.tipo,
            "descrizione": self.descrizione
        }

    @property
    def data(self):
        return json.dumps(self.get_data_record(), separators=(',', ':'), cls=DjangoJSONEncoder)

    def __repr__(self):
        return '{}_{}: {}'.format(self.nome,self.isovalore, self.last_block)

    @property
    def cf(self):
        return self.titolare.cf or "--------"

    @property
    def last_block(self):
        return self.block_set.order_by('index').last()

    @property
    def seed(self):
        return self.block_set.order_by('index').first()

    def create_seed(self):
        assert self.pk is not None
        last_credito = formazione.objects.last()
        print ("LAST CREDITO", last_credito)
        if last_credito: #viene preso come seed il blocco seed dell'ultimo credito esistente
            seed = Block.generate_next(
                last_credito.block_set.first(),
                data=self.data,
                seed=True
            )
        else: 
            seed = Block.generate_next(
                Block(hash=sha256('seed'.encode('utf-8')).hexdigest(),
                    index=-1),
                data=self.data,
                seed=True
            )
        seed.chain = self
        seed.save()

    def is_valid_next_block(self, block):
        return block.is_valid_block(self.last_block)

    def add(self, leaf, data):
        if not self.block_set.count():
            self.create_seed()

        block = Block.generate_next(
            leaf,
            data
        )
        block.chain = self
        block.save()
        print (block.data)
        return block

    @property
    def blockchain_valida(self):
        return self.is_valid_chain()
    
    def is_valid_chain(self, blocks=None):
        blocks = blocks or list(self.block_set.order_by('index'))
        if not len(blocks):
            print('Empty chain')
            return False
        if len(blocks) == 1 and blocks[0].index != 0:
            print('Missing seed block in chain.')
            return False

        seed = blocks[0]

        def traverse_chain(block,is_valid_chain):
            next_blocks = block.chain.block_set.filter(previous_hash=block.hash)
            for nb in next_blocks:
                is_valid_chain = is_valid_chain and traverse_chain(nb, is_valid_chain and nb.is_valid_block)
            return is_valid_chain

        is_valid_chain = traverse_chain(seed, True)

        if is_valid_chain:
            return True
        else:
            print('Block Tree branch hash mismatch')
            return False

    def _replace_chain(self, new_chain):
        if self.is_valid_chain(new_chain) and len(new_chain) > len(self):
            self.block_set.all().delete()
            for block in new_chain:
                block.chain = self
                block.save()
                
    def crediti_disponibili(self,cf=None):
        result = []
        for block in self.block_set.order_by('index'):
            if block.is_leaf():
                if not block.data_query(causale="utilizzo"):
                    if not cf or (cf and block.data_val("cf") == cf):
                        result.append(block)
        return result
    
    @property
    def disponibilita_residua(self):
        res = reduce( (lambda x, y: x + y), [ b.data_val("ammontare_credito") for b in self.crediti_disponibili() ],0)
        return res
    
    @property
    def utilizzazione(self):
        res = reduce( (lambda x, y: x + y), [ b.data_val("ammontare_credito") for b in self.crediti_utilizzati() ],0)
        return res

    def crediti_utilizzati(self,cf=None):
        crediti_set = self.block_set.filter(data__contains='"causale":"utilizzo"')
        if cf:
            crediti_set.filter(data__contains='"cf":"%s"' % cf)
        print ("crediti_set",crediti_set)
        return crediti_set.order_by('index')
        #return filter(lambda block: block.data_query(causale="utilizzo"), crediti_set)
    
    def save(self, *args, **kwargs):
        #actual_cc = self._meta.get_field('coordinateCatastali').value_from_object(self)
        #actual_geom = self._meta.get_field('the_geom').value_from_object(self)
        self.the_geom,self.coordinateCatastali = GeomFromCoordinateCatastali(self.coordinateCatastali, formato='GEOS', check=True)
        print (self.the_geom.point_on_surface.wkt)
        isovalore = zona_isovalore.objects.filter(the_geom__intersects=self.the_geom.point_on_surface).first()
        self.isovalore = isovalore.codice_zona
        super(formazione,self).save(*args, **kwargs)
        self.create_seed()

class trasferimento(models.Model):

    class Meta:
        verbose_name = "Trasferimento"
        verbose_name_plural = "Trasferimenti"

    time_stamp = models.DateTimeField(auto_now_add=True)
    origine = models.ForeignKey(to='Block', on_delete=models.CASCADE, related_name='transazioni_origine')
    destinazione = models.ForeignKey(to='Block', on_delete=models.CASCADE, related_name='transazioni_destinazione',null=True,blank=True)
    residuo = models.ForeignKey(to='Block', on_delete=models.CASCADE, related_name='transazioni_residuo',null=True,blank=True)
    nome = models.CharField(max_length=255)
    #cf = models.CharField(max_length=255, validators =[validate_cf])
    titolare = models.ForeignKey(to='anagrafica', on_delete=models.CASCADE)
    repertorio = models.CharField(max_length=255)
    ammontare_credito = models.DecimalField(max_digits=10, decimal_places=2,null=True,blank=True)

    @property
    def isovalore(self):
        return self.origine.chain.isovalore

    @property
    def cf(self):
        return self.titolare.cf

    @property
    def tipo(self):
        return self.origine.chain.tipo

    def save(self, *args, **kwargs):

        if not self.origine.can_transact():
            raise RequestAborted("Il blocco di origine è gia stato utilizzato")

        disponibilita = float(self.origine.data_val("ammontare_credito"))
        residuo_block = None

        self.ammontare_credito = float(self.ammontare_credito or disponibilita)

        if self.ammontare_credito > disponibilita:
            raise RequestAborted("Il credito da trasferire è superiore a quello disponibile")

        if self.ammontare_credito < disponibilita:
            residuo_data = {
            "causale": "residuo",
            "time_stamp": self.origine.data_val("time_stamp"),
            "nome": self.origine.data_val("nome"),
            "cf": self.origine.data_val("cf"),
            "ammontare_credito": disponibilita - self.ammontare_credito,
            "tipo": self.tipo,
            }
            residuo_block = self.origine.chain.add(self.origine,json.dumps(residuo_data, separators=(',', ':')))

            print ("trasferimento di:", self.ammontare_credito," con residuo:", disponibilita - self.ammontare_credito )
        
        else:
            print ("trasferimento senza residuo: ", self.ammontare_credito)

        self.time_stamp = self.time_stamp or datetime.now(tz=pytz.timezone('Europe/Rome'))
        print ("timestamp", self.time_stamp)

        transazione_block = {
            "causale": "trasferimento",
            "residuo": residuo_block.hash if residuo_block else False,
            "time_stamp": self.time_stamp,
            "nome": self.nome,
            "cf": self.cf,
            "ammontare_credito": self.ammontare_credito,
            "tipo": self.tipo,
            "descrizione": self.repertorio
        }

        self.residuo = residuo_block
        self.destinazione = self.origine.chain.add(self.origine,json.dumps(transazione_block, separators=(',', ':'), cls=DjangoJSONEncoder))
        super(trasferimento,self).save(*args, **kwargs)


class utilizzo(models.Model):

    class Meta:
        verbose_name = "Utilizzo"
        verbose_name_plural = "Utilizzi"

    time_stamp = models.DateTimeField(auto_now_add=True)
    origine = models.ForeignKey(to='Block', on_delete=models.CASCADE, related_name='utilizzi_origine')
    destinazione = models.ForeignKey(to='Block', on_delete=models.CASCADE, related_name='utilizzi_destinazione',null=True,blank=True)
    residuo = models.ForeignKey(to='Block', on_delete=models.CASCADE, related_name='utilizzi_residuo',null=True,blank=True)
    coordinateCatastali = models.CharField(max_length=255)
    isovalore_destinazione = models.CharField(max_length=10)
    the_geom = models.MultiPolygonField(srid=3003,null=True,blank=True)
    ammontare_credito = models.DecimalField(max_digits=10, decimal_places=2,null=True,blank=True)
    causale = models.CharField(max_length=255)

    @property
    def cf(self):
        return self.origine.cf

    @property
    def tipo(self):
        return self.origine.chain.tipo

    @property
    def isovalore_origine(self):
        return self.origine.chain.isovalore

    @property
    def coefficiente_trasformazione(self):
        zona_isovalore_origine = zona_isovalore.objects.get(codice_zona=self.isovalore_origine)
        zona_isovalore_destinazione = zona_isovalore.objects.get(codice_zona=self.isovalore_destinazione)
        return zona_isovalore_origine.areeurb_valoreconvenzionale/zona_isovalore_destinazione.areeurb_valoreconvenzionale


    @property
    def ammontare_credito_trasformato(self):
        return round(float(self.ammontare_credito)*self.coefficiente_trasformazione,1)

    def save(self, *args, **kwargs):
        if not self.origine.can_transact():
            raise RequestAborted("Il blocco di origine è gia stato utilizzato")

        self.the_geom,self.coordinateCatastali = GeomFromCoordinateCatastali(self.coordinateCatastali, formato='GEOS', check=True)
        zona_isovalore_destinazione = zona_isovalore.objects.filter(the_geom__intersects=self.the_geom.point_on_surface).first()
        self.isovalore_destinazione = zona_isovalore_destinazione.codice_zona

        disponibilita = float(self.origine.data_val("ammontare_credito"))
        residuo_block = None

        self.ammontare_credito = float(self.ammontare_credito or disponibilita)

        if self.ammontare_credito > disponibilita:
            raise RequestAborted("Il credito da utilizzare è superiore a quello disponibile")

        if self.ammontare_credito < disponibilita:
            residuo_data = {
            "causale": "residuo",
            "time_stamp": self.origine.data_val("time_stamp"),
            "nome": self.origine.data_val("nome"),
            "cf": self.origine.data_val("cf"),
            "ammontare_credito": disponibilita - self.ammontare_credito,
            "tipo": self.tipo,
            }
            residuo_block = self.origine.chain.add(self.origine, json.dumps(residuo_data, separators=(',', ':'), cls=DjangoJSONEncoder))

            print ("utilizzo di:", self.ammontare_credito," con residuo:", disponibilita - self.ammontare_credito )
        
        else:
            print ("utilizzo senza residuo: ", self.ammontare_credito)

        self.time_stamp = self.time_stamp or datetime.now(tz=pytz.timezone('Europe/Rome'))
        utilizzo_block = {
            "causale": "utilizzo",
            "time_stamp": self.time_stamp,
            "nome": self.origine.data_val("nome"),
            "cf": self.origine.data_val("cf"),
            "coordinateCatastali": self.coordinateCatastali,
            "isovalore_origine": self.isovalore_origine,
            "isovalore_destinazione": self.isovalore_destinazione,
            "ammontare_credito": self.ammontare_credito,
            "tipo": self.tipo,
            "descrizione": self.causale
        }

        self.residuo = residuo_block
        self.destinazione = self.origine.chain.add(self.origine, json.dumps(utilizzo_block, separators=(',', ':'), cls=DjangoJSONEncoder))
        
        super(utilizzo,self).save(*args, **kwargs)


class zona_isovalore(models.Model):

    class Meta:
        verbose_name = "Zone isovalore"
        verbose_name_plural = "Zona isovalore"

    the_geom = models.MultiPolygonField(srid=3003,)#db_column='the_geom'
    codice_zona = models.CharField(max_length=10, )#db_column='ZONA_ISO'
    denominazione = models.CharField(max_length=110, )#db_column='DENOM'
    areeurb_valoreconvenzionale = models.IntegerField()#db_column='Q_AB_NUOVO'
    areeurb_valorearea = models.IntegerField()#db_column='U_INAREAVr'
    areenonurb_valorearea = models.IntegerField()#db_column='DU_INAREAVr'

    def trasformazione(self,zona_dest):
        isovalore_dest = zona_isovalore.objects.get(codice_zona=zona_dest)
        return round(self.areeurb_valoreconvenzionale/isovalore_dest.areeurb_valoreconvenzionale, 4)

    def __str__(self):
        return "{} / {} {}".format(self.pk, self.codice_zona,self.denominazione)

    def save(self, *args, **kwargs):
        return

    def delete(self, *args, **kwargs):
        return


class anagrafica(models.Model):

    class Meta:
        verbose_name = "Anagrafica"
        verbose_name_plural = "Anagrafica"

    cf = models.CharField(max_length=16, primary_key=True, validators =[validate_cf])
    consente_trattamento_dati = models.BooleanField()
    cognome = models.CharField(verbose_name="cognome/denominazione",max_length=255)
    nome = models.CharField(verbose_name="nome/suffisso",max_length=255)
    indirizzo = models.CharField(max_length=255)
    telefono = models.CharField(max_length=255)
    email = models.CharField(max_length=255)
    note = models.CharField(max_length=255,null=True,blank=True)

    def crediti_disponibili(self):
        tutte_formazioni = formazione.objects.all()
        blks = []
        for credito in tutte_formazioni:
            blks += [b for b in credito.crediti_disponibili(self.cf)]
        return blks
    
    @property
    def disponibilita(self):
        res = reduce( (lambda x, y: x + y), [ b.data_val("ammontare_credito") for b in self.crediti_disponibili() ],0)
        return res

    def save(self, *args, **kwargs):
        self.cf = self.cf.upper()
        self.cognome = self.cognome.upper()
        self.nome = self.nome.capitalize()
        super(anagrafica,self).save(*args, **kwargs)

    def __str__(self):
        return self.cf

