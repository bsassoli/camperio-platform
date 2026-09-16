# Riallineamento dell'app Comitato: cosa abbiamo fatto e cosa ci serve da te

Camperio SIM · Comitato Investimenti · App di analisi portafoglio
Data: 13 settembre 2026 · Riferimento: pacchetto «Analisi portafoglio per comitato» del 12/09 · Risposte dell'autore ricevute il **16 settembre 2026** · Stato: pronto per la verifica insieme

La versione che hai sviluppato in locale e quella che gira sui server aziendali erano diventate due programmi diversi. Abbiamo riportato nel programma ufficiale le tue correzioni di metodo, tenendo le protezioni già in produzione. Le sei domande che restavano hanno ora la tua risposta: sono riportate qui sotto, ognuna con l'effetto sul piano di lavoro.

**In due righe.** Le tue quattro correzioni di metodo (copertura con i future, base di calcolo delle percentuali, lettura dei file iShares, report comitato ampliato) sono ora nel programma ufficiale, ognuna con un controllo automatico che ne verifica il comportamento. Non abbiamo portato le parti in cui la versione locale è meno sicura di quella in produzione. Il passaggio in produzione della prima correzione deve avvenire **entro giovedì 18 settembre**.

## Perché serviva un riallineamento

Ad agosto il programma è stato messo sui server aziendali con accesso tramite login Microsoft, controlli di sicurezza e verifiche automatiche sui numeri. Nel frattempo tu hai continuato a lavorare sulla copia locale, aggiungendo correzioni importanti al metodo di calcolo. Nessuna delle due versioni conteneva le novità dell'altra.

Non è colpa di nessuno: le due linee sono partite dallo stesso punto a metà agosto e sono cresciute separate. Il rischio, però, era concreto: usare la versione locale così com'era avrebbe rimosso le protezioni di produzione; lasciare la produzione così com'era avrebbe fatto sparire la copertura dai report dopo il 18 settembre.

## Cosa abbiamo portato nel programma ufficiale

### 1. La copertura con i future ora regge al cambio di contratto (urgente)

Il report «Titoli azionari lordo/netto» agganciava il future sull'S&P 500 tramite il codice del contratto in scadenza. Al rinnovo del contratto (18 settembre) quel codice cambia e la copertura sarebbe sparita dal report senza alcun avviso: il netto sarebbe tornato uguale al lordo. Ora il programma riconosce i future dal nome dell'indice e legge l'esposizione direttamente dal gestionale, con il segno giusto. Funziona per tutti gli indici (S&P, Euro Stoxx, DAX, FTSE 100, SMI, mercati emergenti) e per posizioni sia corte sia lunghe.

| Numero | Significato |
|---|---|
| −328.220 € | copertura S&P sul portafoglio 8097S al 10/09, ora correttamente sottratta |
| −7,1 % | del patrimonio: quanto il rischio azionario sarebbe stato sottostimato |
| 18/09 | scadenza del contratto in essere: la correzione deve essere in produzione prima |

In più: un future su un indice per cui non abbiamo il paniere (Nasdaq, Nikkei, Russell, FTSE MIB) viene riconosciuto ma non ripartito sui singoli titoli, invece di finire per errore sull'S&P; e un'opzione su un singolo titolo (per esempio Micron) non viene più scambiata per un future su indice.

### 2. Le percentuali di allocazione si calcolano sul patrimonio

Nel report cliente le percentuali (azioni, obbligazioni, oro, liquidità) usavano come base «patrimonio più esposizione dei derivati», una taratura nata sul portafoglio 8097S che gonfiava la base e abbassava la percentuale azionaria. Ora la base è sempre il patrimonio di fine periodo, come in Antana. Verificato sul portafoglio R1450 al 22 luglio: esposizione azionaria 70.039,56 € su 103.199,94 €, cioè 67,87 % (Antana mostra 67,86 %: differenza di arrotondamento, la confermiamo insieme).

