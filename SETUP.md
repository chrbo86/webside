# Morgenbrief – GitHub Pages oppsett

## Steg 1 – Last opp filene til repoet

Push hele denne mappen til `github.com/chrbo86/webside` (main-branch).

```bash
git clone https://github.com/chrbo86/webside.git
cp -r morgenbrief-github/. webside/
cd webside
git add -A
git commit -m "Legg til morgenbrief-oppsett"
git push
```

## Steg 2 – Legg til Anthropic API-nøkkel som GitHub Secret

1. Gå til **Settings → Secrets and variables → Actions** i repoet
2. Klikk **New repository secret**
3. Navn: `ANTHROPIC_API_KEY`
4. Verdi: Din Anthropic API-nøkkel (fra console.anthropic.com)

## Steg 3 – Aktiver GitHub Pages

1. Gå til **Settings → Pages**
2. Under *Source*, velg **Deploy from a branch**
3. Branch: `main`, mappe: `/ (root)`
4. Klikk **Save**

Siden vil være tilgjengelig på: `https://chrbo86.github.io/webside/`

## Steg 4 – Kjør første gang manuelt (valgfritt)

1. Gå til **Actions** i repoet
2. Klikk på **Morgenbrief**-workflowen
3. Klikk **Run workflow → Run workflow**

Briefen genereres og publiseres i løpet av ~30 sekunder.

## Daglig kjøring

GitHub Actions kjører automatisk kl. 06:00 Oslo-tid hver dag.

Du kan endre tidspunktet i `.github/workflows/morgenbrief.yml`:
```yaml
- cron: "0 5 * * *"   # 05:00 UTC = 06:00 CET / 07:00 CEST
```

## Filstruktur

```
/
├── index.html                  ← Alltid siste brief
├── archive/
│   ├── index.html              ← Arkivoversikt
│   ├── entries.json            ← Arkivmetadata
│   └── YYYY-MM-DD.html         ← Én fil per dag
├── scripts/
│   └── generate.py             ← Selve generatoren
├── requirements.txt
└── .github/workflows/
    └── morgenbrief.yml         ← GitHub Actions workflow
```
