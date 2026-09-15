# Monitoraggio Promotori — domande per Edoardo

Il porting riproduce i numeri della dashboard cowork così come sono oggi, così che il
confronto con quella viva sia possibile. Leggendo il codice sono emerse però alcune
incongruenze: le decide chi usa il cruscotto, non chi lo migra. Finché non c'è una risposta,
il comportamento resta quello dell'originale.

## A · Decisioni di metodo

1. **Due saldi apporti/prelievi diversi.** Il KPI in alto usa i movimenti reali MOV
   (VBG/VBI/PBG/PBI/GCT), come corretto dopo la verifica sulla stampa movimenti. La colonna
   «Saldo apporti/prelievi» del dettaglio contratti usa ancora la variazione dei cumulati
   SRE, che contiene anche commissioni e bolli. Quindi la somma della colonna non torna con
   il KPI. Portiamo anche la colonna su MOV?
2. **Rendimento ufficiale scaricato ma non mostrato.** Dopo la scelta di usare SRE (verifica
   su R1427) la dashboard continuava a interrogare `GES_RENDI_STORICO`, sia per il periodo sia
   per lo YTD, senza mostrarne il risultato. Nella versione migrata la query esiste ma non
   viene eseguita: i numeri non cambiano e Oracle lavora meno. Va eliminata, oppure va
   mostrata accanto al rendimento SRE?
3. **Contratti chiusi nella fotografia «Al».** Con una data Al scelta a mano, la fotografia
   SRE prende l'ultimo snapshot di ogni contratto del referente, compresi quelli chiusi anni
   prima. Un contratto chiuso nel 2025 entra così nel conteggio dei contratti per servizio
   del 2026, con la sua ultima massa, di solito 0. La query dei fondi invece li esclude.
   Aggiungiamo la stessa esclusione anche qui?
4. **Card dei fondi per famiglia.** Il numero sotto ogni famiglia («n contratti»)
   conta le posizioni, non i contratti: un contratto con due classi dello stesso fondo vale 2.
   Nella versione migrata l'etichetta dice «posizioni». Serve invece il numero di contratti?
5. **Finestra di valorizzazione dei fondi.** Il commento nel codice parla di 60 giorni prima
   di Al, la query ne usa 20. Si è tenuto 20. Quale è quello giusto?
6. **Commissioni e operazioni sull'anno solare** anche quando Dal/Al isolano un trimestre (è
   scritto nelle note). Va bene così o devono seguire il periodo?
7. **Storico limitato a 5 anni.** Il limite nasceva dal tetto di risposta del connettore MCP.
   Con la connessione diretta non c'è più: si allarga?
8. **Gruppo Entra.** Chi deve poter aprire il cruscotto? Nel registro la voce è ancora «?».

## B · Differenze già introdotte (da confermare, nessuna cambia i numeri dei casi normali)

1. **Periodo di default**: non più fisso al 01/01–30/06/2026, ma dal 1° gennaio all'ultimo
   aggiornamento disponibile, come già dicevano le note. L'originale all'avvio mostrava
   «al 30/06» ma calcolava le masse all'ultimo aggiornamento e fondi e flussi al 30/06:
   questa incoerenza sparisce.
2. **Ordine Dal/Al**: nell'originale, cambiare Al dopo aver cambiato Dal cancellava lo
   snapshot Dal. Saldo e rendimento tornavano così al fine anno precedente, mentre in pagina
   restava il Dal scelto. Ora Dal e Al valgono sempre entrambi.
3. **Contratto con il solo snapshot Dal** (esistente a Dal, senza massa nell'anno):
   nell'originale il KPI massa diventava «n.d.», ora il contratto non conta nella massa.
4. **Nessun limite di righe**: l'originale chiedeva al massimo 50 referenti per il menu e
   tetti fissi di righe sulle altre query, e tagliava oltre senza avvisare. Quanti
   referenti ci sono oggi? Se erano più di 50, qualcuno non compariva nel menu.
5. **Nomi dei referenti** fuori dal codice, in un file sulla VM da mantenere a mano (vedi
   README). Nei codici che l'originale non conosceva compariva il solo codice, e resta così.