Anche la classificazione dei derivati azionari è più precisa: le opzioni su singole azioni (Uber, Netflix, Nvidia) contano come azionarie, mentre quelle su tassi, cambi e materie prime restano escluse. Abbiamo corretto un caso limite in cui «Goldman Sachs» veniva scartata perché conteneva la parola «gold».

### 3. I file iShares si leggono anche se cambiano formato

Il programma leggeva i panieri degli ETF contando le colonne del file. Se iShares aggiunge una colonna o cambia lingua, la lettura fallisce in silenzio. Ora riconosce le colonne dal titolo, in italiano e in inglese.

### 4. Il report comitato ha le sezioni nuove

Andamento del peso azionario rispetto a settimana, mese e anno precedente; dettaglio titolo per titolo di azioni, fondi/ETF e oro con rendimento in euro e in valuta; colonna «% inizio mese» per classe; nome del cliente nel titolo. Lo storico dei pesi si accumula in avanti a ogni report: parte da zero ora e si popola settimana dopo settimana. Non è ricostruibile a posteriori, quindi lo abbiamo messo tra i dati salvati nei backup.

## Cosa non abbiamo portato, e perché

| Comportamento della versione locale | Cosa succede in produzione | Decisione |
|---|---|---|
| Se il gestionale non risponde, il report viene prodotto lo stesso con l'ultima copia salvata, senza avviso | Il report si ferma e mostra un errore chiaro | tenuta la produzione |
| Nessun controllo che la matrice valutaria quadri con il patrimonio prima di emettere il report | Se i numeri non tornano il report viene bloccato | tenuta la produzione |
| Accesso senza login aziendale, aperto a tutta la rete | Login Microsoft, accesso solo agli utenti autorizzati | tenuta la produzione |
| Piè di pagina del PDF con i contatti vecchi (tel. 02 30322100, dominio camperio.net), riga tagliata a metà parola e numero di pagina coperto | Contatti aggiornati a settembre (02.50020918, camperiosim.com), impaginazione corretta | tenuta la produzione: contatti **confermati** il 16/09 |
| Variazioni di prezzo mostrate nella valuta del titolo invece che in euro | In euro, cambio incluso | tenuta la produzione: l'euro resta il dato principale, la valuta del titolo si **aggiunge** in una colonna a fianco |
| Analisi opzioni e «Chiedi al portafoglio» | Non presenti | rinviate: sui server manca Bloomberg, serve prima il canale dati (vedi risposta 3) |

## Le domande per te, e le tue risposte

Sono le sei cose che non potevamo decidere al posto tuo. Sotto ogni domanda: la risposta ricevuta il 16 settembre 2026 e cosa ne consegue sul programma ufficiale.

### 1. Per ricostruire le quantità a una data passata: registro ordini o registro movimenti?

Nella nota del 26 giugno avevi scritto di usare il registro **ordini**, perché quello dei movimenti mescola collaterale e trasferimenti che non riconciliano. Nella versione locale di settembre, però, il calcolo usa il registro **movimenti**, con un commento che definisce «inaffidabile» il metodo sugli ordini. Una delle due indicazioni è superata.

**Ci serve:** quale dei due vale oggi, e se hai un caso in cui uno dei due dava il numero sbagliato.

**Risposta (16/09):** vale la versione di settembre, cioè il **registro movimenti**. Il metodo sugli ordini non regge sui conti con operatività in derivati o con rettifiche; il caso concreto arriva a parte. Prima di chiudere, però, va fatta una **quadratura su un paio di conti a una data passata con i due metodi a confronto**: se divergono si guarda su cosa.

**Cosa cambia:** il passaggio al registro movimenti è deciso ma **subordinato alla quadratura**. Prepariamo un confronto ORD contro MOV a parità di data sui conti che ci indichi, con l'elenco delle righe che spiegano la differenza; il cambio entra nel programma ufficiale solo dopo. Nota: oggi il programma è misto anche nella tua versione (il report «Variazioni» usa ancora gli ordini per l'aggiustamento dei prezzi), e quel punto va allineato nello stesso passaggio.

### 2. Il modulo «report pesi/valute/titoli» alternativo: serve ancora?

