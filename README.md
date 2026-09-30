# Portfolio Lab

Simulatore storico di portafogli (ETF, azioni, obbligazioni, materie prime) con interfaccia Qt.

## Avvio

Doppio clic su **Avvia.bat**. Al primo avvio crea l'ambiente Python e scarica circa 1 minuto di dati da Yahoo Finance.

Oppure da terminale:

```
.venv\Scripts\python -m app.main
```

## Cosa fa

- **Portafoglio**: scegli tra 200 strumenti (50 per categoria), assegni i pesi e vedi valore finale, rendimento annuo, volatilità, max drawdown, Sharpe, rendimenti anno per anno, confronto con un benchmark. Supporta capitale iniziale + PAC mensile, ribilanciamento, EUR/USD.
- **Ottimizzatore**: trova 3 portafogli (miglior rischio/rendimento, massimo rendimento, minimo rischio) rispettando vincoli per categoria e peso massimo per asset, con grafico della frontiera efficiente.
- **Proiezione futura**: "se verso X € al mese, nel 20XX quanto avrò?". Mostra lo scenario probabile, pessimistico e ottimistico con 5.000 simulazioni basate sullo storico del tuo portafoglio (o un rendimento fisso), tiene conto dell'inflazione e con un obiettivo in € calcola la probabilità di raggiungerlo e quanto versare al mese.
- **Guida**: spiegazione dei termini.

## Struttura

| File | Contenuto |
|---|---|
| `app/universe.py` | elenco degli asset (modifica qui per aggiungerne) |
| `app/data.py` | download Yahoo Finance, cache in `cache/`, conversione in euro |
| `app/backtest.py` | simulazione mensile, PAC, ribilanciamento, metriche |
| `app/optimizer.py` | ottimizzazione (scipy) e frontiera efficiente |
| `app/ui/` | interfaccia PySide6 + grafici pyqtgraph |

## Limiti

Prezzi con dividendi reinvestiti; esclusi tasse, commissioni e costi di cambio. I future sulle materie prime (`=F`) sono prezzi del contratto più vicino, indicativi e non replicabili 1:1. Risultati passati non garantiscono quelli futuri.
