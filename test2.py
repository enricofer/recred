from recred.models import Block,crediti,transazioni,utilizzi

import json

c1 = crediti.objects.get(pk=75)

def residui(credito):
    import json
    res = []
    for block in credito.disponibilita():
        data = json.loads(block.data)
        res.append([data["nome"],data["volumetria"],block.hash])
    return res

print(c1.last_block)

print(c1.is_valid_chain())

print("residui", residui(c1))

print("utilizzi", [[b.data_val("nome"),b.data_val("volumetria"),b.hash] for b in c1.utilizzi()])

seed = c1.block_set.order_by('index').first()
print ("seed",seed)

print   ()
print   ("========================================================")
print ("leafs",list(c1.block_set.filter(previous_hash=seed.hash)))
print   ("----------------------------------------------------------------")
target = "000a4d46e7b1fdca19b293ad08d65519eee40770e807cc76102a6b578a12b430"

b1 = Block.objects.get(hash=target)

print ("is_valid_block", b1.is_valid_block())
print   ()
print   ("========================================================")
print ("genealogy", b1.genealogy())

for b in b1.genealogy():
    print ("------------------------")
    print (b.hash)
    print ("------------------------")
    print (json.loads(b.data))

print   ()
print   ("========================================================")
print ("tutti blocchi", b1.chain.block_set.order_by('index'))

for b in b1.chain.block_set.order_by('index'):
    print ("------------------------")
    print (b.hash)
    print ("------------------------")
    print (json.loads(b.data))