Nel pacchetto c'è un secondo modulo completo che produce gli stessi report in HTML, Word ed Excel, ma non è collegato a nessun pulsante dell'applicazione. Sembra un rifacimento lasciato a metà, oppure un lavoro futuro.

**Ci serve:** è superato, incompiuto, o qualcosa che vuoi finire? Se superato, lo archiviamo.

**Risposta (16/09):** è un rifacimento a metà che vuoi finire tu. Per ora **resta fuori dal programma ufficiale**.

**Cosa cambia:** il modulo non entra nel monorepo e non compare nel piano di back-port. Resta nel pacchetto archiviato fuori dal repository; quando lo avrai completato lo valutiamo come cosa nuova, non come allineamento.

### 3. L'analisi opzioni si collega davvero a Bloomberg?

Il modulo «Analisi opzioni» prova a leggere volatilità e skew da un collegamento Bloomberg che nel pacchetto non c'è. Senza, usa solo i dati di esempio salvati ad agosto. Sul tuo computer probabilmente funziona perché quel collegamento esiste lì.

**Ci serve:** quel collegamento esiste? È un file tuo o una licenza aziendale? Sui server non c'è Bloomberg: il modulo deve girare sui dati salvati, oppure aspettare un accesso ai dati?

**Risposta (16/09):** il collegamento esiste solo sulla tua postazione ed è il **terminale Bloomberg con licenza nominativa**: non è replicabile su un server e non è condivisibile. Sui server il modulo deve girare con **API che prendono il dato dal tuo PC o dalla postazione Bloomberg**.

**Cosa cambia:** il modulo opzioni non può dipendere da Bloomberg installato sul server — sarebbe una violazione di licenza, oltre che tecnicamente impossibile. Serve un passaggio intermedio: la postazione Bloomberg espone (o pubblica su file) volatilità e skew, il server li legge da lì. Finché quel canale non esiste, il modulo resta sui dati salvati e lo dichiara nel report, invece di far credere che il dato sia aggiornato. È un progetto a sé, da mettere in fila dopo il back-port: va deciso con l'IT chi espone l'API, come si autentica e cosa succede quando la postazione è spenta.

### 4. Quali sono i contatti giusti in calce ai report?

A settembre in produzione sono stati corretti telefono, fax ed email nel piè di pagina (02.50020918, camperioSIM@camperiosim.com). La tua versione locale ha ancora quelli precedenti (02 30322100, camperioSIM@camperio.net), che compaiono anche in tutti i report post-earnings.

**Ci serve:** conferma di quale set è quello corrente, così lo allineiamo ovunque una volta sola.

**Risposta (16/09):** il set giusto è **02.50020918 / camperioSIM@camperiosim.com**.

**Cosa cambia:** niente sul programma ufficiale, che già usa quel set: la riga «da confermare» decade e il set del pacchetto locale (02 30322100, camperio.net) è definitivamente superato. Resta da sistemare dove i contatti vecchi compaiono ancora fuori dal programma: la tua copia locale e i sedici script dei report post-earnings.

### 5. Le variazioni di prezzo: in euro o nella valuta del titolo?

