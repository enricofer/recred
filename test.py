from recred.models import crediti,transazioni,utilizzi

def residui(credito):
    import json
    res = []
    for block in credito.disponibilita():
        data = json.loads(block.data)
        res.append([data["nome"],data["volumetria"],block.hash])
    return res

c1 = crediti(
    nome = "11-AA",
    cf = "00000000000",
    coordinateCatastali = "1/1",
    isovalore = "B1",
    volumetria = 10000,
    descrizione = "formazione credito c1"
) 
c1.save()

print(c1,c1.pk,c1.last_block)

print(c1.is_valid_chain())

print("residui", residui(c1))

t1 = transazioni(
    origine = c1.last_block,
    nome = "BB",
    cf = "11111111111",
    repertorio = "transazione t1",
    volumetria = "5000"
)
t1.save()

print ("t1",t1.origine, t1.destinazione, t1.residuo)

t2 = transazioni(
    origine = t1.residuo,
    nome = "CC",
    cf = "22222222",
    repertorio = "transazione t2",
    volumetria = "1000"
)
t2.save()
print("t2", t2.destinazione.hash, residui(c1))

t3 = transazioni(
    origine = t1.destinazione,
    nome = "DD",
    cf = "33333333333",
    repertorio = "transazione t3",
    volumetria = "1000"
)
t3.save()
print("t3", t3.destinazione.hash, residui(c1))

u1 = utilizzi(
    origine = t3.destinazione,
    coordinateCatastali = "99/99",
    isovalore = "R1",
    #volumetria = 500,
    causale = "utilizzo u1"
)
u1.save()
print("u1", u1.destinazione.hash, residui(c1))

u2 = utilizzi(
    origine = t2.residuo,
    coordinateCatastali = "88/88",
    isovalore = "K1",
    #volumetria = 500,
    causale = "utilizzo u2"
)
u2.save()
print("u2", u2.destinazione.hash, residui(c1))

u3 = utilizzi(
    origine = t3.residuo,
    coordinateCatastali = "88/88",
    isovalore = "K1",
    #volumetria = 500,
    causale = "utilizzo u2"
)
u3.save()
print("u3", u3.destinazione.hash, residui(c1))