import requests, json, gzip, base64, sys
from io import StringIO

SHEET_ID = "1FwVTs_sEjbEbi2BSscJFwpXzpYE0ySsy"
SHEET_NAME = "Cartera"
MESES = ['Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre']

def fetch_sheet():
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={SHEET_NAME}"
    print(f"Fetching: {url}")
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    return r.text

def parse_csv(text):
    import csv
    reader = csv.DictReader(StringIO(text))
    records = []
    mes_num = {m:i+1 for i,m in enumerate(MESES)}
    skipped = 0
    for row in reader:
        try:
            año = int(float(str(row.get('Año','0')).strip() or 0))
            mes = str(row.get('Mes','')).strip()
            if not año or not mes:
                skipped += 1
                continue
            def to_int(v):
                return int(float(str(v).replace(',','').replace(' ','') or 0))
            mn = mes_num.get(mes, 0)
            records.append({
                'año': año, 'mes': mes,
                'servicio': str(row.get('Servicio','')).strip(),
                'nombre': str(row.get('Nombres','')).strip(),
                'documento': str(row.get('Documento','')).strip(),
                'direccion': str(row.get('Direccion','')).strip(),
                'telefono': str(row.get('Telefono','')).strip(),
                'cuenta': str(row.get('Nro Cuenta','')).strip(),
                'fecha': str(row.get('Fecha','')).strip(),
                'vencimiento': str(row.get('Vencimiento','')).strip(),
                'dias': to_int(row.get('Dias Vcto', 0)),
                'rango': str(row.get('Rango','')).strip(),
                'capital': to_int(row.get('Capital', 0)),
                'interes': to_int(row.get('Interes', 0)),
                'saldo': to_int(row.get('Saldo', 0)),
                'pqr': str(row.get('Pqr','')).strip(),
                'gestion': str(row.get('Gestion','')).strip(),
                'periodo': año * 100 + mn,
            })
        except Exception as e:
            skipped += 1
    print(f"  Parsed: {len(records)} records, {skipped} skipped")
    return records

def build_recovery(records):
    from collections import defaultdict
    by_cuenta = defaultdict(list)
    for r in records:
        if r['cuenta']:
            by_cuenta[r['cuenta']].append(r)
    recovery_period = {}
    recovery_by_client = {}
    for cuenta, rows in by_cuenta.items():
        rows_s = sorted(rows, key=lambda x: x['periodo'])
        prev = None
        for r in rows_s:
            if prev and r['periodo'] != prev['periodo']:
                diff = prev['saldo'] - r['saldo']
                if diff > 100:
                    k = f"{r['año']}-{r['mes']}"
                    recovery_period[k] = recovery_period.get(k, 0) + diff
                    doc = r['documento']
                    if doc not in recovery_by_client:
                        recovery_by_client[doc] = {'nombre': r['nombre'], 'documento': doc, 'total': 0, 'periodos': []}
                    recovery_by_client[doc]['total'] += diff
                    recovery_by_client[doc]['periodos'].append({'año': r['año'], 'mes': r['mes'], 'recuperado': diff})
            prev = r
    clients = sorted(recovery_by_client.values(), key=lambda x: -x['total'])
    return recovery_period, clients[:200]

if __name__ == '__main__':
    print("=== Actualizando dashboard desde Google Sheets ===")
    csv_text = fetch_sheet()
    records = parse_csv(csv_text)
    if not records:
        print("ERROR: No se cargaron registros. Verifica que la hoja sea pública.")
        sys.exit(1)
    print("Computing recovery data...")
    rec_period, rec_clients = build_recovery(records)
    print(f"  Recovery periods: {len(rec_period)}, clients: {len(rec_clients)}")
    bundle = {'records': records, 'recovery_by_period': rec_period, 'recovery_clients': rec_clients}
    raw = json.dumps(bundle, ensure_ascii=False).encode('utf-8')
    compressed = gzip.compress(raw, compresslevel=9)
    b64 = base64.b64encode(compressed).decode()
    print(f"  Bundle: {len(raw):,} bytes → {len(b64):,} b64 chars")
    print("Reading template.html...")
    with open('template.html', 'r', encoding='utf-8') as f:
        html = f.read()
    html = html.replace('PLACEHOLDER_DATA', b64)
    with open('index.html', 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"  index.html written: {len(html):,} chars")
    print("=== Listo! ===")
