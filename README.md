Student: Sindrilaru Catalina-Maria

Grupa: 332CA

# Tema 1 - RL

Codul initial pentru task-urile 1 si 2 este lasat comentat la finalul
fisierului switch.py, pentru a se vedea codul si inainte de adaugarea
stp-ului.

Explicatii:

Inainte de adaugarea stp-ului, pentru implementarea vlan-urilor, am 
ales sa folosesc un dictionar pentru tabela mac, in care cheia sa
fie adresa mac, iar valoarea numarul interfetei corespunzatoare.
Totodata, am folosit un dictionar numit type_interfaces,
pe care l-am folosit pentru citirea din fisierul de configuratie
corespunzator fiecarui switch, in care cheia este reprezentata de numele
interfetei (ex: r-0, r-1, rr-0-1), iar valoarea de numele vlan-ului aferent
interfetei (in cazul unei interfete de tip access), sau de litera 'T', daca
interfata este de tip trunk. Dupa aceste initializari, in cadrul structurii
`while` din main, verific daca cadrul este de tip bpdu, ceea ce voi detalia
ulterior, altfel, adaug adresa mac sursa in tabela mac, impreuna cu interfata
pe care a fost primit cadrul si tratez 2 cazuri. Daca destinatia mac este in
tabela mac si daca nu este. Apoi, am urmat modelul din enuntul temei de la 
sectiunea `VLAN` si am luat in considerare (atat pentru cazul in care cadrul
se va trimite doar pe o interfata deja cunoscuta din tabela mac sau pe toate
interfetele inafara de cea pe care s-a primit pachetul), daca cadrul s-a
primit de pe o interfata access sau de pe una trunk. Acest aspect l-am
verificat cu ajutorul 'vlan_id', extras deja in schelet si care este -1
daca cadrul vine de pe access si diferit de -1 daca vine de pe trunk. Pentru
o buna intelegere a codului. Astfel, am creat functiile 'send_frame_from_access' si
'send_frame_from_trunk' care trateaza aceste cazuri. Pentru fiecare din
cele 2 cazuri, am verificat astfel daca interfata pe care se va trimite
cadrul este de tip access sau trunk pentru a lua in considerare existenta
tag-ului in interiorul acestuia.

In functia 'send_frame_from_access', cadrul existent 'data' nu are
tag adaugat, deoarece am verificat anterior ca acesta era -1. Daca interfata
destinatie este de tip trunk, o sa creez un cadru nou, in care inserez numarul
vlanului (pe care il iau din dictionarul type_interfaces) si pentru care cresc
lungimea cu 4 (cei 4 bytes adaugati de id-ul vlan-ului), apoi il trimit pe interfata
destinatie. Daca interfata destinatie este de tip access, nu trebuie
sa adaug tag pentru vlan, insa trebuie sa verific daca vlan-ul aferent
interfetei sursa este acelasi cu vlan-ul aferent interfetei destinatie, pentru
ca doar in acest caz voi trimite cadrul (in cazul in care vlan-urile nu
corespund, nu voi trimite nimic, adica voi da discard la acel cadru).

In functia 'send_frame_from_trunk', cadrul existent 'data' deja are un tag
pentru vlan adaugat (adica vlan_id). Si aici exista aceleasi 2 cazuri. Daca
interfata destinatie este trunk, nu voi modifica nimic la cadru, il voi trimite
cu acelasi tag pentru vlan mai departe. Insa daca interfata destinatie este access,
verific daca vlan-ul aferent interfetei destinatie este acelasi cu vlan-ul din cadru,
iar daca este acelasi, scot acel tag de vlan din cadru si abia apoi il trimit pe
interfata access care este destinatia mea.


Pentru implementarea de `STP`, am urmarit pseudocodul mentionat in cerinta temei.
Pentru starile interfetelor (designated, blocking), am folosit un dictionar in care
cheia este numarul interfetei si valoarea este starea.
Am facut initializarile asa cum se mentiona, toate interfetele unui switch fiind
initial in starea DESIGNATED, iar bridge-id-ul unui switch egal cu root-bridge-id-ul.

Toate variabilele folosite in cadrul functiei 'send_bpdu_every_sec' le-am declarat 
global, pentru a fi vizibile in tot fisierul (functia este realizata de un thread).
In aceasta functie ('send_bpdu_every_sec'), am format bpdu config asa cum se mentiona
in enunt la 'Structura BPDU Config'. Am folosit struct.pack pentru a declara un
anumit numar de bytes. Acest bpdu_config, impreuna cu sursa si destinatia mac,
le-am trimis pe fiecare port trunk al switch-ului.

Revenind in structura 'while' din functia main, am verificat daca destinatia mac
a cadrului primit este adresa multicast pentru bpdu(01:80:C2:00:00:00), iar daca
este, am scos din bpdu-ul primit, bpdu_config (am folosit pe tot parcursul temei int.from_bytes pentru tot ce am folosit legat de bpdu_config pentru ca
struct.pack trimite ca bytes iar comparatiile ulterioare eu le fac cu int-uri).

Am verificat astfel daca switch-ul a primit un bpdu in care root_bridge_id-ul era
mai mic decat cel stiut de switch si astfel isi actualizeaza datele si costul. In cazul in
care el se considera root_bridge inainte, isi va trece interfetele pe blocking,
iar root port-ul pe designated. Daca switch-ul este in continuare root bridge, 
acesta va avea toate interfetele designated. Avand in vedere ca am adaugat aceste
stari pentru porturi, la partea de vlan-uri, inainte de a trimite un cadru, am 
verificat ca interfata destinatie sa nu fie in starea blocking.