La tua versione mostra nel report «Variazioni» il rendimento nella valuta del titolo (quindi senza l'effetto del cambio), la produzione lo mostra in euro. È una scelta di metodo che il comitato vede direttamente.

**Ci serve:** quale delle due vuoi come dato principale; possiamo mostrare l'altra a fianco.

**Risposta (16/09):** **l'euro come dato principale, cambio incluso** — il cliente e il comitato ragionano in euro e tutto il resto del reporting è in euro. La variazione nella valuta del titolo va in una **colonna a fianco**, così l'effetto cambio si legge per differenza.

**Cosa cambia:** il dato principale resta quello della produzione, non si tocca. Si aggiunge la colonna «Var. % valuta» accanto a «Var. %» nei tre formati del report Variazioni (schermo, Word, Excel), con le medie e l'ordinamento che continuano a seguire l'euro. Per i titoli in euro le due colonne coincidono, come deve essere.

### 6. I due loghi in formato vettoriale

Nel pacchetto due file di logo differiscono da quelli in produzione solo nei colori interni (bianco contro blu e grigio). Vogliamo capire se è una modifica voluta.

**Ci serve:** quale versione dei loghi è quella ufficiale.

**Risposta (16/09):** regola fissa: **sui Word si usa il JPG a fondo bianco**, perché il PNG trasparente rende male.

**Cosa cambia:** diventa una regola di redazione, non una scelta caso per caso: i documenti Word prodotti dal programma prendono il logo dal JPG a fondo bianco. Oggi l'intestazione dei Word monta il PNG bianco su fascia blu, quindi la modifica cambia l'aspetto dell'intestazione e va guardata su un documento vero prima di andare in produzione; ci serve inoltre il **file JPG ufficiale** dall'ufficio, perché nel programma non c'è (ricavarlo noi dal PNG vorrebbe dire re-inventare un asset di marchio). Resta invece senza risposta quale dei due SVG sia quello ufficiale: serve solo per la pagina web, non per i Word, e lo chiudiamo alla prossima occasione.

## Come e quando va in produzione

**Entro giovedì 18 settembre:** la correzione della copertura deve essere sui server di produzione, altrimenti dal primo report successivo al rinnovo del contratto il rischio azionario risulterebbe sottostimato di circa sette punti percentuali, senza alcun segnale di errore.

1. **Prima la correzione della copertura**, da sola: installazione sul server di prova, confronto del report Titoli sul portafoglio 8097S con i numeri qui sopra, poi produzione.
2. **Poi tutto il resto** (percentuali, iShares, report comitato ampliato) in un secondo passaggio, sempre prova e poi produzione. Le risposte del 16/09 lo sbloccano: i contatti sono confermati (domanda 4) e la colonna in valuta si aggiunge senza cambiare il dato principale (domanda 5). Il registro movimenti (domanda 1) viaggia **a parte**, dopo la quadratura sui due conti.
3. **«Chiedi al portafoglio»** in un terzo passaggio: non dipende da Bloomberg, quindi può procedere. L'**analisi opzioni** invece resta in attesa del canale dati verso la postazione Bloomberg (domanda 3); intanto, se serve, gira sui dati salvati dichiarandolo nel report. Il modulo «report pesi/valute/titoli» esce dal piano (domanda 2).

Per la verifica insieme ci bastano trenta minuti davanti al server di prova: report Titoli su 8097S, report cliente su R1450 al 22 luglio, report comitato su 8097S con le sezioni nuove.

## Cosa serve da te adesso

Tre cose sole, tutte piccole:

1. **Il caso sugli ordini** che avevi in mente, e **due conti con una data passata** su cui fare la quadratura ordini contro movimenti. Senza quelli il passaggio al registro movimenti resta fermo.
2. **Il file JPG del logo a fondo bianco**, quello ufficiale dell'ufficio, da usare nei Word.
3. **Trenta minuti davanti al server di prova** per la verifica insieme.

## Cosa ti chiediamo per il futuro

- **Un solo programma.** Da ora le modifiche vanno fatte sulla versione ufficiale, non sulla copia locale; altrimenti fra due mesi ci ritroviamo con lo stesso problema. Ti prepariamo un ambiente locale che lavora su dati di esempio, senza bisogno di accesso al gestionale.
- **Il pacchetto che ci hai mandato** è stato messo al sicuro fuori dal repository. Conteneva anche le credenziali di accesso al gestionale e un estratto di dati reali di un cliente: per i prossimi invii basta il solo codice, senza file di configurazione e senza dati.
- **Le analisi post-earnings e gli script di calcolo manuale** restano fuori dal programma: sono materiale di lavoro tuo, non hanno bisogno di stare sui server.

---
Preparato il 13 settembre 2026 sulla base del pacchetto ricevuto il 12 settembre e del programma in produzione al 9 settembre. Tutti i numeri citati sono verificabili sul server di prova. Aggiornato il 16 settembre 2026 con le risposte dell'autore alle sei domande.
