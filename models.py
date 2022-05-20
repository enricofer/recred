from django.contrib.gis.db import models
from django.conf import settings
from django.contrib.auth.hashers import get_random_string
from django.core.serializers.json import DjangoJSONEncoder

import os
import json
import pytz
from hashlib import sha256
from datetime import datetime
from cryptography.fernet import Fernet, base64, InvalidSignature, InvalidToken
import hashlib

__author__ = "Enrico Ferreguti"
__email__ = "enricofer@gmail.com"
__copyright__ = "Copyright 2017, Enrico Ferreguti"
__license__ = "GPL3"


PREF_HASH = "000"


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
    time_stamp = models.DateTimeField(auto_now_add=False)
    index = models.IntegerField(auto_created=True, blank=True)
    data = models.TextField(blank=True, max_length=255)
    hash = models.CharField(max_length=255, blank=True)
    previous_hash = models.CharField(max_length=255)
    chain = models.ForeignKey(to='crediti', on_delete=models.CASCADE)
    nonce = models.CharField(max_length=255, default=0, blank=True)

    def __str__(self):
        return "Block " + str(self.index) + " on " + self.chain.nome

    def __repr__(self):
        return '{}:{}'.format(self.index, str(self.hash)[:8])

    def __hash__(self):
        return sha256(
            u'{}{}{}{}'.format(
                self.index,
                self.data,
                self.previous_hash,
                self.nonce).encode('utf-8')).hexdigest()

    @staticmethod
    def generate_next(latest_block, data):
        block = Block(
            data=data,
            index=latest_block.index + 1,
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
    
    def data_val(self,key):
        return self.data_dict()[key]
    
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
        return self.is_leaf()
    
    def is_leaf(self):
        if self.chain.block_set.filter(previous_hash=self.hash):
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


class crediti(models.Model):
    """
    allows for multiple blockchain entities to exist simultaneously
    """
    time_stamp = models.DateTimeField(auto_now_add=True)
    nome = models.CharField(max_length=255)
    cf = models.CharField(max_length=255)
    coordinateCatastali = models.CharField(max_length=255)
    isovalore = models.CharField(max_length=10)
    the_geom = models.MultiPolygonField(srid=3003,null=True,blank=True)
    volumetria = models.DecimalField(max_digits=10, decimal_places=2)
    descrizione = models.CharField(max_length=255)


    def __str__(self):
        return '{}_{}'.format(self.nome,self.isovalore)

    def __len__(self):
        return self.block_set.count()

    @property
    def data(self):
        record = {
            "causale": "formazione",
            "time_stamp": self.time_stamp or datetime.now(tz=pytz.timezone('Europe/Rome')),
            "nome": self.nome,
            "cf": self.cf,
            "coordinateCatastali": self.coordinateCatastali,
            "isovalore": self.isovalore,
            #"the_geom": self.the_geom.wkt,
            "volumetria": float(self.volumetria),
            "descrizione": self.descrizione
        }
        return json.dumps(record, cls=DjangoJSONEncoder)

    def __repr__(self):
        return '{}_{}: {}'.format(self.nome,self.isovalore, self.last_block)

    @property
    def last_block(self):
        return self.block_set.order_by('index').last()

    @property
    def seed(self):
        return self.block_set.order_by('index').first()

    def create_seed(self):
        assert self.pk is not None
        seed = Block.generate_next(
            Block(hash=sha256('seed'.encode('utf-8')).hexdigest(),
                  index=-1),
            data=self.data,
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
                
    def disponibilita(self):
        result = []
        for block in self.block_set.order_by('index'):
            if block.is_leaf():
                if not block.data_query(causale="utilizzo"):
                    result.append(block)
        return result

    def utilizzi(self):
        return filter(lambda block: block.data_query(causale="utilizzo"), self.block_set.order_by('index'))
    
    def save(self, *args, **kwargs):
        super(crediti,self).save(*args, **kwargs)
        self.create_seed()

class transazioni(models.Model):
    time_stamp = models.DateTimeField(auto_now_add=True)
    origine = models.ForeignKey(to='Block', on_delete=models.CASCADE, related_name='transazioni_origine')
    destinazione = models.ForeignKey(to='Block', on_delete=models.CASCADE, related_name='transazioni_destinazione',null=True,blank=True)
    residuo = models.ForeignKey(to='Block', on_delete=models.CASCADE, related_name='transazioni_residuo',null=True,blank=True)
    nome = models.CharField(max_length=255)
    cf = models.CharField(max_length=255)
    repertorio = models.CharField(max_length=255)
    volumetria = models.DecimalField(max_digits=10, decimal_places=2,null=True,blank=True)

    @property
    def data(self):
        return {
            
        }

    def save(self, *args, **kwargs):

        if not self.origine.can_transact():
            raise ("Il blocco di origine è gia stato utilizzato")

        origine_data = json.loads(self.origine.data)
        disponibilita = float(origine_data["volumetria"])
        residuo_block = None

        self.volumetria = float(self.volumetria or disponibilita)

        if self.volumetria > disponibilita:
            raise ("la volumetria da transare è superiore a quella disponibile")

        if self.volumetria < disponibilita:
            residuo_data = {
            "causale": "residuo",
            "time_stamp": origine_data["time_stamp"],
            "nome": origine_data["nome"],
            "cf": origine_data["cf"],
            "volumetria": disponibilita - self.volumetria
            }
            residuo_block = self.origine.chain.add(self.origine,json.dumps(residuo_data))

            print ("trasferimento di:", self.volumetria," con residuo:", disponibilita - self.volumetria )
        
        else:
            print ("trasferimento senza residuo: ", self.volumetria)

        self.time_stamp = self.time_stamp or datetime.now(tz=pytz.timezone('Europe/Rome'))
        print ("timestamp", self.time_stamp)

        transazione_block = {
            "causale": "transazione",
            "residuo": residuo_block.hash if residuo_block else False,
            "time_stamp": self.time_stamp,
            "nome": self.nome,
            "cf": self.cf,
            "volumetria": self.volumetria,
            "repertorio": self.repertorio
        }

        self.residuo = residuo_block
        self.destinazione = self.origine.chain.add(self.origine,json.dumps(transazione_block, cls=DjangoJSONEncoder))
        super(transazioni,self).save(*args, **kwargs)


class utilizzi(models.Model):
    time_stamp = models.DateTimeField(auto_now_add=True)
    origine = models.ForeignKey(to='Block', on_delete=models.CASCADE, related_name='utilizzi_origine')
    destinazione = models.ForeignKey(to='Block', on_delete=models.CASCADE, related_name='utilizzi_destinazione',null=True,blank=True)
    residuo = models.ForeignKey(to='Block', on_delete=models.CASCADE, related_name='utilizzi_residuo',null=True,blank=True)
    coordinateCatastali = models.CharField(max_length=255)
    isovalore = models.CharField(max_length=10)
    the_geom = models.MultiPolygonField(srid=3003,null=True,blank=True)
    volumetria = models.DecimalField(max_digits=10, decimal_places=2,null=True,blank=True)
    causale = models.CharField(max_length=255)


    def save(self, *args, **kwargs):
        if not self.origine.can_transact():
            raise ("Il blocco di origine è gia stato utilizzato")

        disponibilita = float(self.origine.data_val("volumetria"))
        residuo_block = None

        self.volumetria = float(self.volumetria or disponibilita)

        if self.volumetria > disponibilita:
            raise ("la volumetria da transare è superiore a quella disponibile")

        if self.volumetria < disponibilita:
            residuo_data = {
            "causale": "residuo",
            "time_stamp": self.origine.data_val("time_stamp"),
            "nome": self.origine.data_val("nome"),
            "cf": self.origine.data_val("cf"),
            "volumetria": disponibilita - self.volumetria
            }
            residuo_block = self.origine.chain.add(self.origine, json.dumps(residuo_data, cls=DjangoJSONEncoder))

            print ("utilizzo di:", self.volumetria," con residuo:", disponibilita - self.volumetria )
        
        else:
            print ("utilizzo senza residuo: ", self.volumetria)

        self.time_stamp = self.time_stamp or datetime.now(tz=pytz.timezone('Europe/Rome'))
        utilizzo_block = {
            "causale": "utilizzo",
            "time_stamp": self.time_stamp,
            "nome": self.origine.data_val("nome"),
            "cf": self.origine.data_val("cf"),
            "coordinateCatastali": self.coordinateCatastali,
            "isovalore": self.isovalore,
            "volumetria": self.volumetria,
            "descrizione": self.causale
        }

        self.residuo = residuo_block
        self.destinazione = self.origine.chain.add(self.origine, json.dumps(utilizzo_block, cls=DjangoJSONEncoder))
        super(utilizzi,self).save(*args, **kwargs)

